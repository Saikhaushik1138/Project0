#!/bin/bash

# run_drone.sh - PX4 Gazebo SITL Automation Script

echo "--- Cleaning up previous processes ---"
pkill -9 px4 || true
pkill -9 ruby || true
pkill -9 gz || true

echo "--- Ensuring submodules are initialized ---"
git submodule update --init --recursive --jobs 8

echo "--- Starting PX4 SITL with Gazebo (x500 model) ---"
echo "Drone will takeoff automatically once initialized."
echo "MAVLink Offboard Port: UDP 14540"
echo "------------------------------------------------"

# Start the simulation in the background
make px4_sitl_default gz_x500 &

# Wait for PX4 to start and be ready for commands
echo "Waiting for PX4 to initialize..."
sleep 15

# Send takeoff command via the commander utility
./build/px4_sitl_default/bin/px4-commander takeoff

echo "--- Drone should now be in the air ---"
echo "Use 'killall px4' to stop the simulation."
wait
