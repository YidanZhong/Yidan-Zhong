"""Inspect one unreviewed target at an actual reached pose; never creates GT.

The camera is a diagnostic observer oriented toward the known target, not a
semantic detector or a validated physical camera mount. Raw PhysX hit records
and RGB frames accompany the repository's per-pose visibility calculation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
import sys
import types
from typing import Any


def run_confirmation(world: Any, camera: Any, output: Path, config_path: Path,
                     benchmark_path: Path) -> dict:
    import numpy as np
    import omni.physx
    import omni.usd
    from omni.isaac.dynamic_control import _dynamic_control
    from PIL import Image
    from pxr import Gf, Usd, UsdGeom

    # Match the official visibility runner's lightweight benchmark import.
    package = types.ModuleType('airground_benchmark')
    package.__path__ = [str(benchmark_path)]
    sys.modules.setdefault('airground_benchmark', package)
    from airground_benchmark.ground_truth import (
        TargetInstance, ConfirmationPose, RaycastConfirmationVisibilityConfig,
        _raycast_confirmation_pose_metric, _obb_surface_distance_2d,
    )
    from airground_benchmark.isaac_los import make_isaac_physx_raycast_fn

    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    instance = TargetInstance.model_validate(config['target'])
    if instance.verified or instance.ground_reachable != 'unknown':
        raise ValueError('This diagnostic requires an unreviewed target with unknown reachability')
    stage = omni.usd.get_context().get_stage()
    prim = stage.GetPrimAtPath(instance.usd_prim_path)
    if not prim.IsValid():
        raise RuntimeError('Target prim does not exist in the loaded scene')
    box = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render']).ComputeWorldBound(prim).ComputeAlignedRange()
    actual_center = np.array(box.GetMidpoint());actual_size = np.array(box.GetSize())
    if np.linalg.norm(actual_center - np.array(config['candidate']['center_xyz_m'])) > .02:
        raise RuntimeError('Loaded target bounds differ from the exported candidate')
    query = omni.physx.get_physx_scene_query_interface()
    class SnapshotQuery:
        def raycast_all(self, origin: Any, direction: Any, distance: float, callback: Any) -> None:
            # Copy callback-owned values immediately; static colliders may have
            # an empty rigid-body path, so prefer the actual collision prim.
            errors = []
            def collect(hit: Any) -> bool:
                try:
                    value = (lambda k: hit.get(k)) if isinstance(hit,dict) else (lambda k: getattr(hit,k,None))
                    path = str(value('collision') or value('rigid_body') or value('rigidBody') or '')
                    if not path:
                        raise RuntimeError('PhysX hit has no collider identity')
                    return callback({'prim_path':path,'distance':float(value('distance'))})
                except Exception as exc:
                    errors.append(exc)
                    return False
            query.raycast_all(origin,direction,distance,collect)
            if errors:
                raise RuntimeError('Target visibility raycast callback failed') from errors[0]
    raycast = make_isaac_physx_raycast_fn(SnapshotQuery())
    dc = _dynamic_control.acquire_dynamic_control_interface()
    body = dc.get_rigid_body('/World/ugv/base_link')
    if not body or body == _dynamic_control.INVALID_HANDLE:
        raise RuntimeError('Actual Jackal body is unavailable')
    target = np.array(instance.obb.center_xyz_m)
    visibility_config = RaycastConfirmationVisibilityConfig(
        camera_height_m=1.2, min_distance_m=1.5, max_distance_m=8.,
        horizontal_fov_rad=math.pi/2, min_visible_fraction=.2,
        required_consecutive_frames=5, target_sample_count=5,
        occlusion_epsilon_m=.001, ignored_prim_prefixes=('/World/ugv',))
    usd_camera = UsdGeom.Camera(stage.GetPrimAtPath(camera.prim_path))
    usd_camera.GetFocalLengthAttr().Set(18.)
    usd_camera.GetHorizontalApertureAttr().Set(36.)
    width, height = camera.get_resolution()
    usd_camera.GetVerticalApertureAttr().Set(36.*height/width)
    camera_transform = UsdGeom.Xformable(usd_camera)

    def aim(eye: list[float], look: list[float]) -> None:
        camera_transform.ClearXformOpOrder()
        camera_transform.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(
            Gf.Vec3d(*eye), Gf.Vec3d(*look), Gf.Vec3d(0,0,1)).GetInverse())

    def save_rgb(name: str) -> dict:
        rgb = np.asarray(camera.get_rgba())[...,:3].astype(np.uint8)
        if rgb.shape != (height,width,3) or rgb.std() < 1:
            raise RuntimeError('Target camera frame is invalid')
        path = output/name
        Image.fromarray(rgb).save(path)
        return {'file':name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'sim_time_s':float(world.current_time),
                'rendering_frame':int(camera.get_current_frame().get('rendering_frame',-1))}

    report = {'scope':'single_unreviewed_target_diagnostic', 'passed':False,
        'formal_episode':False, 'semantic_detection_performed':False,
        'review_status':'pending_human_review', 'target':config['target'],
        'candidate':config['candidate'], 'task_id':config['task_id'],
        'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'actual_candidate_bounds':{'center_xyz_m':actual_center.tolist(),'size_xyz_m':actual_size.tolist()},
        'camera':'diagnostic observer at actual reached XY, z=1.2 above support plane, target-facing yaw',
        'visibility_config':visibility_config.model_dump(mode='json'),
        'distance_note':'Official visibility metric uses center distance; OBB surface distance is separately recorded for the reach window.',
        'frames':[], 'images':[]}
    try:
        pose = dc.get_rigid_body_pose(body)
        xy = [float(pose.p.x),float(pose.p.y)]
        yaw = math.atan2(target[1]-xy[1],target[0]-xy[0])
        aim([*xy,1.2],[xy[0]+math.cos(yaw),xy[1]+math.sin(yaw),1.2])
        for _ in range(30): world.step(render=True)
        for index in range(5):
            for _ in range(12): world.step(render=True)
            live = dc.get_rigid_body_pose(body)
            if math.hypot(live.p.x-xy[0],live.p.y-xy[1]) > .05:
                raise RuntimeError('Robot moved while acquiring stopped confirmation evidence')
            hits = []
            def traced(sender: Any, recipient: Any) -> Any:
                result = raycast(sender, recipient)
                hits.append({'origin':[sender.x_m,sender.y_m,sender.z_m],
                    'endpoint':[recipient.x_m,recipient.y_m,recipient.z_m],
                    'hits':[{'distance_m':h.distance_m,'prim_path':h.prim_path} for h in result]})
                return result
            # visible_fraction is an unused input for this PhysX metric; no
            # synthetic confirmation region or reviewed manifest is created.
            candidate_pose = ConfirmationPose(frame='map', position_xyz_m=(*xy,0.),
                yaw_rad=yaw,distance_to_target_m=0.,visible_fraction=0.)
            metric = _raycast_confirmation_pose_metric(0,candidate_pose,instance,traced,visibility_config).model_dump(mode='json')
            metric.pop('consecutive_visible_frames')  # measure actual distinct frames below
            image = save_rgb(f'target-confirmation-{index+1:02d}.png')
            surface = _obb_surface_distance_2d(*xy,instance.obb)
            report['images'].append(image)
            report['frames'].append({'index':index, 'sim_time_s':float(world.current_time),
                'robot_position_xyz_m':[live.p.x,live.p.y,live.p.z],
                'camera_position_xyz_m':[*xy,1.2], 'camera_yaw_rad':yaw,
                'obb_surface_distance_m':surface, 'metric':metric,'rays':hits})
        aim([xy[0]-5,xy[1]-6,7.], [*target[:2],.8])
        for _ in range(30): world.render()
        report['images'].append(save_rgb('target-context.png'))
        frames=report['frames']
        gaps=[b['sim_time_s']-a['sim_time_s'] for a,b in zip(frames,frames[1:])]
        frame_ids=[i['rendering_frame'] for i in report['images'][:5]]
        target_hit_count=sum(h['prim_path'] and (h['prim_path']==instance.usd_prim_path or
            h['prim_path'].startswith(instance.usd_prim_path+'/')) for f in frames for ray in f['rays'] for h in ray['hits'])
        report['target_prim_hit_count']=target_hit_count
        report['actual_consecutive_visible_frames']=5 if all(f['metric']['valid'] and
            1.5<=f['obb_surface_distance_m']<=8. for f in frames) and all(0<g<=.15 for g in gaps) else 0
        report['passed']=bool(report['actual_consecutive_visible_frames']==5 and
            len(set(frame_ids))==5 and target_hit_count>0)
        logging.info('TARGET_CONFIRMATION_RESULT passed=%s visible=%s',report['passed'],
                     [f['metric']['visible_fraction'] for f in frames])
    finally:
        (output/'target-confirmation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not report['passed']:
        raise RuntimeError('Target confirmation incomplete; inspect actual ray and RGB evidence')
    return report
