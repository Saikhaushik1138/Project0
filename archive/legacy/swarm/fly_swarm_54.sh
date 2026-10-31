#!/bin/bash
# fly_swarm_54.sh - Launch 54 drones in PX4 + Gazebo SITL simulation
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
bash "$SCRIPT_DIR/../launch_swarm_gazebo.sh" 54
