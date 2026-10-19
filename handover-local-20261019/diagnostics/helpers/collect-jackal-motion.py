import csv
import hashlib
import json
import math
from pathlib import Path

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/jackal_motion_20261018'
job='jackal-motion-a03'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
execution=read(run/job/'execution.json')
app=read(run/(job+'-frames')/'report.json')
motion=read(run/(job+'-frames')/'jackal-motion.json')
peer=read(run/(job+'-wsl')/'report.json')
samples=motion['samples']
by_stamp={round(s['sim_time_s']*1e9):s for s in samples}
tf_by_stamp={t['stamp_ns']:t for t in peer['tf'] if t['frame']=='ugv/odom' and t['child']=='ugv/base_link'}
matched=[]
for o in peer['odom']:
    s=by_stamp.get(o['stamp_ns']);t=tf_by_stamp.get(o['stamp_ns'])
    if s and t and o['frame']=='ugv/odom' and o['child']=='ugv/base_link':
        error=max(abs(a-b) for field in ['position','quaternion_xyzw'] for a,b in zip(s[field],o[field]))
        tf_error=max(abs(a-b) for field in ['position','quaternion_xyzw'] for a,b in zip(t[field],o[field]))
        if max(error,tf_error)<1e-9: matched.append(o['stamp_ns'])
resources=[json.loads(line) for line in (run/job/'resources.jsonl').read_text().splitlines() if line.strip()]
checks={'odom_received':len(peer['odom']),'tf_received':len(peer['tf']),
        'physx_odom_tf_exact_matches':len(matched),'clock_received':len(peer['clock_ns']),
        'clock_monotonic':peer['clock_monotonic'],'clock_publishers':peer['clock_publishers'],
        'static_map_to_odom':['map','ugv/odom'] in peer['tf_static'],
        'commands_received':len(motion['commands']),'watchdog_interventions':motion['watchdog_count']}
stopped=[s for s in samples if 6<=s['elapsed_sim_s']<=6.8 or 12<=s['elapsed_sim_s']<=12.8 or s['elapsed_sim_s']>=18]
checks['max_stopped_abs_yaw_rate_radps']=max(abs(s['angular_world'][2]) for s in stopped)
checks['pose_time_monotonic']=all(b['sim_time_s']>a['sim_time_s'] for a,b in zip(samples,samples[1:]))
passed=(execution.get('exit_code')==0 and app.get('status')=='passed' and motion.get('passed')
        and peer.get('passed') and len(matched)>=100 and len(matched)==len(peer['odom'])
        and checks['clock_publishers']==1 and checks['max_stopped_abs_yaw_rate_radps']<.06
        and checks['pose_time_monotonic'])
data={'task':'Local-Scene1-Reproduction / Jackal-ROS-Motion','date':'2026-10-18','passed':bool(passed),
      'scope':'Real wheel motion over Windows/WSL ROS, no Nav2 or benchmark',
      'robot_motion_verified':bool(passed),'nav2_verified':False,'scene1_reproduced':False,'real_episode_count':0,
      'simulator':'Isaac Sim 4.5.0 native Windows','ros':'Humble / rmw_fastrtps_cpp / domain 42',
      'hardware':'RTX 4060 Laptop 8 GiB / 32 GiB RAM / driver 577.02',
      'scene_sha256':app['scene_sha256'],'robot_setup':app['jackal_setup'],'execution':execution,
      'metrics':motion['metrics'],'checks':checks,
      'resources':{'min_available_gib':min(s['available_gib'] for s in resources),
                   'min_commit_headroom_gib':min(s['available_commit_gib'] for s in resources),
                   'peak_gpu_gib':max(s['gpu_memory_fraction'] for s in resources)*8188/1024},
      'previous_attempt':{'id':'jackal-motion-a01','metrics':read(run/'jackal-motion-a01-frames/jackal-motion.json')['metrics'],
                          'result':'Failed unchanged: final throttled sample was 18.9667 s, below 19 s duration gate. Final sampling fixed and real run repeated; thresholds unchanged.'},
      'aborted_attempt':{'id':'jackal-motion-a02','execution':read(run/'jackal-motion-a02/execution.json'),
                         'reason':'GPU telemetry nvidia-smi exceeded its 8-second deadline; guard stopped the process. Query recovered, same guards retained for retry.'},
      'limitations':['Odometry and TF come from actual PhysX rigid-body state, not encoders or localization.',
                     'Map to odom is an explicit diagnostic identity. No Nav2 action was sent.',
                     '120 Hz CPU physics and benchmark support plane/traction; not the full benchmark runtime.',
                     'Screenshots use an external diagnostic camera; onboard sensors and obstacle cloud remain pending.'],
      'nav2_next_dependencies':['Publish obstacle PointCloud2 with its actual sensor TF.',
                               'Generate a diagnostic navigability map or obtain reviewed map for exact paper replication.',
                               'Integrate existing Nav2 launch, lifecycle and NavigateToPose; preserve simulation clock.',
                               'Teacher-reviewed GT/map/episode inputs required for comparable formal benchmark.'],
      'cleanup':read(run/'cleanup.json') if (run/'cleanup.json').exists() else None,
      'images':[{'file':f,'sha256':hashlib.sha256((run/(job+'-frames')/f).read_bytes()).hexdigest()} for f in
                ['jackal-start.png','jackal-forward.png','jackal-turn.png','jackal-stopped.png']]}
with (run/'trajectory.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['elapsed_sim_s','x_m','y_m','z_m','yaw_rad','speed_mps','command_v','command_w','stale'])
    for s in samples:
        w.writerow([s['elapsed_sim_s'],*s['position'],s['yaw'],math.hypot(*s['linear_world'][:2]),*s['applied_command'],s['stale_command']])
for p in [run/'evidence.json',root/'docs/development/ugv-ogn/jackal-motion-20261018.json']:
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':passed,'metrics':data['metrics'],'checks':checks,'resources':data['resources']},ensure_ascii=False))
if not passed: raise SystemExit(1)
