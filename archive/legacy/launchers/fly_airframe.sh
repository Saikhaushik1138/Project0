#!/bin/bash

# fly_airframe.sh - Headless PX4 SITL (Airframe only)

echo "--- 1. Resetting Environment ---"
pkill -9 -u $USER -f "px4" 2>/dev/null || true

echo "--- 2. Launching Headless PX4 ---"
echo "No visuals. MAVLink available on UDP 14540."
echo "--------------------------------------------------------"

make px4_sitl none
