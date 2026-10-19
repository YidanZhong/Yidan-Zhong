#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/mnt/d/RAVEN-4060/setup/fastdds-wsl.xml
job="$1"
case "$job" in jackal-target-a[0-9][0-9]) ;; *) exit 2 ;; esac
exec timeout --signal=INT --kill-after=30 850 python3 -u /mnt/d/RAVEN-4060/setup/probe_nav2_wsl_peer.py \
 --frames "/mnt/d/RAVEN-4060/logs/$job-frames" \
 --output "/mnt/d/RAVEN-4060/logs/$job-wsl" --run-id "$job-20261018" \
 --air-stack /mnt/d/RAVEN-4060/source/AirStack \
 >"/mnt/d/RAVEN-4060/logs/$job-wsl.log" 2>&1