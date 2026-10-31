import time
from pymavlink import mavutil

print("Connecting to your active Mac Gazebo Drone...")
# Connect directly to the local PX4 simulator network port
drone = mavutil.mavlink_connection('udpin:localhost:14540')

# Wait for a heartbeat signal from the simulator
drone.wait_heartbeat()
print("Connected! Your script is now officially talking via MAVLink.")

try:
    while True:
        # Grab live global positioning data coming out of Gazebo
        msg = drone.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1.0)
        if msg:
            # Convert relative altitude from millimeters to meters
            alt = msg.relative_alt / 1000.0
            print(f"[MAVLink Data] Drone Altitude: {alt:.2f}m")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("Disconnected.")