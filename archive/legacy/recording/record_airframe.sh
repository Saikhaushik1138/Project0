#!/bin/bash

# record_airframe.sh - Recording Metrics for Case 1 (Headless Airframe)

CASE="airframe"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DIR="recording_${CASE}_${TIMESTAMP}"
mkdir -p "$DIR"

echo "--- Recording Case 1: Airframe (Headless) ---"

# 1. Wireshark Payload (MAVLink Traffic)
sudo tcpdump -i lo0 -w "$DIR/payload.pcap" udp port 14540 or udp port 14550 > /dev/null 2>&1 &
TCP_PID=$!

# 2. CPU Usage
PX4_PID=$(pgrep px4)
top -l 0 -pid $PX4_PID -stats "command,cpu,mem" > "$DIR/cpu_usage.log" &
TOP_PID=$!

echo "Recording started. Outputs in: $DIR"
echo "Metrics being captured: Idle/Peak CPU, MAVLink Payload."
echo "Press Ctrl+C to stop..."

cleanup() {
    sudo kill $TCP_PID
    kill $TOP_PID
    echo -e "\nRecording stopped. Files saved in $DIR"
    exit
}

trap cleanup SIGINT
while true; do sleep 1; done
