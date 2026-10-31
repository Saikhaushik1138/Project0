#!/bin/bash

# fly_case4.sh - Secure: Simulation with Chacha20_hardened.py Proxy

echo "--- Case 4: Secure (Protected by Chacha20_hardened.py) ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true
pkill -9 -u $USER -f "Chacha20_hardened" 2>/dev/null || true
pkill -9 -u $USER -f "hainjec" 2>/dev/null || true
pkill -9 -u $USER -f "record_chacha20_hardened.sh" 2>/dev/null || true

export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR/Tools/simulation/gz/models:$SCRIPT_DIR/Tools/simulation/gz/worlds"

echo "1. Starting Secure MAVLink Proxy (Chacha20_hardened.py)..."
# Note: DRONE_CHACHA_KEY must be set in the environment
python3 Chacha20_hardened.py &
PROXY_PID=$!

echo "2. Starting Recording (record_chacha20_hardened.sh)..."
bash record_chacha20_hardened.sh &
RECORD_PID=$!

echo "3. Launching Gazebo & PX4..."
echo "TIP: 'python3 hainjec.py' will now be BLOCKED by the proxy."
echo "     The proxy adds CPU and Latency overhead (visible in metrics)."

make px4_sitl_default gz_x500

kill -SIGINT $RECORD_PID
kill $PROXY_PID
