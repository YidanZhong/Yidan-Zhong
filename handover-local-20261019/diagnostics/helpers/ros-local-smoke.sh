#!/bin/bash
set -euo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=1
out=/mnt/d/RAVEN-4060/logs/ros-local-smoke
mkdir -p "$out"
timeout 12 ros2 run demo_nodes_cpp talker >"$out/talker.log" 2>&1 &
talker=$!
trap 'kill "$talker" 2>/dev/null || true' EXIT
set +e
timeout 10 ros2 run demo_nodes_cpp listener >"$out/listener.log" 2>&1
result=$?
set -e
if [ "$result" != 124 ] && [ "$result" != 0 ]; then cat "$out/listener.log"; exit "$result"; fi
if ! grep -q 'I heard' "$out/listener.log"; then cat "$out/listener.log"; exit 1; fi
tail -n 3 "$out/listener.log"
echo RAVEN_ROS_LOCAL_PUBSUB_PASSED
