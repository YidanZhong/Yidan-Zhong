#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/mnt/d/RAVEN-4060/setup/fastdds-wsl.xml
python3 - <<'PY'
import rclpy,time,json,math
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
rclpy.init();n=rclpy.create_node('raven_route_inspect');d={}
def odom(m):
 q=m.pose.pose.orientation;p=m.pose.pose.position
 d['odom']={'stamp':m.header.stamp.sec+m.header.stamp.nanosec*1e-9,'xy':[p.x,p.y],'yaw':math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),'v':m.twist.twist.linear.x,'w':m.twist.twist.angular.z}
def cmd(m):d['cmd']=[m.linear.x,m.angular.z]
n.create_subscription(Odometry,'/ugv/odom',odom,10);n.create_subscription(Twist,'/ugv/cmd_vel',cmd,10)
t=time.monotonic()
while time.monotonic()-t<4:rclpy.spin_once(n,timeout_sec=.1)
print(json.dumps(d));n.destroy_node();rclpy.shutdown()
PY