#!/bin/bash

# fly_case1.sh - Baseline: Standard Simulation

echo "--- Case 1: Baseline (Unprotected, No Attack) ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true

export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR/Tools/simulation/gz/models:$SCRIPT_DIR/Tools/simulation/gz/worlds"

echo "Launching Gazebo & PX4... Connect QGroundControl to UDP 14550."
make px4_sitl_default gz_x500
