#!/bin/bash
set -e

cd "$(dirname "$0")"
source /opt/ros/noetic/setup.bash
if [ -f ~/catkin_ws/devel/setup.bash ]; then
  source ~/catkin_ws/devel/setup.bash
fi
python3 server_robot.py
