#!/bin/bash

# fly.sh - PX4 Gazebo SITL with Interactive MAVLink Terminal

echo "--- 1. Resetting Environment ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true
pkill -9 -u $USER -f "ruby" 2>/dev/null || true
pkill -9 -u $USER -f "MAVProxy" 2>/dev/null || true

# Clear Gazebo cache
rm -rf ~/.gz/sim/* 2>/dev/null || true

echo "--- 2. Setting Resource Paths ---"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR/Tools/simulation/gz/models:$SCRIPT_DIR/Tools/simulation/gz/worlds"
export GZ_SIM_RENDER_ENGINE=ogre2
export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"

echo "--- 3. Launching MAVLink Terminal ---"
# Open a new macOS Terminal window running MAVProxy
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR' && mavproxy.py --master=udp:127.0.0.1:14550\""

echo "--- 4. Launching Drone & Gazebo ---"
echo "The PX4 shell (pxh) will run in THIS terminal."
echo "A separate MAVLink terminal (MAVProxy) has been opened."
echo "--------------------------------------------------------"

# Run the simulation
make px4_sitl_default gz_x500
