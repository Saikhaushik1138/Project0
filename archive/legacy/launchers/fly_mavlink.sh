#!/bin/bash

# fly_mavlink.sh - PX4 MAVLink-based Simulation Launcher

export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "--- 1. Checking Dependencies ---"
if ! command -v ant &> /dev/null; then
    echo "WARNING: 'ant' is not installed. jMAVSim (visuals) will not work."
    echo "Falling back to Headless MAVLink (Gazebo-based or None)..."
fi

echo "--- 2. Resetting Environment ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true
pkill -9 -u $USER -f "MAVProxy" 2>/dev/null || true

echo "--- 3. Launching MAVLink Terminal ---"
# Open a new macOS Terminal window running MAVProxy
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR' && mavproxy.py --master=udp:127.0.0.1:14550\""

echo "--- 4. Launching Simulation ---"
if command -v ant &> /dev/null; then
    make px4_sitl jmavsim
else
    echo "Running Headless SITL..."
    make px4_sitl none
fi
