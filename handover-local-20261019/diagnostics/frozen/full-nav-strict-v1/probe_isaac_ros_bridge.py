"""Real Isaac-to-ROS transport diagnostic; never actuates a robot or scores episodes."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any


def run_probe(world: Any, camera: Any, output: Path, seconds: float, run_id: str) -> dict:
    import numpy as np
    import rclpy
    from builtin_interfaces.msg import Time
    from geometry_msgs.msg import Twist
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import CameraInfo, Image
    from std_msgs.msg import String

    rclpy.init(args=[])
    node = rclpy.create_node('raven_isaac_transport_probe', namespace='/ugv')
    clock_pub = node.create_publisher(Clock, '/clock', 10)
    image_pub = node.create_publisher(Image, '/ugv/diagnostic_camera/rgb', 5)
    info_pub = node.create_publisher(CameraInfo, '/ugv/diagnostic_camera/camera_info', 5)
    ack_pub = node.create_publisher(String, '/ugv/diagnostic/ack', 10)
    report: dict = {'scope': 'actual_camera_clock_and_command_transport_only',
                    'robot_actuated': False, 'benchmark_accepted': False, 'run_id': run_id,
                    'clock_count': 0, 'commands': [], 'frames': [], 'challenge_received': False,
                    'rclpy_file': rclpy.__file__}

    def on_command(message: Twist) -> None:
        report['commands'].append({'linear_x': message.linear.x, 'angular_z': message.angular.z,
                                   'sim_time_s': float(world.current_time)})

    def on_challenge(message: String) -> None:
        if message.data == run_id:
            report['challenge_received'] = True

    node.create_subscription(Twist, '/ugv/cmd_vel', on_command, 10)
    node.create_subscription(String, '/ugv/diagnostic/challenge', on_challenge, 10)

    def stamp(value: float) -> Time:
        ns = round(value * 1_000_000_000)
        return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)

    def acknowledge(phase: str) -> None:
        ack_pub.publish(String(data=json.dumps({
            'run_id': run_id, 'phase': phase, 'challenge_received': report['challenge_received'],
            'commands_received': len(report['commands']), 'robot_actuated': False,
            'last_command': report['commands'][-1] if report['commands'] else None})))

    started = time.monotonic()
    last_image = last_ack = 0.0
    last_sensor_frame = -1
    report['start_sim_time_s'] = float(world.current_time)
    try:
        while time.monotonic() - started < seconds:
            world.step(render=True)
            rclpy.spin_once(node, timeout_sec=0)
            clock_pub.publish(Clock(clock=stamp(float(world.current_time))))
            report['clock_count'] += 1
            now = time.monotonic()
            sensor = camera.get_current_frame()
            sensor_frame = int(sensor.get('rendering_frame', -1))
            if now - last_image >= .2 and sensor_frame > last_sensor_frame:
                rgba = np.asarray(camera.get_rgba())
                if rgba.ndim == 3 and rgba.shape[2] == 4:
                    rgb = rgba[..., :3].astype(np.uint8)
                    if float(np.mean(np.max(rgb, axis=2) > 8)) >= .05:
                        sensor_time = float(sensor.get('rendering_time', world.current_time))
                        msg = Image()
                        msg.header.stamp = stamp(sensor_time)
                        msg.header.frame_id = 'raven_diagnostic_camera_optical'
                        msg.height, msg.width = rgb.shape[:2]
                        msg.encoding, msg.is_bigendian = 'rgb8', 0
                        msg.step = msg.width * 3
                        raw = rgb.tobytes()
                        msg.data = raw
                        image_pub.publish(msg)
                        info = CameraInfo()
                        info.header, info.width, info.height = msg.header, msg.width, msg.height
                        info.distortion_model = 'plumb_bob'
                        info.d = [0.] * 5
                        info.k = camera.get_intrinsics_matrix().reshape(-1).tolist()
                        info.r = np.eye(3).reshape(-1).tolist()
                        info.p = np.column_stack((np.asarray(info.k).reshape(3, 3), np.zeros(3))).reshape(-1).tolist()
                        info_pub.publish(info)
                        report['frames'].append({'stamp_ns': msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec,
                                                 'sensor_frame': sensor_frame, 'width': msg.width,
                                                 'height': msg.height, 'sha256_rgb': hashlib.sha256(raw).hexdigest()})
                        last_sensor_frame, last_image = sensor_frame, now
            if now - last_ack >= .5:
                acknowledge('running')
                last_ack = now
            time.sleep(.025)
        report['end_sim_time_s'] = float(world.current_time)
        kinds = {(round(c['linear_x'], 3), round(c['angular_z'], 3)) for c in report['commands']}
        report['passed'] = (report['challenge_received'] and report['clock_count'] >= 30
                            and len(report['frames']) >= 10
                            and {(0., 0.), (.1, 0.), (0., .05)} <= kinds
                            and report['commands'][-1]['linear_x'] == 0
                            and report['commands'][-1]['angular_z'] == 0)
        for _ in range(10):
            acknowledge('finished')
            rclpy.spin_once(node, timeout_sec=.05)
        logging.info('ROS_BRIDGE_PROBE: passed=%s images=%s commands=%s',
                     report['passed'], len(report['frames']), len(report['commands']))
    finally:
        report['wall_seconds'] = time.monotonic() - started
        (output / 'ros-bridge.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        node.destroy_node()
        rclpy.shutdown()
    if not report.get('passed'):
        raise RuntimeError('ROS bridge did not meet bidirectional transport checks; inspect ros-bridge.json')
    return report
