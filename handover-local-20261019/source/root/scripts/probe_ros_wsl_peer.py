"""Bounded real ROS Humble peer for the Isaac transport probe; no navigation claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import struct
import time
import zlib


def save_rgb_png(path: Path, width: int, height: int, raw: bytes) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    scanlines = b''.join(b'\0' + raw[y * width * 3:(y + 1) * width * 3] for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--timeout', type=float, default=650)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    import rclpy
    from geometry_msgs.msg import Twist
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import CameraInfo, Image
    from std_msgs.msg import String

    rclpy.init(args=[])
    node = rclpy.create_node('raven_wsl_transport_probe', namespace='/ugv')
    commands = node.create_publisher(Twist, '/ugv/cmd_vel', 10)
    challenges = node.create_publisher(String, '/ugv/diagnostic/challenge', 10)
    report: dict = {'scope': 'transport_only_no_robot_actuation', 'run_id': args.run_id,
                    'clock_ns': [], 'images': [], 'camera_info': [], 'acks': [],
                    'commands_sent': [], 'rclpy_file': rclpy.__file__}
    first_clock_wall = None

    def on_clock(message: Clock) -> None:
        nonlocal first_clock_wall
        if first_clock_wall is None:
            first_clock_wall = time.monotonic()
            logging.info('FIRST_REAL_SIM_CLOCK')
        report['clock_ns'].append(message.clock.sec * 10**9 + message.clock.nanosec)

    def on_image(message: Image) -> None:
        raw = bytes(message.data)
        if message.encoding != 'rgb8' or len(raw) != message.width * message.height * 3:
            raise RuntimeError('Unexpected camera encoding or dimensions')
        entry = {'stamp_ns': message.header.stamp.sec * 10**9 + message.header.stamp.nanosec,
                 'width': message.width, 'height': message.height, 'frame_id': message.header.frame_id,
                 'sha256_rgb': hashlib.sha256(raw).hexdigest()}
        report['images'].append(entry)
        if len(report['images']) == 1:
            save_rgb_png(args.output / 'received-camera.png', message.width, message.height, raw)
            logging.info('FIRST_REAL_CAMERA_IMAGE %sx%s', message.width, message.height)

    def on_info(message: CameraInfo) -> None:
        report['camera_info'].append({'stamp_ns': message.header.stamp.sec * 10**9 + message.header.stamp.nanosec,
                                      'width': message.width, 'height': message.height, 'k': list(message.k)})

    def on_ack(message: String) -> None:
        ack = json.loads(message.data)
        if ack.get('run_id') == args.run_id:
            report['acks'].append(ack)

    node.create_subscription(Clock, '/clock', on_clock, 10)
    node.create_subscription(Image, '/ugv/diagnostic_camera/rgb', on_image, 5)
    node.create_subscription(CameraInfo, '/ugv/diagnostic_camera/camera_info', on_info, 5)
    node.create_subscription(String, '/ugv/diagnostic/ack', on_ack, 10)
    (args.output / 'ready.json').write_text(json.dumps({'run_id': args.run_id, 'ready': True}))
    started, last_publish = time.monotonic(), 0.
    try:
        while time.monotonic() - started < args.timeout:
            rclpy.spin_once(node, timeout_sec=.05)
            now = time.monotonic()
            if now - last_publish >= .2:
                elapsed = now - first_clock_wall if first_clock_wall is not None else -1
                msg = Twist()
                if 2 <= elapsed < 6:
                    msg.linear.x = .1
                elif 6 <= elapsed < 10:
                    msg.angular.z = .05
                commands.publish(msg)
                challenges.publish(String(data=args.run_id))
                report['commands_sent'].append([msg.linear.x, msg.angular.z])
                last_publish = now
            if report['acks'] and report['acks'][-1]['phase'] == 'finished':
                break
            if first_clock_wall is not None and now - first_clock_wall > 90:
                break
        clocks = report['clock_ns']
        report['clock_monotonic'] = all(b >= a for a, b in zip(clocks, clocks[1:]))
        report['clock_publisher_count'] = node.count_publishers('/clock')
        report['topic_types'] = node.get_topic_names_and_types()
        report['passed'] = (len(clocks) >= 30 and report['clock_monotonic'] and clocks[-1] > clocks[0]
                            and len(report['images']) >= 10 and len(report['camera_info']) >= 10
                            and any(a.get('challenge_received') and a.get('commands_received', 0) >= 10 for a in report['acks'])
                            and report['acks'][-1]['phase'] == 'finished')
    except Exception as error:
        report['passed'], report['error'] = False, str(error)
        logging.exception('WSL peer failed')
    finally:
        for _ in range(5):
            commands.publish(Twist())
            rclpy.spin_once(node, timeout_sec=.05)
        report['wall_seconds'] = time.monotonic() - started
        (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        node.destroy_node()
        rclpy.shutdown()
    logging.info('WSL_PEER passed=%s clocks=%s images=%s', report.get('passed'), len(report['clock_ns']), len(report['images']))
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
