#!/bin/bash

# record_metrics.sh - Comprehensive PX4/Gazebo Performance Recorder

OUTPUT_DIR="recordings_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "--- Performance Recording Started ---"
echo "Outputs will be saved in: $OUTPUT_DIR"

# 1. Capture MAVLink Payloads (Wireshark compatible)
# Note: Requires sudo for tcpdump on some Mac configurations
echo "[1/4] Starting MAVLink packet capture (UDP 14540, 14550)..."
sudo tcpdump -i lo0 -w "$OUTPUT_DIR/mavlink_traffic.pcap" udp port 14540 or udp port 14550 > /dev/null 2>&1 &
TCPDUMP_PID=$!

# 2. Capture Gazebo Simulation Stats (Frame rates / RTF)
echo "[2/4] Starting Gazebo statistics logging..."
gz topic -e -t /world/default/stats > "$OUTPUT_DIR/gazebo_stats.log" &
GZ_STATS_PID=$!

# 3. Capture System-level CPU Usage (Mac top)
echo "[3/4] Starting CPU usage monitoring..."
# Monitor px4 and ruby (Gazebo) processes
PX4_PID=$(pgrep px4)
GZ_PID=$(pgrep ruby) # Gazebo Sim usually runs as 'ruby' or 'gz'
top -l 0 -pid $PX4_PID -stats "command,cpu,mem" > "$OUTPUT_DIR/system_cpu.log" &
TOP_PID=$!

# 4. Internal PX4 Performance (Update Rates & Module CPU)
echo "[4/4] Instructions for Internal Metrics:"
echo "     To get Update Rates: Run 'perf' in the pxh shell."
echo "     To get Module CPU:   Run 'top' in the pxh shell."
echo "----------------------------------------------------"
echo "Press Ctrl+C to stop recording..."

cleanup() {
    echo ""
    echo "--- Stopping Recording ---"
    sudo kill $TCPDUMP_PID
    kill $GZ_STATS_PID
    kill $TOP_PID
    echo "Processing data..."
    
    # Extract Average Update Rate (Example from a log if we had it, 
    # but PX4 ULog is better for this)
    
    echo "Results saved to $OUTPUT_DIR"
    exit
}

trap cleanup SIGINT

# Keep script running
while true; do
    sleep 1
done
