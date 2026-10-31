#!/bin/bash

# fly_case2.sh - Vulnerable: Standard Simulation + Potential Attack

echo "--- Case 2: Vulnerable (Unprotected, Attack Ready) ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true
pkill -9 -u $USER -f "hainjec" 2>/dev/null || true

export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR/Tools/simulation/gz/models:$SCRIPT_DIR/Tools/simulation/gz/worlds"

echo "Launching Gazebo & PX4..."
echo "TIP: Use 'python3 hainjec.py' in a separate terminal to simulate the Disarm Hack."
make px4_sitl_default gz_x500
