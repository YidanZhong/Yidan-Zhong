"""Launch repository Nav2 on a measured local map and independently record ROS evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--air-stack',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    ready=args.frames/'nav2-ready.json'
    deadline=time.monotonic()+600
    while not ready.exists():
        if time.monotonic()>deadline: raise RuntimeError('Native map/sensor readiness deadline exceeded')
        native_report=args.frames/'report.json'
        if native_report.exists(): raise RuntimeError('Native probe exited before navigation readiness')
        execution=args.frames.parent/args.frames.name.removesuffix('-frames')/'execution.json'
        if execution.exists(): raise RuntimeError('Native resource guard exited before navigation readiness')
        time.sleep(.5)
    configuration=json.loads(ready.read_text())
    if configuration['run_id']!=args.run_id: raise RuntimeError('Native run identifier mismatch')
    full_map=configuration.get('full_map',False)
    if full_map:
        import numpy as np
        # The pinned exporter writes binary P5 with a full-line comment.
        # Read directly without adding an image dependency to the ROS runtime.
        with (args.frames/'local-map.pgm').open('rb') as stream:
            header=[]
            while len(header)<4:
                header.extend(stream.readline().split(b'#',1)[0].split())
            if header[0]!=b'P5' or header[3]!=b'255':
                raise RuntimeError('Expected 8-bit P5 map')
            source_cells=np.frombuffer(stream.read(),dtype=np.uint8).reshape(int(header[2]),int(header[1]))[::-1]
        expected_map=np.where(source_cells==254,0,100).astype(np.int8)
        if hashlib.sha256((args.frames/'local-map.pgm').read_bytes()).hexdigest()!=configuration['map_pgm_sha256']:
            raise RuntimeError('Transferred full map checksum differs')
        os.environ['AIRGROUND_LEAN_SUBSCRIPTIONS']='1'

    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import OccupancyGrid, Odometry, Path as NavPath
    from sensor_msgs.msg import PointCloud2
    from rosgraph_msgs.msg import Clock
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from action_msgs.msg import GoalStatusArray

    rclpy.init(args=[])
    node=rclpy.create_node('raven_nav2_evidence',namespace='/ugv')
    record={'run_id':args.run_id,'clouds':[],'odom':[],'plans':[],'clock_count':0,
            'clock_backwards':0,'max_clock_publishers':0,'cmd_count':0,'costmaps':{},'cloud_subscribers':[],
            'terminal_actions':[]}
    terminal_ids=set()
    map_subscriptions={}
    previous_clock=-1.
    def stamp(t): return t.sec+t.nanosec*1e-9
    def cloud(msg):
        record['clouds'].append({'sim_time_s':stamp(msg.header.stamp),'points':msg.width*msg.height,
            'frame':msg.header.frame_id,'sha256':hashlib.sha256(bytes(msg.data)).hexdigest()})
    def odom(msg):
        p=msg.pose.pose.position
        record['odom'].append({'sim_time_s':stamp(msg.header.stamp),'x':p.x,'y':p.y,'z':p.z})
    def clock(msg):
        nonlocal previous_clock
        t=stamp(msg.clock)
        record['clock_backwards']+=int(t<previous_clock)
        previous_clock=t
        record['clock_count']+=1
    def cmd(msg): record['cmd_count']+=1
    def plan(msg):
        record['plans'].append({'sim_time_s':stamp(msg.header.stamp),
            'xy':[[p.pose.position.x,p.pose.position.y] for p in msg.poses]})
    def action_status(msg):
        for entry in msg.status_list:
            uid=bytes(entry.goal_info.goal_id.uuid).hex()
            if entry.status>=4 and uid not in terminal_ids:
                terminal_ids.add(uid)
                record['terminal_actions'].append({'uuid':uid,'status':entry.status,'sim_time_s':previous_clock,
                    'odom':record['odom'][-1] if record['odom'] else None})
    def costmap(name,msg):
        entry=record['costmaps'].setdefault(name,{'messages':0,'max_lethal_cells':0})
        entry['messages']+=1
        if full_map:
            cells=np.frombuffer(msg.data,dtype=np.int8).reshape(msg.info.height,msg.info.width)
            entry['max_lethal_cells']=max(entry['max_lethal_cells'],int(np.count_nonzero(cells>=99)))
            entry.update({'width':msg.info.width,'height':msg.info.height,'resolution':msg.info.resolution,
                'origin':[msg.info.origin.position.x,msg.info.origin.position.y],
                'sha256':hashlib.sha256(msg.data).hexdigest()})
            if entry['messages']==1 or (name=='local' and entry['messages']%10==0):
                np.savez_compressed(args.output/f'{name}-latest.npz',data=cells,
                    origin=entry['origin'],resolution=msg.info.resolution,sim_time_s=stamp(msg.header.stamp))
            if name=='map':
                entry['matches_full_source_map']=bool(np.array_equal(cells,expected_map))
            if name in ('map','global') and name in map_subscriptions:
                node.destroy_subscription(map_subscriptions.pop(name))
            return
        entry['max_lethal_cells']=max(entry['max_lethal_cells'],sum(v>=99 for v in msg.data))
        if entry['messages']==1 or entry['messages']%10==0:
            payload={'width':msg.info.width,'height':msg.info.height,'resolution':msg.info.resolution,
                'origin':[msg.info.origin.position.x,msg.info.origin.position.y],
                'sim_time_s':stamp(msg.header.stamp),'data':list(msg.data)}
            (args.output/f'{name}-latest.json').write_text(json.dumps(payload))
    node.create_subscription(PointCloud2,'/ugv/sensors/ouster/point_cloud',cloud,20)
    node.create_subscription(Odometry,'/ugv/odom',odom,50)
    node.create_subscription(Clock,'/clock',clock,50)
    node.create_subscription(Twist,'/ugv/cmd_vel',cmd,20)
    node.create_subscription(NavPath,'/ugv/plan',plan,10)
    node.create_subscription(GoalStatusArray,'/ugv/navigate_to_pose/_action/status',action_status,
        QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    for name,topic in [('map','/ugv/map'),('local','/ugv/local_costmap/costmap'),('global','/ugv/global_costmap/costmap')]:
        map_subscriptions[name]=node.create_subscription(OccupancyGrid,topic,lambda msg,n=name:costmap(n,msg),qos)
    goals=configuration.get('goals_xy',[configuration['goal_xy']])
    tour_arg=';'.join(f'{goal[0]},{goal[1]}' for goal in goals)
    command=[sys.executable,'-u',str(args.air_stack/'simulation/isaac-sim/tools/run_nav2_smoke.py'),
        '--output',str(args.output/'nav2-steps.jsonl'),'--work-dir',str(args.output/'nav2-runtime'),
        '--map-yaml',str(args.frames/'local-map.yaml'),f'--tour-goals={tour_arg}',
        '--tour-output',str(args.output/'tour.json'),'--tour-goal-timeout-s','120','--tour-settle-s','3',
        '--startup-timeout-s','90','--tf-startup-timeout-s','30',
        '--desired-linear-vel-mps','.2','--max-linear-vel-mps','.25','--max-angular-vel-radps','.35',
        # Keep the repository's 20 rad/s^2 angular-acceleration default. RPP
        # limits the command relative to measured yaw rate; a low override
        # traps the stationary skid-steer below its static-friction threshold.
        '--linear-accel-mps2','.3',
        '--costmap-resolution-m','.05' if full_map else '.1','--local-costmap-size-m','8',
        '--pointcloud-obstacle-range-m','8','--pointcloud-raytrace-range-m','10']
    (args.output/'command.json').write_text(json.dumps(command,indent=2))
    log=(args.output/'runner.log').open('w')
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    started=time.monotonic();last_check=0
    try:
        while process.poll() is None:
            rclpy.spin_once(node,timeout_sec=.02)
            if time.monotonic()-last_check>2:
                record['max_clock_publishers']=max(record['max_clock_publishers'],node.count_publishers('/clock'))
                for endpoint in node.get_subscriptions_info_by_topic('/ugv/sensors/ouster/point_cloud'):
                    identity=endpoint.node_namespace.rstrip('/')+'/'+endpoint.node_name
                    if identity not in record['cloud_subscribers']: record['cloud_subscribers'].append(identity)
                last_check=time.monotonic()
                steps=args.output/'nav2-steps.jsonl'
                completed=[]
                if steps.exists():
                    for line in steps.read_text().splitlines():
                        try: entry=json.loads(line)
                        except json.JSONDecodeError: continue
                        if entry.get('step')=='tour_goal': completed.append(entry['details'])
                temporary=args.output/'goal-progress.tmp'
                temporary.write_text(json.dumps({'run_id':args.run_id,'goals':completed}))
                temporary.replace(args.output/'goal-progress.json')
            if time.monotonic()-started>480:
                raise RuntimeError('WSL navigation wall deadline exceeded')
            if (args.frames/'report.json').exists():
                raise RuntimeError('Native simulation exited during navigation')
            if (args.frames.parent/args.frames.name.removesuffix('-frames')/'execution.json').exists():
                raise RuntimeError('Native resource guard exited during navigation')
        record['exit_code']=process.returncode
        for _ in range(30): rclpy.spin_once(node,timeout_sec=.01)
        tour_path=args.output/'tour.json'
        record['tour']=json.loads(tour_path.read_text()) if tour_path.exists() else None
        record['passed']=bool(process.returncode==0 and record['tour'] and record['tour']['reached_count']==len(goals)
            and len(record['terminal_actions'])==len(goals) and all(a['status']==4 for a in record['terminal_actions'])
            and record['plans'] and record['cmd_count']>10 and len(record['clouds'])>10
            and all(record['costmaps'].get(n,{}).get('messages',0)>0 for n in ('map','global','local'))
            and record['costmaps']['local']['max_lethal_cells']>0
            and record['clock_backwards']==0 and record['max_clock_publishers']==1)
        if full_map:
            record['passed']=bool(record['passed'] and record['costmaps'].get('map',{}).get('matches_full_source_map')
                and record['costmaps']['global']['width']==record['costmaps']['map']['width']
                and record['costmaps']['global']['height']==record['costmaps']['map']['height']
                and record['costmaps']['global']['origin']==record['costmaps']['map']['origin']
                and abs(record['costmaps']['global']['resolution']-.05)<1e-8)
            record['map_evidence_policy']='Full map/global binary snapshots once; local costmap live; existing lean subscriptions enabled'
    except BaseException as exc:
        record['passed']=False;record['error']=repr(exc)
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGINT)
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGTERM)
        log.close()
        record['wall_seconds']=time.monotonic()-started
        (args.output/'ros-evidence.json').write_text(json.dumps(record,indent=2))
        result={key:record.get(key) for key in ('run_id','passed','exit_code','error','tour','costmaps','clock_backwards','max_clock_publishers')}
        temporary=args.output/'done.tmp'
        temporary.write_text(json.dumps(result,indent=2));temporary.replace(args.output/'done.json')
        print(json.dumps(result),flush=True)
        node.destroy_node();rclpy.shutdown()
    return 0 if record['passed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
