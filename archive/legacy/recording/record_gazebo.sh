#!/bin/bash

# record_gazebo.sh - Recording Metrics for Case 2 (Gazebo + MAVLink)

CASE="gazebo"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DIR="recording_${CASE}_${TIMESTAMP}"
mkdir -p "$DIR"

echo "--- Recording Case 2: Gazebo + MAVLink ---"

# 1. Wireshark Payload
sudo tcpdump -i lo0 -w "$DIR/payload.pcap" udp port 14540 or udp port 14550 > /dev/null 2>&1 &
TCP_PID=$!

# 2. CPU Usage (PX4 + Gazebo/Ruby)
PX4_PID=$(pgrep px4)
GZ_PID=$(pgrep ruby)
top -l 0 -pid $PX4_PID -pid $GZ_PID -stats "command,cpu,mem" > "$DIR/cpu_usage.log" &
TOP_PID=$!

# 3. Gazebo Stats (for 1% low frames)
gz topic -e -t /world/default/stats > "$DIR/gazebo_stats.log" &
GZ_PID_STATS=$!

echo "Recording started. Outputs in: $DIR"
echo "Metrics being captured: CPU, MAVLink Payload, 1% Low Frame Data."
echo "Press Ctrl+C to stop..."

cleanup() {
    sudo kill $TCP_PID
    kill $TOP_PID
    kill $GZ_PID_STATS
    echo -e "\nRecording stopped. Files saved in $DIR"
    echo "Tip: Run 'python3 analyze_stats.py $DIR/gazebo_stats.log' for frame analysis."
    exit
}

trap cleanup SIGINT
while true; do sleep 1; done
