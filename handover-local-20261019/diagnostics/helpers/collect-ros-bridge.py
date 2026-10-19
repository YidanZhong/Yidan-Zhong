import hashlib
import json
from pathlib import Path

root = Path(r'D:\xprogram\RAVEN-AirGround-github')
run = root / 'runs/ros_bridge_20261018'
job = 'ros-bridge-a01'
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
execution = read(run / job / 'execution.json')
isaac = read(run / (job + '-frames') / 'report.json')
bridge = read(run / (job + '-frames') / 'ros-bridge.json')
peer = read(run / (job + '-wsl') / 'report.json')
samples = [json.loads(line) for line in (run / job / 'resources.jsonl').read_text().splitlines() if line.strip()]
sent = {f['stamp_ns']: f for f in bridge['frames']}
matches = [f for f in peer['images'] if f['stamp_ns'] in sent and f['sha256_rgb'] == sent[f['stamp_ns']]['sha256_rgb']]
info_stamps = {f['stamp_ns'] for f in peer['camera_info'] if len(f['k']) == 9 and f['k'][0] > 0 and f['k'][4] > 0}
passed = (execution.get('exit_code') == 0 and isaac.get('status') == 'passed' and bridge.get('passed')
          and peer.get('passed') and len(matches) == len(peer['images']) and len(matches) >= 10
          and sum(f['stamp_ns'] in info_stamps for f in matches) >= 10 and peer['clock_publisher_count'] == 1)
data = {'task': 'Local-Scene1-Reproduction / Windows-WSL-ROS-Bridge', 'date': '2026-10-18',
        'scope': 'Actual Isaac 4.5 Retro camera + simulation clock + ROS command reception, no robot actuation',
        'passed': bool(passed), 'scene1_reproduced': False, 'robot_motion_verified': False,
        'nav2_verified': False, 'real_episode_count': 0,
        'hardware': 'Second PC RTX 4060 Laptop 8 GiB / 32 GiB RAM / NVIDIA 577.02',
        'ros_distro': 'humble', 'rmw': 'rmw_fastrtps_cpp', 'domain': 42,
        'source': {'scene_sha256': isaac['scene_sha256'], 'stage_prims': isaac['stage_prims'],
                   'render_script_sha256': isaac['script_sha256']},
        'network': read(run / 'ros-bridge-network-20261018.json'),
        'execution': execution,
        'checks': {'clock_messages': len(peer['clock_ns']), 'clock_monotonic': peer['clock_monotonic'],
                   'clock_publishers': peer['clock_publisher_count'],
                   'received_sim_time_start_s': peer['clock_ns'][0] / 1e9 if peer['clock_ns'] else None,
                   'received_sim_time_end_s': peer['clock_ns'][-1] / 1e9 if peer['clock_ns'] else None,
                   'images_sent': len(bridge['frames']), 'images_received': len(peer['images']),
                   'pixel_hash_matches': len(matches), 'camera_info_received': len(peer['camera_info']),
                   'commands_received': len(bridge['commands']),
                   'command_kinds': sorted({(c['linear_x'], c['angular_z']) for c in bridge['commands']}),
                   'challenge_received': bridge['challenge_received']},
        'resources': {'min_available_gib': min(s['available_gib'] for s in samples),
                      'min_commit_headroom_gib': min(s['available_commit_gib'] for s in samples),
                      'peak_gpu_fraction': max(s['gpu_memory_fraction'] for s in samples)},
        'topics': peer['topic_types'],
        'limitations': ['Commands were received and acknowledged but not connected to an articulation.',
                       'This was a bounded low-rate 480x300 diagnostic, not full navigation sensor throughput.',
                       'Native rclpy publishing in the enabled bridge was tested; full OmniGraph runtime was not.',
                       'Camera is a diagnostic scene viewpoint, not a calibrated robot-mounted sensor.',
                       'Teacher-reviewed GT/map/episode inputs and robot/Nav2 integration remain pending.'],
        'cleanup': read(run / 'cleanup.json') if (run / 'cleanup.json').exists() else None,
        'artifacts': str(run),
        'script_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [root/'scripts/probe_windows_scene_render.py',root/'scripts/probe_isaac_ros_bridge.py',root/'scripts/probe_ros_wsl_peer.py']}}
for p in [run/'evidence.json',root/'docs/development/ugv-ogn/ros-bridge-20261018.json']:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'passed':passed, 'checks':data['checks'], 'resources':data['resources']},ensure_ascii=False))
if not passed:
    raise SystemExit(1)
