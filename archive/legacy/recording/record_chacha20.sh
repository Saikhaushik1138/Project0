#!/bin/bash

# record_chacha20.sh - Recording Metrics for Case 4 (Chacha20.py Execution)

CASE="chacha20"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DIR="recording_${CASE}_${TIMESTAMP}"
mkdir -p "$DIR"

echo "--- Recording Case 4: Chacha20.py (ChaCha20-Poly1305 MAVLink Proxy) ---"

# 1. Wireshark Payload
sudo tcpdump -i lo0 -w "$DIR/payload.pcap" udp port 14540 or udp port 14550 > /dev/null 2>&1 &
TCP_PID=$!

# 2. CPU Usage (PX4 + Python Script)
PX4_PID=$(pgrep px4)
PY_PID=$(pgrep -f "python3 Chacha20.py")
top -l 0 -pid $PX4_PID -pid $PY_PID -stats "command,cpu,mem" > "$DIR/cpu_usage.log" &
TOP_PID=$!

echo "Recording started. Outputs in: $DIR"
echo "Metrics being captured: CPU, MAVLink Payload (Custom Packets)."
echo "Press Ctrl+C to stop..."

cleanup() {
    sudo kill $TCP_PID
    kill $TOP_PID
    echo -e "\nRecording stopped. Files saved in $DIR"
    exit
}

trap cleanup SIGINT
while true; do sleep 1; done
