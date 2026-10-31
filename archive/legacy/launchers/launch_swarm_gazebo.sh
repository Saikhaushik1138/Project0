#!/bin/bash
# launch_swarm_gazebo.sh - Unified PX4 multi-vehicle SITL Gazebo swarm launcher.
# Usage: ./launch_swarm_gazebo.sh <num_drones>

NUM_DRONES=$1
if [ -z "$NUM_DRONES" ]; then
    echo "Usage: $0 <num_drones> (e.g., 2, 4, 8, 16, 32, 64)"
    exit 1
fi

echo "=================================================================="
echo "🚀 LAUNCHING SWARM OF $NUM_DRONES DRONES IN PX4 + GAZEBO SITL 🚀"
echo "=================================================================="

# Set file descriptor limit higher for large swarms
ulimit -n 4096 2>/dev/null || true

# 1. Cleanup old instances
echo "--- 1. Resetting Environment ---"
pkill -9 px4 || true
pkill -9 -f "gz sim" || true
pkill -9 ruby || true
pkill -9 -f MAVProxy || true
rm -rf ~/.gz/sim/* 2>/dev/null || true

# 2. Paths and Pose
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -d "$SCRIPT_DIR/New Folder With Items/Tools" ]; then
    TOOLS_DIR="$SCRIPT_DIR/New Folder With Items/Tools"
else
    TOOLS_DIR="$SCRIPT_DIR/Tools"
fi

export PX4_GZ_MODELS="$TOOLS_DIR/simulation/gz/models"
export PX4_GZ_WORLDS="$TOOLS_DIR/simulation/gz/worlds"
export GZ_SIM_RESOURCE_PATH="$PX4_GZ_MODELS:$PX4_GZ_WORLDS"
export GZ_SIM_RENDER_ENGINE=ogre2

# Source env script if it exists
if [ -f "$SCRIPT_DIR/build/px4_sitl_default/rootfs/gz_env.sh" ]; then
    source "$SCRIPT_DIR/build/px4_sitl_default/rootfs/gz_env.sh"
fi

# 3. Choose layout cols
if [ $NUM_DRONES -le 4 ]; then
    COLS=2
elif [ $NUM_DRONES -le 16 ]; then
    COLS=4
else
    COLS=8
fi

SPACING=3.0 # meters spacing in grid

echo "--- 2. Starting Instance 0 (Launches Gazebo Server & UI) ---"
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_GZ_MODEL_POSE="0,0,0,0,0,0"

# Make sure working directory for instance 0 exists
mkdir -p "$SCRIPT_DIR/build/px4_sitl_default/instance_0"
cd "$SCRIPT_DIR/build/px4_sitl_default/instance_0"
"$SCRIPT_DIR/build/px4_sitl_default/bin/px4" -i 0 -d "$SCRIPT_DIR/build/px4_sitl_default/etc" > px4_0.log 2>&1 &
PX4_0_PID=$!

echo "Waiting for Gazebo server to initialize..."
sleep 10

# 4. Spawn other instances
echo "--- 3. Starting Remaining $((NUM_DRONES - 1)) Standalone Instances ---"
export PX4_GZ_STANDALONE=1

for (( k=1; k<$NUM_DRONES; k++ )); do
    ROW=$(($k / $COLS))
    COL=$(($k % $COLS))
    X=$(echo "$COL * $SPACING" | bc)
    Y=$(echo "$ROW * $SPACING" | bc)
    
    export PX4_SYS_AUTOSTART=4001
    export PX4_SIM_MODEL=gz_x500
    export PX4_GZ_MODEL_POSE="$X,$Y,0,0,0,0"
    echo "Starting Drone $((k+1)) / $NUM_DRONES at pos ($X, $Y) [Instance ID: $k]..."
    
    mkdir -p "$SCRIPT_DIR/build/px4_sitl_default/instance_$k"
    cd "$SCRIPT_DIR/build/px4_sitl_default/instance_$k"
    "$SCRIPT_DIR/build/px4_sitl_default/bin/px4" -i $k -d "$SCRIPT_DIR/build/px4_sitl_default/etc" > px4_$k.log 2>&1 &
    
    sleep 1.2 # Stagger launches to avoid overloading CPU/RAM
done

echo "------------------------------------------------------------------"
echo "✨ Swarm loaded successfully!"
echo "QGroundControl will automatically connect and show all $NUM_DRONES drones."
echo "If you have MAVProxy installed, run: mavproxy.py --master=udp:127.0.0.1:14550"
echo "To control all drones simultaneously, use QGroundControl Swarm features."
echo "------------------------------------------------------------------"
echo "Press Ctrl+C to terminate simulation and clean up."

cleanup() {
    echo -e "\n--- Terminating Swarm Simulation ---"
    pkill -9 px4 || true
    pkill -9 -f "gz sim" || true
    pkill -9 ruby || true
    exit 0
}

trap cleanup SIGINT

# Keep script running
while true; do
    sleep 1
done
