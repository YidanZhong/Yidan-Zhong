"""Render real Isaac images with one camera; diagnostic only, no benchmark score."""
from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import logging
import os
from pathlib import Path
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--graphics-api', choices=('vulkan', 'd3d12'), default='vulkan')
    parser.add_argument('--cpu-threads', type=int, default=4)
    parser.add_argument('--shader-concurrency', type=int, default=1)
    parser.add_argument('--defer-stage', action='store_true',
                        help='Create the stage explicitly after SimulationApp initialization')
    parser.add_argument('--first-frame-timeout', type=float, default=240)
    parser.add_argument('--gui', action='store_true', help='Show the real Isaac application window')
    parser.add_argument('--renderer', choices=('RayTracedLighting', 'PathTracing'),
                        default='RayTracedLighting')
    parser.add_argument('--async-loads', action='store_true', help='Diagnostic asynchronous asset loading')
    parser.add_argument('--disable-motion-bvh', action='store_true',
                        help='Camera-only diagnostic; do not use for RTX lidar/radar acceptance')
    parser.add_argument('--camera-size', nargs=2, type=int, default=(480, 300), metavar=('WIDTH', 'HEIGHT'))
    parser.add_argument('--settle-frames', type=int, default=60,
                        help='Additional render updates after the first useful sensor buffer')
    parser.add_argument('--physics-only', action='store_true',
                        help='Check real PhysX scene queries only; does not validate rendering')
    parser.add_argument('--ray-origin', nargs=3, type=float, action='append')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ros2-seconds', type=float, default=0,
                        help='Optional bounded ROS transport diagnostic after rendering')
    parser.add_argument('--ros2-run-id', default='')
    parser.add_argument('--jackal-usd', type=Path)
    parser.add_argument('--air-stack-root', type=Path)
    parser.add_argument('--jackal-spawn', nargs=4, type=float, metavar=('X','Y','Z','YAW'))
    parser.add_argument('--drive-audit', choices=('direct','actions'),
                        help='Bounded physics-only drivetrain comparison; no ROS navigation claim')
    parser.add_argument('--nav2-goal', nargs=2, type=float, action='append', metavar=('X','Y'),
                        help='Optional real Nav2 diagnostic goal; requires a separate WSL Nav2 runner')
    parser.add_argument('--nav2-require-detour', action='store_true',
                        help='Require a blocked direct leg and obstacle-clear actual trajectory')
    parser.add_argument('--nav2-full-map',type=Path,help='Checksum-pinned private diagnostic full-map manifest')
    parser.add_argument('--target-confirmation', type=Path,
                        help='Optional unreviewed target diagnostic after a real Nav2 arrival')
    parser.add_argument('--benchmark-package', type=Path)
    parser.add_argument('--review-manifest', type=Path,
                        help='Static target-review camera poses; never approves target annotations')
    parser.add_argument('--tile-validation', type=Path,
                        help='Bounded native PhysX whole-window versus tiled terrain diagnostic')
    args, _ = parser.parse_known_args()
    if args.cpu_threads < 1 or args.shader_concurrency < 1 or args.first_frame_timeout <= 0:
        parser.error('Thread counts and first-frame timeout must be positive')
    if args.physics_only and args.scene and not args.ray_origin and not args.tile_validation:
        parser.error('Scene physics diagnostics require explicit --ray-origin x y z')
    if args.tile_validation and (not args.physics_only or not args.scene or not args.air_stack_root
                                or not args.benchmark_package or args.ros2_seconds or args.review_manifest):
        parser.error('Tile validation requires physics-only, scene and source paths, without ROS or review cameras')
    if not (64 <= args.camera_size[0] <= 1280 and 64 <= args.camera_size[1] <= 960):
        parser.error('Diagnostic camera size must be within 64x64 and 1280x960')
    if not 0 <= args.settle_frames <= 600:
        parser.error('Settling frames must be between 0 and 600')
    if not 0 <= args.ros2_seconds <= (600 if args.nav2_goal else 120) or (args.ros2_seconds and not args.ros2_run_id):
        parser.error('ROS diagnostic requires a run ID; maximum wall duration is 120 s (Nav2: 600 s)')
    if args.nav2_goal and not args.jackal_usd:
        parser.error('Nav2 requires the real Jackal asset and motion options')
    if args.drive_audit and (not args.physics_only or not args.jackal_usd or args.nav2_goal):
        parser.error('Drivetrain audit requires physics-only Jackal and no Nav2 goals')
    if args.target_confirmation and (not args.nav2_goal or not args.benchmark_package):
        parser.error('Target confirmation requires Nav2 and the benchmark package path')
    if args.review_manifest and (not args.scene or args.ros2_seconds or args.physics_only):
        parser.error('Static target review requires a scene and no ROS or physics-only operation')
    if args.jackal_usd and (not args.air_stack_root or not args.jackal_spawn or (not args.ros2_seconds and not args.drive_audit)):
        parser.error('Jackal motion requires source root, explicit spawn, and ROS diagnostic options')
    args.output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    report = {'scope': 'physics_scene_query_diagnostic_only' if args.physics_only
                      else 'render_and_physics_diagnostic_only', 'benchmark_accepted': False,
              'scene': str(args.scene) if args.scene else 'diagnostic_cube', 'frames': [],
              'graphics_api_requested': args.graphics_api,
              'cpu_threads': args.cpu_threads, 'shader_concurrency': args.shader_concurrency,
              'defer_stage': args.defer_stage,
              'gui': args.gui,
              'renderer': args.renderer, 'sync_loads': not args.async_loads,
              'disable_motion_bvh': args.disable_motion_bvh,
              'camera_size': args.camera_size,
              'settle_frames': args.settle_frames, 'minimum_nonblack_fraction': .05,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'vulkan_driver_filter': os.environ.get('VK_LOADER_DRIVERS_SELECT')}
    started = time.monotonic()
    application = None
    capture = None
    preview_window = None
    stack_log = (args.output / 'python-stacks.log').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(60, repeat=True, file=stack_log)

    def save_phase(phase: str) -> None:
        report['phase'] = phase
        report['elapsed_s'] = time.monotonic() - started
        (args.output / 'progress.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if capture and phase in ('stage_loaded', 'camera_initialized', 'waiting_for_camera_frame'):
            capture.capture_next_frame_swapchain(str(args.output / f'ui-{phase}.png'))

    try:
        save_phase('starting_application')
        from isaacsim import SimulationApp
        application = SimulationApp({'headless': not args.gui, 'hide_ui': not args.gui,
            'renderer': args.renderer, 'anti_aliasing': 0, 'multi_gpu': False,
            'sync_loads': not args.async_loads, 'width': 640, 'height': 480,
            'window_width': 1280, 'window_height': 800,
            'create_new_stage': not args.defer_stage,
            'extra_args': [f'--/app/vulkan={str(args.graphics_api == "vulkan").lower()}',
                f'--/plugins/carb.tasking.plugin/threadCount={args.cpu_threads}',
                f'--/plugins/omni.tbb.globalcontrol/maxThreadCount={args.cpu_threads}',
                '--/persistent/physics/numThreads=2',
                f'--/gpu/shadercompiler/warmcountMax={args.shader_concurrency}',
                f'--/gpu/shadercompiler/warmcount={args.shader_concurrency}',
                f'--/rtx/shaderDb/concurrency={args.shader_concurrency}'] +
                (['--/renderer/raytracingMotion/enabled=false'] if args.disable_motion_bvh else [])})
        logging.info('ISAAC_APP_STARTED')
        save_phase('application_started')
        import carb
        report['isaac_app_version'] = carb.settings.get_settings().get('/app/version')
        report['motion_bvh_effective'] = carb.settings.get_settings().get('/renderer/raytracingMotion/enabled')
        import numpy as np
        import omni.usd
        from pxr import Gf, UsdGeom, UsdLux
        from isaacsim.core.api import World
        from isaacsim.core.utils.extensions import enable_extension
        if args.ros2_seconds:
            enable_extension('isaacsim.ros2.bridge')
            for _ in range(10):
                application.update()
            report['ros2_bridge_enabled'] = omni.kit.app.get_app().get_extension_manager().is_extension_enabled('isaacsim.ros2.bridge')
            if not report['ros2_bridge_enabled']:
                raise RuntimeError('Native ROS 2 bridge failed to enable')
        if args.gui:
            enable_extension('omni.kit.renderer.capture')
            import omni.kit.renderer.capture
            capture = omni.kit.renderer.capture.acquire_renderer_capture_interface()
            capture.capture_next_frame_swapchain(str(args.output / 'ui-startup.png'))
        enable_extension('isaacsim.sensors.camera')
        from isaacsim.sensors.camera import Camera
        from PIL import Image

        if args.scene:
            scene = args.scene.resolve(strict=True)
            report['scene_sha256'] = hashlib.sha256(scene.read_bytes()).hexdigest()
            if not omni.usd.get_context().open_stage(str(scene)):
                raise RuntimeError('USD stage open failed')
            while omni.usd.get_context().get_stage_loading_status()[2] > 0:
                application.update()
            views = [((-33., -21.5, 1.2), (-20., -21.5, 1.2)),
                     ((-10., -40., 45.), (-10., 10., 0.))]
        else:
            if args.defer_stage:
                omni.usd.get_context().new_stage()
            views = [((3., -3., 2.), (0., 0., 0.5))]
        stage = omni.usd.get_context().get_stage()
        review_views = []
        if args.review_manifest:
            from pxr import Usd
            review = json.loads(args.review_manifest.read_text(encoding='utf-8-sig'))
            if review['scene_sha256'] != report['scene_sha256']:
                raise RuntimeError('Review manifest scene hash does not match loaded stage')
            bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default','render'])
            report['review_manifest_sha256'] = hashlib.sha256(args.review_manifest.read_bytes()).hexdigest()
            report['review_status'] = 'pending_human_review'
            report['review_targets'] = []
            views = []
            for row in review['rows']:
                instance = row['target']
                if instance['verified'] or instance['ground_reachable'] != 'unknown':
                    raise RuntimeError('Review packet expects unreviewed input')
                path=instance.get('usd_prim_path')
                observed={'instance_id':instance['instance_id'],'usd_prim_path':path,
                    'binding_status':'unbound','actual_candidate_center_xyz_m':None,
                    'actual_candidate_size_xyz_m':None}
                if path:
                    prim = stage.GetPrimAtPath(path)
                    if not prim.IsValid():
                        raise RuntimeError(f'Missing review candidate prim: {instance["instance_id"]}')
                    box = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
                    observed.update(binding_status='candidate_pending_review',
                        actual_candidate_center_xyz_m=list(box.GetMidpoint()),
                        actual_candidate_size_xyz_m=list(box.GetSize()))
                report['review_targets'].append(observed)
                for view_index, view in enumerate(row['views']):
                    views.append((view['eye'],view['look_at']))
                    review_views.append({'instance_id':instance['instance_id'],'view_index':view_index,
                        'target_index':len(report['review_targets'])-1})
            if not views:
                raise RuntimeError('Review manifest contains no camera views')
        report['stage_prims'] = sum(1 for _ in stage.Traverse())
        logging.info('STAGE_LOADED: %s prims', report['stage_prims'])
        save_phase('stage_loaded')
        dt = 1/250 if args.tile_validation else 1/120 if args.jackal_usd else 1/60
        world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=dt,
                      physics_prim_path='/World/PhysicsScene')
        robot = drive = None
        if args.jackal_usd:
            enable_extension('isaacsim.robot.wheeled_robots')
            from probe_jackal_motion import create_robot
            robot, drive, report['jackal_setup'] = create_robot(world, stage,
                args.jackal_usd.resolve(strict=True), args.air_stack_root.resolve(strict=True), args.jackal_spawn)
        cube = None
        if not args.scene:
            from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
            world.scene.add(FixedCuboid(prim_path='/World/DiagnosticGround', name='ground',
                position=np.array([0., 0., -.05]), scale=np.array([20., 20., .1]),
                color=np.array([.35, .35, .35])))
            cube = world.scene.add(DynamicCuboid(prim_path='/World/DiagnosticCube', name='cube',
                position=np.array([0., 0., 1.5]), scale=np.array([.5, .5, .5]),
                color=np.array([.8, .15, .1])))
            light = UsdLux.DomeLight.Define(stage, '/World/DiagnosticLight')
            light.CreateIntensityAttr(1000)
        if args.physics_only:
            if args.tile_validation:
                from probe_tiled_terrain import run_validation
                tile_input = json.loads(args.tile_validation.read_text(encoding='utf-8-sig'))
                if tile_input['scene_sha256'] != report['scene_sha256']:
                    raise RuntimeError('Tile validation scene checksum mismatch')
                report['tile_validation'] = run_validation(world, stage, args.output,
                    args.tile_validation, args.air_stack_root, args.benchmark_package)
                report['rendering_verified'] = False
                report['physics_passed'] = True
                report['status'] = 'passed'
                save_phase('tile_validation_complete')
                return 0
            import omni.physx
            world.reset()
            save_phase('physics_reset')
            for _ in range(90):
                world.step(render=False)
            if args.drive_audit:
                from probe_jackal_drive_audit import run_audit
                report['drive_audit']=run_audit(world,robot,drive,args.output,args.drive_audit)
                report['rendering_verified']=False
                report['physics_passed']=True
                report['status']='passed'
                save_phase('drive_audit_complete')
                return 0
            query = omni.physx.get_physx_scene_query_interface()
            rays = []
            for origin in args.ray_origin or [(2., 2., 8.)]:
                hit = query.raycast_closest(tuple(origin), (0., 0., -1.), 10.)
                ray = {'origin': origin, 'hit': bool(hit['hit'])}
                if ray['hit']:
                    ray.update(distance=float(hit['distance']),
                               position=[float(v) for v in hit['position']],
                               normal=[float(v) for v in hit['normal']],
                               collision=str(hit['collision']))
                rays.append(ray)
            report['physx_rays'] = rays
            report['sim_time_s'] = float(world.current_time)
            report['rendering_verified'] = False
            if not any(ray['hit'] for ray in rays):
                raise RuntimeError('No real PhysX ray hit was returned')
            report['physics_passed'] = True
            report['status'] = 'passed'
            save_phase('physics_queries_complete')
            return 0
        camera_path = '/World/RavenDiagnosticCamera'
        usd_camera = UsdGeom.Camera.Define(stage, camera_path)
        usd_camera.CreateFocalLengthAttr(18.)
        usd_camera.CreateClippingRangeAttr(Gf.Vec2f(.05, 1000.))
        camera = Camera(prim_path=camera_path, name='diagnostic_camera', resolution=tuple(args.camera_size))
        world.reset()
        save_phase('physics_reset')
        camera.initialize()
        save_phase('camera_initialized')
        if args.gui:
            from omni.kit.viewport.utility import get_active_viewport
            viewport = get_active_viewport()
            if viewport:
                viewport.camera_path = camera_path
        if cube:
            report['cube_initial_z'] = float(cube.get_world_pose()[0][2])
        for index, (eye, target) in enumerate(views):
            transform = UsdGeom.Xformable(usd_camera)
            transform.ClearXformOpOrder()
            transform.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(
                Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse())
            save_phase('render_warmup_started')
            for step in range(90):
                world.step(render=True)
                if step % 15 == 0:
                    report['warmup_step'] = step
                    save_phase('render_warmup')
            if cube:
                report['cube_final_z'] = float(cube.get_world_pose()[0][2])
                report['physics_passed'] = .15 < report['cube_final_z'] < .4
                save_phase('waiting_for_camera_frame')
            rgba = np.asarray(camera.get_rgba())
            deadline = time.monotonic() + args.first_frame_timeout
            expected_shape = (args.camera_size[1], args.camera_size[0], 4)

            def useful_frame(buffer: np.ndarray) -> bool:
                return (buffer.shape == expected_shape
                        and float(np.mean(np.max(buffer[..., :3], axis=2) > 8)) >= .05
                        and float(buffer[..., :3].std()) >= 1.)

            consecutive_valid, invalid_after_first = 0, 0
            saw_valid = useful_frame(rgba)
            required_valid = max(1, args.settle_frames)
            while consecutive_valid < required_valid and time.monotonic() < deadline:
                world.step(render=True)
                # Async loading may temporarily invalidate a buffer after its first
                # useful frame. Require a consecutive stable window, within the
                # original deadline, rather than accepting a transient first frame.
                time.sleep(.02)
                rgba = np.asarray(camera.get_rgba())
                if useful_frame(rgba):
                    consecutive_valid += 1
                    saw_valid = True
                else:
                    invalid_after_first += int(saw_valid)
                    consecutive_valid = 0
            if consecutive_valid < required_valid:
                raise RuntimeError(f'Camera stable-frame deadline exceeded; output shape: {rgba.shape}')
            rgb = rgba[..., :3].astype(np.uint8)
            path = args.output / f'view-{index}.png'
            Image.fromarray(rgb).save(path)
            frame = {'file': path.name, 'eye': eye, 'target': target,
                     'mean': float(rgb.mean()), 'std': float(rgb.std()),
                     'nonblack_fraction': float(np.mean(np.max(rgb, axis=2) > 8)),
                     'rendering_frame': int(camera.get_current_frame().get('rendering_frame', 0)),
                     'consecutive_valid_frames': consecutive_valid,
                     'invalid_frames_after_first': invalid_after_first,
                     'sim_time_s': float(world.current_time)}
            if review_views:
                frame.update(review_views[index])
                frame['camera_intrinsics'] = {'focal_length':usd_camera.GetFocalLengthAttr().Get(),
                    'horizontal_aperture':usd_camera.GetHorizontalApertureAttr().Get(),
                    'vertical_aperture':usd_camera.GetVerticalApertureAttr().Get(),
                    'resolution':list(args.camera_size)}
            report['frames'].append(frame)
            logging.info('FRAME_SAVED: %s', frame)
            if capture and (not review_views or index in (0,len(views)-1)):
                import omni.ui as ui
                if preview_window:
                    preview_window.visible = False
                preview_window = ui.Window('RAVEN | Actual camera RGB diagnostic', width=1000, height=700)
                preview_window.position_x = 100
                preview_window.position_y = 40
                with preview_window.frame:
                    with ui.VStack(spacing=8):
                        ui.Label(f'Isaac Sim 4.5.0 | {args.scene.name if args.scene else "Physics cube"} | {args.graphics_api}', height=24)
                        ui.Label(f'Actual RGB sensor frame {frame["rendering_frame"]} | sim time {frame["sim_time_s"]:.3f} s | not a navigation benchmark', height=24)
                        ui.Image(str(path), width=args.camera_size[0], height=args.camera_size[1])
                for _ in range(10):
                    application.update()
                    time.sleep(.02)
                capture.capture_next_frame_swapchain(str(args.output / f'ui-camera-preview-{index}.png'))
                for _ in range(10):
                    application.update()
                    time.sleep(.02)
            if frame['std'] < 1.0:
                raise RuntimeError('Rendered image has insufficient variation; inspect output')
        if cube:
            report['cube_final_z'] = float(cube.get_world_pose()[0][2])
            if not .15 < report['cube_final_z'] < .4:
                raise RuntimeError('Physics cube did not settle on the ground')
        if args.ros2_seconds:
            save_phase('ros2_transport_started')
            if args.nav2_goal:
                if args.nav2_full_map and json.loads(args.nav2_full_map.read_text())['scene_sha256']!=report['scene_sha256']:
                    raise RuntimeError('Full-map scene hash differs from runtime')
                from probe_jackal_nav2 import run_navigation
                report['jackal_nav2'] = run_navigation(world, robot, drive, camera, args.output,
                    args.ros2_seconds, args.ros2_run_id, args.nav2_goal, args.nav2_require_detour,args.nav2_full_map)
                if args.target_confirmation:
                    from probe_target_confirmation import run_confirmation
                    report['target_confirmation'] = run_confirmation(world,camera,args.output,
                        args.target_confirmation,args.benchmark_package)
            elif robot is not None:
                from probe_jackal_motion import run_motion
                report['jackal_motion'] = run_motion(world, robot, drive, camera, args.output, args.ros2_seconds, args.ros2_run_id)
            else:
                from probe_isaac_ros_bridge import run_probe
                report['ros2'] = run_probe(world, camera, args.output, args.ros2_seconds, args.ros2_run_id)
        report['status'] = 'passed'
        save_phase('frames_complete')
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        logging.exception('Diagnostic failed')
    finally:
        report['elapsed_s'] = time.monotonic() - started
        (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if application:
            application.close(wait_for_replicator=False)
        faulthandler.cancel_dump_traceback_later()
        stack_log.close()
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
