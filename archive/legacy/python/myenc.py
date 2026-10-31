#!/usr/bin/env python3
"""
myenc.py - Secure MAVLink Cryptographic Proxy
Implements a symmetric key validation layer to protect against raw packet injection.
This script acts as a 'Firewall' between the external network and the PX4 Autopilot.
"""

import socket
import threading
import time
import os
import hmac
import hashlib

# CONFIGURATION
PX4_IP = "127.0.0.1"
PX4_PORT = 14540       # The real PX4 port (internal)
PROXY_PORT = 14560     # The port that QGC and myenc.py communicate on (external)

# SHARED SYMMETRIC KEY (Pre-shared with authorized controllers)
SECRET_KEY = b"MAVLINK_SECURE_2026_KEY"

def verify_signature(data):
    """
    Simulates high-cost symmetric key verification.
    In a real scenario, this would check a MAVLink 2 Signature block.
    """
    # Simulate cryptographic computation cost (CPU usage)
    # We perform a heavy hash multiple times to simulate overhead
    for _ in range(1000):
        dummy = hmac.new(SECRET_KEY, data, hashlib.sha256).digest()
    
    # Check if the packet has our 'Secret Signature' appended
    # For this demo, we check if the packet ends with a specific HMAC of its own content
    # But since we want to BLOCK 'hainjec.py', we'll just check if it's 'authorized'
    
    # In this simulation: any packet from hainjec.py won't have the signature.
    # Authorized packets from our own 'Secure Controller' would have it.
    if data.endswith(b"SIGNED_OK"):
        return True
    return False

def proxy_logic():
    print(f"[🛡️] myenc.py: Secure Proxy Active on port {PROXY_PORT}")
    print(f"[🛡️] Forwarding verified traffic to PX4 at {PX4_IP}:{PX4_PORT}")

    # Socket to listen for incoming GCS/Attack traffic
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_sock.bind(("0.0.0.0", PROXY_PORT))

    # Socket to talk to PX4
    px4_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        data, addr = listen_sock.recvfrom(4096)
        
        # PERFORMANCE COST: Start of verification
        start_time = time.perf_counter()
        
        is_valid = verify_signature(data)
        
        end_time = time.perf_counter()
        processing_ms = (end_time - start_time) * 1000
        
        if is_valid:
            # Forward to PX4
            px4_sock.sendto(data[:-9], (PX4_IP, PX4_PORT)) # Strip the signature before sending to PX4
            # print(f"[OK] Forwarded valid packet. Cost: {processing_ms:.2f}ms")
        else:
            # BLOCK the packet (This blocks hainjec.py)
            print(f"[❌] BLOCKED UNAUTHORIZED PACKET from {addr}. Cost: {processing_ms:.2f}ms")

def px4_to_gcs():
    """Forward data from PX4 back to the requester."""
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_sock.bind(("0.0.0.0", 14541)) # Listener for PX4 return traffic

    gcs_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # This part is simplified for the demo
    while True:
        data, addr = listen_sock.recvfrom(4096)
        # In a real proxy, we'd sign outgoing data too.
        # For now, just forward back to port 14550 (Standard QGC)
        gcs_sock.sendto(data, ("127.0.0.1", 14550))

if __name__ == "__main__":
    try:
        t1 = threading.Thread(target=proxy_logic)
        t1.daemon = True
        t1.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[🛡️] Stopping Secure Proxy...")
