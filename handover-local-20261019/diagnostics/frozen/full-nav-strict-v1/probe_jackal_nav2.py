"""Real local Nav2 diagnostic: PhysX map/cloud, wheel control, and evidence.

This uses the same ground exclusion and full attitude transform as the repo's
jackal_proximity_cloud.py, with an explicitly named diagnostic sensor frame.
It does not validate localization, RTX lidar, reviewed GT, or paper episodes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
import time
from typing import Any


def rotation(q: list[float]) -> Any:
    import numpy as np
    x, y, z, w = np.asarray(q) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def scene_hit(query: Any, origin: Any, direction: Any, distance: float) -> dict | None:
    hits, errors = [], []
    def collect(hit: Any) -> bool:
        # Isaac 4.5 raycast_all callbacks use RaycastHit objects; unlike
        # raycast_closest they are not dictionaries. Match the repository's
        # generate_traversability_raycast adapter and fail outside the C callback.
        try:
            value = (lambda key: hit.get(key)) if isinstance(hit,dict) else (lambda key: getattr(hit,key,None))
            path = str(value('collision') or value('rigidBody') or value('rigid_body') or '')
            hit_distance = float(value('distance'))
            if not math.isfinite(hit_distance) or hit_distance < 0:
                raise ValueError('Invalid PhysX hit distance')
            if not path.startswith('/World/ugv'):
                hits.append({'distance':hit_distance,'collision':path})
            return True
        except Exception as exc:
            errors.append(exc)
            return False
    query.raycast_all(tuple(float(v) for v in origin), tuple(float(v) for v in direction), distance, collect)
    if errors: raise RuntimeError('PhysX raycast callback failed') from errors[0]
    return min(hits, key=lambda h: h['distance']) if hits else None


def generate_map(query: Any, output: Path, center: list[float], goals: list[list[float]]) -> dict:
    import numpy as np
    from PIL import Image
    resolution, size = .1, 200
    origin = [math.floor(center[0])-10., math.floor(center[1])-10.]
    grid = np.full((size, size), 205, dtype=np.uint8)
    hit_paths: dict[str, int] = {}
    for iy in range(size):
        for ix in range(size):
            x, y = origin[0]+(ix+.5)*resolution, origin[1]+(iy+.5)*resolution
            hit = scene_hit(query, (x,y,3.), (0.,0.,-1.), 3.1)
            if hit:
                z = 3.-float(hit['distance'])
                grid[size-1-iy, ix] = 0 if z > .05 else 254
                if z > .05:
                    path = str(hit.get('collision', hit.get('rigidBody', 'unknown')))
                    hit_paths[path] = hit_paths.get(path, 0)+1
    # Unknown border prevents plans leaving the measured window.
    grid[[0,-1],:] = 205
    grid[:,[0,-1]] = 205
    Image.fromarray(grid).save(output/'local-map.pgm')
    Image.fromarray(grid).resize((800,800),Image.Resampling.NEAREST).save(output/'local-map.png')
    (output/'local-map.yaml').write_text(
        f'image: local-map.pgm\nresolution: {resolution}\norigin: [{origin[0]}, {origin[1]}, 0.0]\n'
        'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n',encoding='utf-8')
    result = {'method':'vertical PhysX raycast, z=3 to -0.1 m, self excluded, obstacle z>0.05 m',
              'resolution_m':resolution,'width':size,'height':size,'origin':origin,
              'occupied_cells':int((grid==0).sum()),'free_cells':int((grid==254).sum()),
              'unknown_cells':int((grid==205).sum()),'obstacle_paths':hit_paths,
              'reviewed':False,'limitations':'local diagnostic projection; not reviewed traversability or semantic GT'}
    (output/'map-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if not result['occupied_cells']:
        raise RuntimeError('Measured map contains no obstacles; inspect query results')
    for label, xy in [('spawn',center)]+[(f'goal-{i+1}',g) for i,g in enumerate(goals)]:
        ix,iy = [int((xy[k]-origin[k])/resolution) for k in (0,1)]
        if not (4 <= ix < size-4 and 4 <= iy < size-4):
            raise RuntimeError(f'{label} outside measured map')
        patch = grid[size-1-iy-3:size-1-iy+4, ix-3:ix+4]
        if not (patch == 254).all():
            raise RuntimeError(f'{label} footprint not free in actual raycast map')
    return result


def route_geometry(output: Path, map_info: dict, points: list[list[float]]) -> dict:
    """Diagnostic geometry audit against measured occupancy, not a planner or GT score."""
    if map_info.get('scope')=='unreviewed_full_map_diagnostic':
        from probe_full_map_nav2 import geometry
        return geometry(output,map_info,points)
    import numpy as np
    from PIL import Image
    grid=np.array(Image.open(output/'local-map.pgm'))[::-1]
    resolution=map_info['resolution_m'];origin=np.array(map_info['origin'])
    cells=np.argwhere(grid==0)
    centers=origin+(cells[:,::-1]+.5)*resolution
    minimum=float('inf');outside=0;occupied=0
    for offset in range(0,len(points),128):
        chunk=np.asarray(points[offset:offset+128])[:,:2]
        delta=np.maximum(np.abs(chunk[:,None,:]-centers[None,:,:])-resolution/2,0.)
        minimum=min(minimum,float(np.sqrt((delta*delta).sum(axis=2)).min()))
        indices=np.floor((chunk-origin)/resolution).astype(int)
        for ix,iy in indices:
            if not (0<=ix<grid.shape[1] and 0<=iy<grid.shape[0]) or grid[iy,ix]==205: outside+=1
            elif grid[iy,ix]==0: occupied+=1
    return {'min_center_clearance_m':minimum,
            'min_circumscribed_footprint_clearance_m':minimum-math.hypot(.508/2,.43/2),
            'center_samples_on_obstacles':occupied,'center_samples_unknown_or_outside':outside}


def run_navigation(world: Any, robot: Any, drive: Any, camera: Any, output: Path,
                   seconds: float, run_id: str, goals: list[list[float]], require_detour: bool=False,
                   full_map_manifest: Path | None=None) -> dict:
    import numpy as np
    import rclpy
    from builtin_interfaces.msg import Time
    from geometry_msgs.msg import TransformStamped, Twist
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import PointCloud2, PointField
    from tf2_msgs.msg import TFMessage
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from omni.isaac.dynamic_control import _dynamic_control
    import omni.physx
    import omni.usd
    from pxr import UsdGeom, Gf
    from PIL import Image

    query = omni.physx.get_physx_scene_query_interface()
    dc = _dynamic_control.acquire_dynamic_control_interface()
    body = dc.get_rigid_body('/World/ugv/base_link')
    if not body or body == _dynamic_control.INVALID_HANDLE:
        raise RuntimeError('Jackal PhysX body unavailable')
    indices = np.array([robot.get_dof_index(n) for n in drive.config.wheel_joint_names], dtype=np.int32)
    def state() -> dict:
        pose = dc.get_rigid_body_pose(body)
        q = [float(v) for v in (pose.r.x,pose.r.y,pose.r.z,pose.r.w)]
        return {'position':[float(v) for v in (pose.p.x,pose.p.y,pose.p.z)],'quaternion_xyzw':q,
                'linear_world':[float(v) for v in dc.get_rigid_body_linear_velocity(body)],
                'angular_world':[float(v) for v in dc.get_rigid_body_angular_velocity(body)]}
    initial = state()
    if full_map_manifest:
        from probe_full_map_nav2 import load_map
        measured_map=load_map(full_map_manifest,output,initial['position'][:2],goals)
    else:
        measured_map = generate_map(query,output,initial['position'][:2],goals)
    direct_legs=[]
    for start,end in zip([initial['position'][:2]]+goals[:-1],goals):
        points=np.linspace(start,end,max(2,int(math.dist(start,end)/.025)+1)).tolist()
        direct_legs.append({'start':start,'goal':end,**route_geometry(output,measured_map,points)})
    if require_detour and not any(leg['center_samples_on_obstacles']>0 or leg.get('center_samples_outside_selected_map',0)>0 for leg in direct_legs):
        raise RuntimeError('Detour test requires a direct leg blocked by measured obstacles')
    (output/'route-preflight.json').write_text(json.dumps(direct_legs,indent=2),encoding='utf-8')
    report = {'scope':'full_map_local_route_diagnostic_only' if full_map_manifest else 'local_route_diagnostic_only','run_id':run_id,'goal_xy':goals[-1],'goals_xy':goals,
              'require_detour':require_detour,'direct_legs':direct_legs,
              'odometry_source':'PhysX body state, no localization validation',
              'sensor_source':'CPU PhysX raycast fan, not RTX lidar',
              'tf_tree':['map -> ugv/base_link (PhysX)','ugv/base_link -> ugv/diagnostic_lidar (static)'],
              'map':measured_map,'samples':[],'commands':[],'clouds':[],'images':[], 'passed':False}
    rclpy.init(args=[])
    node = rclpy.create_node('raven_jackal_nav2_probe',namespace='/ugv')
    pubs = {name:node.create_publisher(typ,topic,10) for name,typ,topic in [
        ('clock',Clock,'/clock'),('odom',Odometry,'/ugv/odom'),('tf',TFMessage,'/tf'),
        ('cloud',PointCloud2,'/ugv/sensors/ouster/point_cloud')]}
    static = node.create_publisher(TFMessage,'/tf_static',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    fixed = TransformStamped()
    fixed.header.frame_id,fixed.child_frame_id = 'ugv/base_link','ugv/diagnostic_lidar'
    fixed.transform.translation.z=.42
    fixed.transform.rotation.w=1.
    static.publish(TFMessage(transforms=[fixed]))
    command=[0.,0.]
    last_command_wall,last_command_sim=-1e9,-1e9
    def on_command(msg: Twist) -> None:
        nonlocal command,last_command_wall,last_command_sim
        if not all(math.isfinite(v) for v in (msg.linear.x,msg.angular.z)):
            return
        command=[max(-.3,min(.3,msg.linear.x)),max(-.4,min(.4,msg.angular.z))]
        last_command_wall,last_command_sim=time.monotonic(),float(world.current_time)
        report['commands'].append({'sim_time_s':last_command_sim,'requested':[msg.linear.x,msg.angular.z],'applied':command[:]})
    node.create_subscription(Twist,'/ugv/cmd_vel',on_command,20)
    directions=np.array([(math.cos(math.radians(e))*math.cos(a),math.cos(math.radians(e))*math.sin(a),math.sin(math.radians(e)))
                         for e in (-38,-21,-12,-4,2,6,12,20,30,45) for a in np.linspace(0,2*math.pi,120,endpoint=False)])
    def stamp(value: float) -> Time:
        ns=round(value*1e9)
        return Time(sec=ns//10**9,nanosec=ns%10**9)
    def capture(name: str, current: dict) -> None:
        p=current['position']
        cam=UsdGeom.Xformable(omni.usd.get_context().get_stage().GetPrimAtPath(camera.prim_path))
        cam.ClearXformOpOrder()
        cam.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(p[0]-2,p[1]+2.5,p[2]+1.7),
            Gf.Vec3d(p[0],p[1],p[2]+.1),Gf.Vec3d(0,0,1)).GetInverse())
        for _ in range(12): world.render()
        rgb=np.asarray(camera.get_rgba())[...,:3].astype(np.uint8)
        if rgb.ndim!=3 or rgb.std()<1: raise RuntimeError('Actual camera screenshot unavailable')
        path=output/f'nav2-{name}.png'
        Image.fromarray(rgb).save(path)
        report['images'].append({'file':path.name,'sim_time_s':float(world.current_time),'position':p})

    started=time.monotonic()
    sim_start=float(world.current_time)
    last_publish,last_cloud=-1e9,-1e9
    step=0
    done_at=None
    done_path=output.parent/f'{output.name.removesuffix("-frames")}-wsl/done.json'
    progress_path=done_path.with_name('goal-progress.json')
    last_progress_check=-1e9
    saved=set()
    try:
        capture('start',initial)
        (output/'nav2-ready.json').write_text(json.dumps({'run_id':run_id,'goal_xy':goals[-1],
            'goals_xy':goals,'map':'local-map.yaml','full_map':bool(full_map_manifest),
            'map_pgm_sha256':measured_map.get('source_map_pgm_sha256')}),encoding='utf-8')
        logging.info('NAV2_READY %s',run_id)
        while time.monotonic()-started < seconds:
            for _ in range(5): rclpy.spin_once(node,timeout_sec=0)
            now=float(world.current_time)
            if done_at is None and done_path.exists():
                report['wsl_result']=json.loads(done_path.read_text(encoding='utf-8'))
                if report['wsl_result'].get('run_id') != run_id: raise RuntimeError('Wrong WSL run identifier')
                done_at=now
            stale=now-last_command_sim>.5 or time.monotonic()-last_command_wall>1.
            applied=[0.,0.] if stale or done_at is not None else command
            wheel=drive.wheel_velocities(*applied)
            robot.set_joint_velocities(np.array([wheel[n] for n in drive.config.wheel_joint_names]),joint_indices=indices)
            world.step(render=(step%8==0));step+=1
            now=float(world.current_time);current=state();rot=rotation(current['quaternion_xyzw'])
            if rot[2,2]<math.cos(.5) or current['position'][2]<-.1:
                raise RuntimeError('Jackal tilt/ground safety bound exceeded')
            if math.dist(current['position'][:2],initial['position'][:2])>8.:
                raise RuntimeError('Local diagnostic travel bound exceeded')
            if now-last_publish>=.05:
                t=stamp(now);pubs['clock'].publish(Clock(clock=t))
                odom=Odometry();odom.header.stamp=t;odom.header.frame_id='map';odom.child_frame_id='ugv/base_link'
                odom.pose.pose.position.x,odom.pose.pose.position.y,odom.pose.pose.position.z=current['position']
                q=current['quaternion_xyzw']
                odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z,odom.pose.pose.orientation.w=q
                v=rot.T@current['linear_world'];omega=rot.T@current['angular_world']
                odom.twist.twist.linear.x,odom.twist.twist.linear.y,odom.twist.twist.linear.z=map(float,v)
                odom.twist.twist.angular.z=float(omega[2]);pubs['odom'].publish(odom)
                tf=TransformStamped();tf.header=odom.header;tf.child_frame_id=odom.child_frame_id
                tf.transform.translation.x,tf.transform.translation.y,tf.transform.translation.z=current['position']
                tf.transform.rotation=odom.pose.pose.orientation;pubs['tf'].publish(TFMessage(transforms=[tf]))
                report['samples'].append({'sim_time_s':now,'applied_command':applied[:],'stale':stale,**current})
                last_publish=now
            if now-last_cloud>=.2:
                origin=np.asarray(current['position'])+rot@np.array([0.,0.,.42])
                points=[]
                for direction, world_direction in zip(directions,directions@rot.T):
                    hit=scene_hit(query,origin,world_direction,10.)
                    if hit and .3<=hit['distance']<=10. and origin[2]+hit['distance']*world_direction[2]>=.05:
                        points.append(direction*hit['distance'])
                points=np.asarray(points,dtype='<f4').reshape(-1,3)
                msg=PointCloud2();msg.header.stamp=stamp(now);msg.header.frame_id='ugv/diagnostic_lidar'
                msg.height=1;msg.width=len(points);msg.point_step=12;msg.row_step=12*len(points);msg.is_dense=True
                msg.fields=[PointField(name=n,offset=i*4,datatype=PointField.FLOAT32,count=1) for i,n in enumerate(('x','y','z'))]
                msg.data=points.tobytes();pubs['cloud'].publish(msg)
                report['clouds'].append({'sim_time_s':now,'points':len(points),'sha256':hashlib.sha256(msg.data).hexdigest()})
                if len(report['clouds'])==1:
                    np.savez_compressed(output/'cloud-first.npz',sensor_xyz=points,world_xyz=points@rot.T+origin)
                last_cloud=now
            distance=math.dist(current['position'][:2],initial['position'][:2])
            if distance>=1 and 'moving' not in saved:
                capture('moving',current);saved.add('moving')
            if now-last_progress_check>=.5:
                if progress_path.exists():
                    progress=json.loads(progress_path.read_text(encoding='utf-8'))
                    if progress['run_id']!=run_id: raise RuntimeError('Wrong progress run identifier')
                    for entry in progress['goals']:
                        name=f'after-goal-{entry["index"]+1:02d}'
                        if name not in saved:
                            capture(name,current);saved.add(name)
                last_progress_check=now
            if distance>=3 and 'en-route' not in saved:
                capture('en-route',current);saved.add('en-route')
            if done_at is not None and now-done_at>=2.:
                capture('stopped',current);break
            # Pace at no faster than real time; deadlines and goal metrics use /clock.
            delay=(now-sim_start)-(time.monotonic()-started)
            if delay>0: time.sleep(min(delay,.02))
        final=state();samples=report['samples']
        geometry=route_geometry(output,measured_map,[s['position'][:2] for s in samples])
        yaws=np.unwrap([math.atan2(2*(s['quaternion_xyzw'][3]*s['quaternion_xyzw'][2]+s['quaternion_xyzw'][0]*s['quaternion_xyzw'][1]),
                                  1-2*(s['quaternion_xyzw'][1]**2+s['quaternion_xyzw'][2]**2)) for s in samples])
        report['metrics']={'final_goal_error_m':math.dist(final['position'][:2],goals[-1]),
            'displacement_m':math.dist(final['position'][:2],initial['position'][:2]),
            'path_length_m':sum(math.dist(a['position'][:2],b['position'][:2]) for a,b in zip(samples,samples[1:])),
            'final_speed_mps':math.hypot(*final['linear_world'][:2]),'sim_duration_s':float(world.current_time)-sim_start,
            'cloud_count':len(report['clouds']),'nonempty_clouds':sum(c['points']>0 for c in report['clouds']),
            'accumulated_abs_yaw_rad':float(np.abs(np.diff(yaws)).sum()),'map_geometry':geometry}
        m=report['metrics']
        report['passed']=bool(report.get('wsl_result',{}).get('passed') and m['final_goal_error_m']<.4
            and m['path_length_m']>1. and m['final_speed_mps']<.04 and m['nonempty_clouds']>10
            and geometry.get('center_samples_outside_selected_map',0)==0
            and (not require_detour or (geometry['min_circumscribed_footprint_clearance_m']>0
                 and geometry['center_samples_unknown_or_outside']==0 and m['accumulated_abs_yaw_rad']>1.)))
        logging.info('NAV2_NATIVE_RESULT %s',report['metrics'])
    finally:
        robot.set_joint_velocities(np.zeros(4),joint_indices=indices)
        report['wall_seconds']=time.monotonic()-started
        (output/'jackal-nav2.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        node.destroy_node();rclpy.shutdown()
    if not report['passed']: raise RuntimeError('Nav2 local goal validation incomplete; inspect actual evidence')
    return report
