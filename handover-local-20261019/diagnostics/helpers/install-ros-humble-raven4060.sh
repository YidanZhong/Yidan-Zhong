#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export LANG=C.UTF-8
exec > >(tee -a /mnt/d/RAVEN-4060/logs/ros-humble-install.log) 2>&1
date -Is
curl -fsSL --connect-timeout 15 --max-time 45 --retry 2 https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest -o /tmp/raven-ros-source-release.json
version=$(python3 -c 'import json; print(json.load(open("/tmp/raven-ros-source-release.json"))["tag_name"])')
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
curl -fsSL --connect-timeout 15 --max-time 120 --retry 2 "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${version}/ros2-apt-source_${version}.jammy_all.deb" -o /tmp/raven-ros2-apt-source.deb
dpkg -i /tmp/raven-ros2-apt-source.deb
apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update
apt-get --no-remove -y install systemd udev libsystemd0 libudev1
apt-get --no-remove -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -y install --no-install-recommends ros-humble-ros-base ros-humble-demo-nodes-cpp
set +u
source /opt/ros/humble/setup.bash
set -u
ros2 pkg prefix rclpy
ros2 pkg prefix demo_nodes_cpp
dpkg-query -W ros-humble-ros-base ros-humble-rmw-fastrtps-cpp
date -Is
echo RAVEN_ROS_HUMBLE_INSTALLED
