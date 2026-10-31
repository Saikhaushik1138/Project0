#!/bin/bash
# fly_swarm_2.sh - Launch 2 drones in PX4 + Gazebo SITL simulation
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
bash "$SCRIPT_DIR/../launch_swarm_gazebo.sh" 2
