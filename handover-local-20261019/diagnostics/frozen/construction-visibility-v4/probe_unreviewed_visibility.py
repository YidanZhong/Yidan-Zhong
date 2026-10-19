"""Real PhysX samples at private geometric candidate poses; never approves GT."""
from pathlib import Path
import hashlib,json,math
from typing import Any

def run_visibility(world: Any, stage: Any, output: Path, input_path: Path) -> dict:
    import omni.physx
    from pxr import Usd,UsdGeom
    from airground_benchmark.ground_truth import (TargetInstance,ConfirmationPose,
        RaycastConfirmationVisibilityConfig,_raycast_confirmation_pose_metric,_obb_surface_distance_2d)
    from airground_benchmark.isaac_los import make_isaac_physx_raycast_fn
    payload=json.loads(input_path.read_text(encoding='utf-8-sig'))
    if payload['scope']!='unreviewed_candidate_visibility_diagnostic' or payload['formal_gt_approved']:
        raise ValueError('Only explicitly unreviewed private diagnostics are accepted')
    if hashlib.sha256((output/'colliders.json').read_bytes()).hexdigest()!=payload['colliders_sha256']:
        raise RuntimeError('Actual collider identity differs from the sampled map')
    if len(payload['rows'])>64:raise ValueError('Bounded diagnostic accepts at most 64 instances')
    from pxr import PhysxSchema
    from isaacsim.core.simulation_manager import SimulationManager
    import omni.kit.app
    timing={'requested_physics_dt_s':1/250,'stride_steps':25,'snapshots':[]}
    def timing_snapshot(label):
        snapshot={'label':label,'physics_dt_s':float(world.get_physics_dt()),'sim_time_s':float(world.current_time),
                  'context_path':str(world.get_physics_context().prim_path),'active_scenes':[],'manager_scenes':[]}
        from pxr import UsdPhysics
        for prim in stage.Traverse():
            if prim.IsA(UsdPhysics.Scene):
                snapshot['active_scenes'].append({'path':str(prim.GetPath()),'hz':PhysxSchema.PhysxSceneAPI(prim).GetTimeStepsPerSecondAttr().Get()})
        # Read-only diagnostic of the SDK's scene registry, not a mutation.
        for path,api in SimulationManager._physics_scene_apis.items():
            snapshot['manager_scenes'].append({'path':str(path),'active':bool(api.GetPrim().IsActive()),'hz':api.GetTimeStepsPerSecondAttr().Get()})
        timing['snapshots'].append(snapshot)
        (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))
    timing_snapshot('before_event_flush')
    for _ in range(3):omni.kit.app.get_app().update()
    timing_snapshot('after_three_app_updates')
    world.set_simulation_dt(physics_dt=1/250,rendering_dt=1/250)
    timing_snapshot('after_reapply')
    if abs(float(world.get_physics_dt())-1/250)>1e-7:raise RuntimeError('Actual step rate differs from requested 250 Hz after bounded event flush')
    config=RaycastConfirmationVisibilityConfig(camera_height_m=1.2,min_distance_m=1.5,max_distance_m=8.,
        horizontal_fov_rad=math.pi/2,min_visible_fraction=.2,required_consecutive_frames=5,
        target_sample_count=5,occlusion_epsilon_m=.001,
        ignored_prim_prefixes=('/World/uav','/World/UAV','/World/ugv','/World/UGV'))
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']);prepared=[];skipped=[]
    for row in payload['rows']:
        instance=TargetInstance.model_validate(row['target'])
        if instance.verified or instance.ground_reachable!='unknown':raise ValueError('Input approval flags changed')
        if not instance.usd_prim_path or not row['poses']:
            skipped.append({'instance_id':instance.instance_id,'reason':row['skip_reason']});continue
        if len(row['poses'])>8:raise ValueError('More than eight poses for one target')
        prim=stage.GetPrimAtPath(instance.usd_prim_path)
        if not prim:raise RuntimeError('Target candidate missing: '+instance.instance_id)
        box=cache.ComputeWorldBound(prim).ComputeAlignedRange();candidate=row['candidate']
        for actual,expected in [(box.GetMidpoint(),candidate['center_xyz_m']),(box.GetSize(),candidate['size_xyz_m'])]:
            if max(abs(float(a)-b) for a,b in zip(actual,expected))>.02:raise RuntimeError('Candidate geometry changed')
        for index,pose in enumerate(row['poses']):
            point=pose['position_xyz_m'];surface=_obb_surface_distance_2d(*point[:2],instance.obb)
            center=math.hypot(point[0]-instance.obb.center_xyz_m[0],point[1]-instance.obb.center_xyz_m[1])
            if not 1.5<=surface<=8. or not 1.5<=center<=8.:raise ValueError('Pose violates original distance gates')
            value=ConfirmationPose(frame='map',position_xyz_m=point,yaw_rad=pose['yaw_rad'],distance_to_target_m=0.,visible_fraction=0.)
            prepared.append({'instance':instance,'pose':value,'index':index,'cell':pose['flat_cell'],'surface':surface,'frames':[]})
    query=omni.physx.get_physx_scene_query_interface();raw_calls=[]
    class SnapshotQuery:
        def raycast_all(self,origin,direction,distance,callback):
            hits=[];errors=[]
            def collect(hit):
                try:
                    get=hit.get if isinstance(hit,dict) else lambda k:getattr(hit,k,None)
                    path=str(get('collision') or get('rigid_body') or get('rigidBody') or '')
                    if not path:raise RuntimeError('Missing actual collider path')
                    copied={'prim_path':path,'distance_m':float(get('distance')),
                            'position_xyz_m':[float(v) for v in get('position')],
                            'normal_xyz':[float(v) for v in get('normal')]}
                    hits.append(copied)
                    return callback({'prim_path':path,'distance':copied['distance_m']})
                except Exception as exc:errors.append(exc);return False
            query.raycast_all(origin,direction,float(distance),collect)
            raw_calls.append({'origin_xyz_m':list(origin),'direction_xyz':list(direction),'distance_m':float(distance),'hits':hits})
            if errors:raise RuntimeError('Native PhysX callback failed') from errors[0]
    raycast=make_isaac_physx_raycast_fn(SnapshotQuery())
    trace=output/'visibility-frames.unreviewed.jsonl';times=[]
    with trace.open('x',encoding='utf-8') as stream:
        for frame_index in range(5):
            if frame_index:
                for _ in range(25):world.step(render=False)
            stamp=float(world.current_time);times.append(stamp)
            for entry in prepared:
                raw_calls.clear();instance=entry['instance'];pose=entry['pose']
                metric=_raycast_confirmation_pose_metric(entry['index'],pose,instance,raycast,config).model_dump(mode='json')
                metric.pop('consecutive_visible_frames')
                target_hits=sum(h['prim_path']==instance.usd_prim_path or h['prim_path'].startswith(instance.usd_prim_path+'/') for ray in raw_calls for h in ray['hits'])
                zero_hits=sum(h['distance_m']<=1e-6 for ray in raw_calls for h in ray['hits'])
                row={'frame_index':frame_index,'sim_time_s':stamp,'instance_id':instance.instance_id,'pose_index':entry['index'],
                     'flat_cell':entry['cell'],'position_xyz_m':list(pose.position_xyz_m),'yaw_rad':pose.yaw_rad,
                     'obb_surface_distance_m':entry['surface'],'target_prim_hit_count':target_hits,'zero_distance_hit_count':zero_hits,'metric':metric,'rays':list(raw_calls)}
                stream.write(json.dumps(row)+'\n');entry['frames'].append({'valid':metric['valid'],'sim_time_s':stamp,'target_hits':target_hits,'zero_hits':zero_hits})
            if float(world.current_time)!=stamp:raise RuntimeError('World advanced within a sample batch')
            stream.flush()
    gaps=[b-a for a,b in zip(times,times[1:])]
    if not all(0<g<=.15 for g in gaps):raise RuntimeError('Five distinct PhysX sample times do not meet frame-gap gate')
    rows=[]
    for entry in prepared:
        frames=entry['frames'];consecutive=5 if all(f['valid'] for f in frames) else 0
        hits=sum(f['target_hits'] for f in frames)
        zero_hits=sum(f['zero_hits'] for f in frames)
        rows.append({'instance_id':entry['instance'].instance_id,'pose_index':entry['index'],'flat_cell':entry['cell'],
                     'actual_consecutive_visible_frames':consecutive,'target_prim_hit_count':hits,
                     'zero_distance_hit_count':zero_hits,
                     'diagnostic_pose_passed':consecutive==5 and hits>0 and zero_hits==0,'human_review':'pending'})
    valid_ids=sorted({r['instance_id'] for r in rows if r['diagnostic_pose_passed']})
    result={'scope':'actual PhysX visibility at unreviewed private candidate poses','formal_gt_approved':False,
            'execution_complete':True,'poses_sampled':len(rows),'instances_sampled':len({r['instance_id'] for r in rows}),
            'timing':timing,'five_frame_times_s':times,'frame_gaps_s':gaps,'configuration':config.model_dump(mode='json'),
            'diagnostic_instances_with_passing_pose':valid_ids,'rows':rows,'skipped':skipped,
            'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),
            'limitations':['No real RGB or ROS camera stream generated; five real PhysX times match official raycast trace method.',
                           'Candidate bindings and OBBs remain unreviewed; no formal arrival set or target flags changed.',
                           'Finite eight-direction sampling cannot prove global invisibility when all sampled poses fail.',
                           'Poses are private diagnostic observers, not an actual UGV patrol.']}
    (output/'visibility-summary.unreviewed.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
