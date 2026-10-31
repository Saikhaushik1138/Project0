#!/bin/bash

# fly_case6.sh - Secure Simulation with Ultra-Hardened ChaCha20-Poly1305 V10 Proxy
# Encrypts all GCS <-> Drone communication bi-directionally.

echo "--- Case 6: Secure (Protected by Chacha20_ultra_hardened_V10.py via secure_proxy_v10.py) ---"

# 1. Clean up existing processes
pkill -9 -u $USER -f "px4" 2>/dev/null || true
pkill -9 -u $USER -f "gz sim" 2>/dev/null || true
pkill -9 -u $USER -f "secure_proxy_v10" 2>/dev/null || true
pkill -9 -u $USER -f "Chacha20_ultra_hardened_V10" 2>/dev/null || true

# 2. Export environment variables for the V10 Crypto implementation
export DRONE_LAT="47.397742"
export DRONE_LON="8.545594"
export DRONE_GCS_TOKEN_KEY="b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"
export DRONE_KEYSTORE='{"drone_A": "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"}'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR/Tools/simulation/gz/models:$SCRIPT_DIR/Tools/simulation/gz/worlds"

# 3. Start the Bidirectional Proxy
echo "1. Starting Secure MAVLink Proxy (secure_proxy_v10.py)..."
python3 -u secure_proxy_v10.py &
PROXY_PID=$!

# Give the proxy a moment to bind to sockets
sleep 1

# 4. Launch PX4 & Gazebo simulation
echo "2. Launching Gazebo & PX4..."
echo "----------------------------------------------------------------------"
echo "INSTRUCTIONS FOR QGROUNDCONTROL:"
echo "Configure a UDP Comm Link in QGroundControl:"
echo "  - Port: 14550 (GCS listens here for decrypted telemetry)"
echo "  - Target Hosts: add '127.0.0.1:14560' (Sends unencrypted commands here)"
echo "----------------------------------------------------------------------"

make px4_sitl_default gz_x500

# Cleanup on exit
echo "Cleaning up..."
kill $PROXY_PID 2>/dev/null || true
pkill -9 -u $USER -f "secure_proxy_v10" 2>/dev/null || true
