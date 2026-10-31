#!/bin/bash

# fly_case3.sh - Secure: Simulation with myenc.py Proxy

echo "--- Case 3: Secure (Protected by myenc.py) ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true
pkill -9 -u $USER -f "myenc" 2>/dev/null || true
pkill -9 -u $USER -f "hainjec" 2>/dev/null || true

export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR/Tools/simulation/gz/models:$SCRIPT_DIR/Tools/simulation/gz/worlds"

echo "1. Starting Secure MAVLink Proxy (myenc.py)..."
python3 myenc.py &
PROXY_PID=$!

echo "2. Launching Gazebo & PX4..."
echo "TIP: 'python3 hainjec.py' will now be BLOCKED by the proxy."
echo "     The proxy adds CPU and Latency overhead (visible in metrics)."

make px4_sitl_default gz_x500

kill $PROXY_PID
