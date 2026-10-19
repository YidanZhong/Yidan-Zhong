"""Bounded real Jackal wheel motion over ROS; diagnostic only, never a Nav2 score."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Any


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def create_robot(world: Any, stage: Any, asset: Path, air_stack: Path, spawn: list[float]) -> tuple[Any, Any, dict]:
    import numpy as np
    from pxr import UsdPhysics
    from isaacsim.robot.wheeled_robots.robots import WheeledRobot
    sim = air_stack / 'simulation/isaac-sim'
    sys.path.insert(0, str(sim / 'utils'))
    import scene_prep
    import ugv_traction_setup as traction
    from scene_physics_profile import DEFAULT_AIRGROUND_PHYSICS_PROFILE
    drive_path = sim / 'extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/vehicles/jackal_diff_drive.py'
    drive_module = load_module('raven_diagnostic_jackal_drive', drive_path)
    config = drive_module.JackalDriveConfig(wheel_velocity_scale=traction.UGV_WHEEL_VELOCITY_SCALE,
        angular_velocity_scale=traction.AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN,
        max_angular_radps=traction.AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS)
    # Keep the World-owned physics scene, without editing the source USD on disk.
    for prim in list(stage.Traverse()):
        if prim.IsA(UsdPhysics.Scene) and str(prim.GetPath()) != '/World/PhysicsScene':
            prim.SetActive(False)
    profile = replace(DEFAULT_AIRGROUND_PHYSICS_PROFILE, physics_hz=120)
    settings = {'physics_profile': scene_prep.configure_airground_physics_profile(stage, root_prim_path='/', profile=profile)}
    settings['support_plane'] = scene_prep.add_ground_support_plane(stage,
        contact_offset_m=traction.AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M,
        rest_offset_m=traction.AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M)
    robot = world.scene.add(WheeledRobot(prim_path='/World/ugv', name='ugv', create_robot=True,
        usd_path=str(asset), wheel_dof_names=list(config.wheel_joint_names),
        position=np.array(spawn[:3]), orientation=np.array([math.cos(spawn[3]/2),0.,0.,math.sin(spawn[3]/2)])))
    traction.ensure_articulation_root(stage, '/World/ugv', 'diagnostic Jackal')
    settings['contact'] = traction.apply_wheel_contact_offsets(stage, robot_prim_path='/World/ugv',
        contact_offset_m=traction.AIRGROUND_WHEEL_CONTACT_OFFSET_M,rest_offset_m=traction.AIRGROUND_WHEEL_REST_OFFSET_M)
    settings['solver'] = traction.apply_ugv_solver_iterations(stage, articulation_prim_path='/World/ugv',
        position_iterations=traction.AIRGROUND_UGV_SOLVER_POSITION_ITERATIONS,
        velocity_iterations=traction.AIRGROUND_UGV_SOLVER_VELOCITY_ITERATIONS)
    settings['traction'] = traction.apply_ugv_wheel_traction(stage, robot_prim_path='/World/ugv',
        material_paths=('/World/ugv/PhysicsMaterials/wheels','/World/PhysicsMaterials/airground_ground_contact'),
        static_friction=traction.AIRGROUND_UGV_WHEEL_STATIC_FRICTION,
        dynamic_friction=traction.AIRGROUND_UGV_WHEEL_DYNAMIC_FRICTION,
        friction_combine_mode=traction.AIRGROUND_UGV_WHEEL_FRICTION_COMBINE_MODE,
        max_torque_nm=traction.AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM)
    settings.update(asset_sha256=hashlib.sha256(asset.read_bytes()).hexdigest(), spawn=spawn,
                    drive=asdict(config), drive_source_sha256=hashlib.sha256(drive_path.read_bytes()).hexdigest(),
                    control='set_joint_velocities on four wheel DOFs; no body pose writes during motion')
    if any(settings[k].get('status') != 'ok' for k in ('contact','solver','traction')):
        raise RuntimeError('Jackal contact/solver/traction configuration incomplete')
    return robot, drive_module.JackalDiffDrive(config), settings


def run_motion(world: Any, robot: Any, drive: Any, camera: Any, output: Path, seconds: float, run_id: str) -> dict:
    import numpy as np
    import rclpy
    from builtin_interfaces.msg import Time
    from geometry_msgs.msg import TransformStamped, Twist
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String
    from tf2_msgs.msg import TFMessage
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from omni.isaac.dynamic_control import _dynamic_control
    from PIL import Image
    import omni.usd
    from pxr import UsdGeom, Gf

    dc = _dynamic_control.acquire_dynamic_control_interface()
    body = dc.get_rigid_body('/World/ugv/base_link')
    if not body or body == _dynamic_control.INVALID_HANDLE:
        raise RuntimeError('Real PhysX Jackal base body unavailable')
    indices = np.array([robot.get_dof_index(n) for n in drive.config.wheel_joint_names], dtype=np.int32)
    rclpy.init(args=[])
    node = rclpy.create_node('raven_jackal_motion_probe', namespace='/ugv')
    clock_pub = node.create_publisher(Clock, '/clock', 10)
    odom_pub = node.create_publisher(Odometry, '/ugv/odom', 10)
    tf_pub = node.create_publisher(TFMessage, '/tf', 10)
    static_pub = node.create_publisher(TFMessage, '/tf_static', QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    status_pub = node.create_publisher(String, '/ugv/diagnostic/motion_status', 10)
    fixed = TransformStamped()
    fixed.header.frame_id, fixed.child_frame_id = 'map', 'ugv/odom'
    fixed.transform.rotation.w = 1.
    static_pub.publish(TFMessage(transforms=[fixed]))
    report: dict = {'scope':'real_wheel_motion_diagnostic_only','nav2_verified':False,'run_id':run_id,
        'odometry_source':'PhysX base rigid-body state, not encoder odometry or localization',
        'tf_tree':['map -> ugv/odom (diagnostic identity)','ugv/odom -> ugv/base_link (PhysX)'],
        'samples':[],'commands':[],'images':[],'watchdog_count':0,'challenge_received':False}
    command = [0.,0.]
    last_command_wall, last_command_sim = -1e9, -1e9

    def on_command(msg: Twist) -> None:
        nonlocal last_command_wall, last_command_sim, command
        if not all(math.isfinite(v) for v in (msg.linear.x,msg.angular.z)):
            return
        command = [max(-.3,min(.3,msg.linear.x)), max(-.4,min(.4,msg.angular.z))]
        last_command_wall,last_command_sim = time.monotonic(),float(world.current_time)
        report['commands'].append({'sim_time_s':last_command_sim,'linear_x':command[0],'angular_z':command[1]})

    def on_challenge(msg: String) -> None:
        if msg.data == run_id:
            report['challenge_received'] = True

    node.create_subscription(Twist,'/ugv/cmd_vel',on_command,10)
    node.create_subscription(String,'/ugv/diagnostic/challenge',on_challenge,10)
    def stamp(value: float) -> Time:
        ns=round(value*1e9)
        return Time(sec=ns//10**9,nanosec=ns%10**9)

    def state() -> dict:
        pose=dc.get_rigid_body_pose(body)
        linear=dc.get_rigid_body_linear_velocity(body)
        angular=dc.get_rigid_body_angular_velocity(body)
        q=[float(v) for v in (pose.r.x,pose.r.y,pose.r.z,pose.r.w)]
        x,y,z,w=q
        return {'position':[float(v) for v in (pose.p.x,pose.p.y,pose.p.z)], 'quaternion_xyzw':q,
                'linear_world':[float(v) for v in linear], 'angular_world':[float(v) for v in angular],
                'yaw':math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)),
                'roll':math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),
                'pitch':math.asin(max(-1.,min(1.,2*(w*y-z*x))))}

    def status(phase: str, elapsed: float) -> None:
        status_pub.publish(String(data=json.dumps({'run_id':run_id,'phase':phase,'elapsed_sim_s':elapsed,
            'challenge_received':report['challenge_received'],'commands_received':len(report['commands'])})))

    started, motion_start = time.monotonic(), None
    step, last_published = 0, -1e9
    saved = set()
    try:
        while time.monotonic()-started < seconds:
            for _ in range(4):
                rclpy.spin_once(node,timeout_sec=0)
            now=float(world.current_time)
            if motion_start is None and report['challenge_received'] and report['commands']:
                motion_start=now
            elapsed=now-motion_start if motion_start is not None else -1.
            stale=(now-last_command_sim > .5 or time.monotonic()-last_command_wall > 1.)
            applied=[0.,0.] if stale or motion_start is None else command
            if stale and command != [0.,0.]:
                report['watchdog_count']+=1
            wheel=drive.wheel_velocities(*applied)
            robot.set_joint_velocities(np.array([wheel[n] for n in drive.config.wheel_joint_names]),joint_indices=indices)
            world.step(render=(step%8==0))
            step+=1
            now=float(world.current_time)
            elapsed=now-motion_start if motion_start is not None else -1.
            current=state()
            if abs(current['roll']) > .5 or abs(current['pitch']) > .5 or current['position'][2] < -.1:
                raise RuntimeError('Jackal tilt/ground safety bound exceeded')
            if now-last_published >= .05 or elapsed >= 19.:
                sample={'sim_time_s':now,'elapsed_sim_s':elapsed,'applied_command':applied[:],
                        'stale_command':stale,**current,
                        'wheel_radps':[float(v) for v in robot.get_joint_velocities()[indices]]}
                report['samples'].append(sample)
                t=stamp(now)
                clock_pub.publish(Clock(clock=t))
                odom=Odometry()
                odom.header.stamp,odom.header.frame_id,odom.child_frame_id=t,'ugv/odom','ugv/base_link'
                p=current['position'];q=current['quaternion_xyzw']
                odom.pose.pose.position.x,odom.pose.pose.position.y,odom.pose.pose.position.z=p
                odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z,odom.pose.pose.orientation.w=q
                yaw=current['yaw'];vx,vy,vz=current['linear_world']
                odom.twist.twist.linear.x=math.cos(yaw)*vx+math.sin(yaw)*vy
                odom.twist.twist.linear.y=-math.sin(yaw)*vx+math.cos(yaw)*vy
                odom.twist.twist.angular.z=current['angular_world'][2]
                odom_pub.publish(odom)
                tf=TransformStamped();tf.header=odom.header;tf.child_frame_id=odom.child_frame_id
                tf.transform.translation.x,tf.transform.translation.y,tf.transform.translation.z=p
                tf.transform.rotation=odom.pose.pose.orientation
                tf_pub.publish(TFMessage(transforms=[tf]))
                status('running',elapsed)
                last_published=now
            for name, at in [('start',.3),('forward',4.8),('turn',10.8),('stopped',18.)]:
                if elapsed >= at and name not in saved:
                    p=current['position']
                    cam=UsdGeom.Xformable(omni.usd.get_context().get_stage().GetPrimAtPath(camera.prim_path))
                    cam.ClearXformOpOrder()
                    cam.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(p[0]-1.8,p[1]+2,p[2]+1.2),Gf.Vec3d(p[0],p[1],p[2]+.1),Gf.Vec3d(0,0,1)).GetInverse())
                    # Render without advancing physics, so screenshots cannot add uncommanded travel.
                    for _ in range(12):
                        world.render()
                    rgb=np.asarray(camera.get_rgba())[...,:3].astype(np.uint8)
                    if rgb.ndim!=3 or rgb.std()<1:
                        raise RuntimeError('Motion screenshot unavailable')
                    path=output/f'jackal-{name}.png';Image.fromarray(rgb).save(path)
                    report['images'].append({'file':path.name,'elapsed_sim_s':elapsed,'position':p})
                    saved.add(name)
            if elapsed >= 19.:
                break
            time.sleep(.002)
        samples=report['samples']
        def nearest(t: float) -> dict:
            return min(samples,key=lambda s:abs(s['elapsed_sim_s']-t))
        a,b=nearest(1.),nearest(5.)
        forward=math.hypot(b['position'][0]-a['position'][0],b['position'][1]-a['position'][1])
        a,b=nearest(7.),nearest(11.)
        turn=math.atan2(math.sin(b['yaw']-a['yaw']),math.cos(b['yaw']-a['yaw']))
        stopped=[s for s in samples if 6<=s['elapsed_sim_s']<=6.8 or 12<=s['elapsed_sim_s']<=12.8 or s['elapsed_sim_s']>=18]
        stop_speed=max(math.hypot(*s['linear_world'][:2]) for s in stopped) if stopped else float('inf')
        watchdog=[s for s in samples if 16<=s['elapsed_sim_s']<=16.8]
        watchdog_stopped=bool(watchdog) and all(s['stale_command'] and s['applied_command']==[0.,0.] and math.hypot(*s['linear_world'][:2])<.04 for s in watchdog)
        report['metrics']={'forward_distance_m':forward,'turn_angle_rad':turn,'max_stopped_speed_mps':stop_speed,
                           'watchdog_stopped':watchdog_stopped,'elapsed_sim_s':samples[-1]['elapsed_sim_s'],
                           'max_abs_roll_rad':max(abs(s['roll']) for s in samples)}
        report['passed']=bool(.6<forward<1.4 and .4<turn<2.5 and stop_speed<.04 and watchdog_stopped and samples[-1]['elapsed_sim_s']>=19)
        status('finished',samples[-1]['elapsed_sim_s'])
        for _ in range(10):
            rclpy.spin_once(node,timeout_sec=.05)
        logging.info('JACKAL_MOTION_RESULT %s',report['metrics'])
    finally:
        robot.set_joint_velocities(np.zeros(4),joint_indices=indices)
        report['wall_seconds']=time.monotonic()-started
        (output/'jackal-motion.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        node.destroy_node();rclpy.shutdown()
    if not report.get('passed'):
        raise RuntimeError('Jackal motion thresholds not met; inspect actual trace')
    return report
