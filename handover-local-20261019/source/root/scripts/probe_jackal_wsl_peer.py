"""Send a bounded simulation-time Jackal test and record actual ROS odometry/TF."""
from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
import time


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String
    from tf2_msgs.msg import TFMessage
    from rclpy.qos import QoSProfile,DurabilityPolicy
    rclpy.init(args=[])
    node=rclpy.create_node('raven_jackal_motion_peer',namespace='/ugv')
    cmd=node.create_publisher(Twist,'/ugv/cmd_vel',10)
    challenge=node.create_publisher(String,'/ugv/diagnostic/challenge',10)
    report={'run_id':args.run_id,'clock_ns':[],'odom':[],'tf':[],'tf_static':[],'status':[],'commands':[]}
    latest=None

    def stamp(msg): return msg.sec*10**9+msg.nanosec
    def on_clock(msg: Clock): report['clock_ns'].append(stamp(msg.clock))
    def on_odom(msg: Odometry):
        p=msg.pose.pose.position;q=msg.pose.pose.orientation
        report['odom'].append({'stamp_ns':stamp(msg.header.stamp),'frame':msg.header.frame_id,'child':msg.child_frame_id,
            'position':[p.x,p.y,p.z],'quaternion_xyzw':[q.x,q.y,q.z,q.w],
            'linear_x':msg.twist.twist.linear.x,'angular_z':msg.twist.twist.angular.z})
    def on_tf(msg: TFMessage):
        for t in msg.transforms:
            p=t.transform.translation;q=t.transform.rotation
            report['tf'].append({'stamp_ns':stamp(t.header.stamp),'frame':t.header.frame_id,'child':t.child_frame_id,
                'position':[p.x,p.y,p.z],'quaternion_xyzw':[q.x,q.y,q.z,q.w]})
    def on_static(msg: TFMessage):
        report['tf_static'] += [[t.header.frame_id,t.child_frame_id] for t in msg.transforms]
    def send(t: float):
        if 15 <= t < 17:
            return  # Deliberate command silence tests the simulator watchdog.
        msg=Twist()
        if 1 <= t < 5: msg.linear.x=.25
        elif 7 <= t < 11: msg.angular.z=.3
        elif 13 <= t < 15: msg.linear.x=.15
        cmd.publish(msg)
        report['commands'].append({'elapsed_sim_s':t,'linear_x':msg.linear.x,'angular_z':msg.angular.z})
    def on_status(msg: String):
        nonlocal latest
        item=json.loads(msg.data)
        if item.get('run_id')==args.run_id:
            latest=item
            report['status'].append(item)
            send(item['elapsed_sim_s'])
    node.create_subscription(Clock,'/clock',on_clock,10)
    node.create_subscription(Odometry,'/ugv/odom',on_odom,10)
    node.create_subscription(TFMessage,'/tf',on_tf,10)
    node.create_subscription(TFMessage,'/tf_static',on_static,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    node.create_subscription(String,'/ugv/diagnostic/motion_status',on_status,10)
    (args.output/'ready.json').write_text(json.dumps({'run_id':args.run_id}))
    started,last_challenge=time.monotonic(),0.
    try:
        while time.monotonic()-started<780:
            rclpy.spin_once(node,timeout_sec=.005)
            now=time.monotonic()
            if now-last_challenge>.2:
                challenge.publish(String(data=args.run_id))
                if latest is None: send(-1)
                last_challenge=now
            if latest and latest['phase']=='finished':
                # Drain pending odometry/TF without issuing more nonzero commands.
                for _ in range(100): rclpy.spin_once(node,timeout_sec=.001)
                break
        clocks=report['clock_ns']
        report['clock_monotonic']=all(b>=a for a,b in zip(clocks,clocks[1:]))
        report['clock_publishers']=node.count_publishers('/clock')
        report['topics']=node.get_topic_names_and_types()
        report['passed']=bool(latest and latest['phase']=='finished' and len(report['odom'])>100
            and len(report['tf'])>100 and ['map','ugv/odom'] in report['tf_static'] and report['clock_monotonic'])
        logging.info('JACKAL_WSL finished=%s odom=%s tf=%s',report['passed'],len(report['odom']),len(report['tf']))
    finally:
        for _ in range(5):
            cmd.publish(Twist());rclpy.spin_once(node,timeout_sec=.02)
        report['wall_seconds']=time.monotonic()-started
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        node.destroy_node();rclpy.shutdown()
    return 0 if report.get('passed') else 1


if __name__=='__main__': raise SystemExit(main())
