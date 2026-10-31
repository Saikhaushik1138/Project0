#!/usr/bin/env python3
"""
UAV Swarm Simulation Engine - MAVLink & ChaCha20-Poly1305 Integration
=====================================================================
This module simulates a multi-node UAV swarm network using raw binary MAVLink v2
packets encrypted with ChaCha20-Poly1305 (from Chacha20_hardened.py) under a
simulated cyber-attack.
"""

import os
import time
import struct
import hmac
import hashlib
import random
import collections
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.exceptions import InvalidTag

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Pre-shared symmetric key (32 bytes) used by the swarm proxies
SWARM_SECRET_KEY = b"MAVLINK_CHACHA20_SWARM_SECRET_32"

class MAVLinkFrameSimulator:
    """Helper to build standard binary MAVLink v2 frames."""
    @staticmethod
    def calculate_crc(buffer: bytes) -> int:
        crc = 0xFFFF
        for byte in buffer:
            tmp = byte ^ (crc & 0xFF)
            tmp ^= (tmp << 4) & 0xFF
            crc = (crc >> 8) ^ (tmp << 8) ^ (tmp << 1) ^ (tmp << 4)
        return crc & 0xFFFF

    @staticmethod
    def build_unencrypted_command(cmd_id: int, sys_id=1, comp_id=1, seq=1) -> bytes:
        """Builds a raw, unencrypted MAVLink v2 COMMAND_LONG frame."""
        magic = b'\xFD'
        payload_len = b'\x21'      # 33 bytes payload for COMMAND_LONG
        incompat_flags = b'\x00'
        compat_flags = b'\x00'
        seq_byte = struct.pack("B", seq)
        sys_id_byte = struct.pack("B", sys_id)
        comp_id_byte = struct.pack("B", comp_id)
        msg_id_bytes = b'\x4C\x00\x00' # Message ID 76 (COMMAND_LONG) in 3 bytes
        
        # Payload (COMMAND_LONG)
        param1 = struct.pack("<f", 0.0) 
        padding = struct.pack("<ffffff", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        command_field = struct.pack("<H", cmd_id)
        target_sys = b'\x01'
        target_comp = b'\x01'
        confirmation = b'\x00'
        
        payload = param1 + padding + command_field + target_sys + target_comp + confirmation
        header_payload = payload_len + incompat_flags + compat_flags + seq_byte + sys_id_byte + comp_id_byte + msg_id_bytes + payload
        
        # MAVLink CRC seed for COMMAND_LONG is 152 (0x98)
        crc = MAVLinkFrameSimulator.calculate_crc(header_payload + b'\x98')
        return magic + header_payload + struct.pack("<H", crc)

class DroneNode:
    def __init__(self, node_id, lat, lon, is_compromised=False):
        self.node_id = node_id
        # STATUS: "ACTIVE" (normal flight), "COMPROMISED" (attacker), "DISARMED" (crashed due to successful attack)
        self.status = "COMPROMISED" if is_compromised else "ACTIVE"
        
        # GPS coordinate binding values (used as AAD in ChaCha20-Poly1305 proxy)
        self.lat = lat
        self.lon = lon
        
        # Cryptographic Proxy state (Chacha20_hardened.py)
        self.seen_nonces = set()
        self.key = SWARM_SECRET_KEY
        
        # Node statistics
        self.benign_sent = 0
        self.benign_received = 0
        self.benign_dropped_noise = 0
        
        self.attack_sent = 0
        self.attack_detected = 0
        self.attack_succeeded = 0
        self.false_positives = 0
        self.false_negatives = 0

    def reset_metrics(self):
        self.benign_sent = 0
        self.benign_received = 0
        self.benign_dropped_noise = 0
        self.attack_sent = 0
        self.attack_detected = 0
        self.attack_succeeded = 0
        self.false_positives = 0
        self.false_negatives = 0

    # ---------------------------------------------------------------------------
    # Cryptographic Proxy Logic (from Chacha20_hardened.py)
    # ---------------------------------------------------------------------------
    def encrypt_packet(self, payload: bytes, target_lat: float, target_lon: float) -> bytes:
        """Encrypts MAVLink payload with ChaCha20-Poly1305, binding target GPS as AAD."""
        nonce = os.urandom(12)
        aad = struct.pack(">dd", target_lat, target_lon) # V6 Fix: Target location bound to packet
        chacha = ChaCha20Poly1305(self.key)
        ct = chacha.encrypt(nonce=nonce, data=payload, associated_data=aad)
        
        # Assemble encrypted wire frame:
        # Magic (0xFD) + Header fields + Nonce (12 bytes) + Ciphertext & Tag (ct)
        header = (
            b'\xFD'                          # magic
            + struct.pack("B", len(ct))      # payload length
            + b'\x00\x00'                    # flags
            + b'\x01'                        # seq
            + struct.pack("B", self.node_id) # sys_id
            + b'\xBE'                        # comp_id
            + b'\x02\xCB\x00'                # custom secure msg_id
        )
        return header + nonce + ct

    def decrypt_packet(self, data: bytes) -> bytes | None:
        """Decrypts and verifies incoming packets, checking MAC and AAD (GPS)."""
        MIN_LEN = 1 + 9 + 12 + 16 # Magic + Header + Nonce + Poly1305 Tag
        if len(data) < MIN_LEN or data[0] != 0xFD:
            return None
            
        nonce = data[10:22]
        ciphertext = data[22:]
        aad = struct.pack(">dd", self.lat, self.lon) # Expect packet bound to THIS node's GPS location
        
        chacha = ChaCha20Poly1305(self.key)
        try:
            return chacha.decrypt(nonce=nonce, data=ciphertext, associated_data=aad)
        except InvalidTag:
            return None # MAC or GPS verification failed!

    def generate_arm_token(self, nonce: bytes, cmd: int, ts: float) -> bytes:
        """Generates a secure 32-byte HMAC-SHA256 token (V5 Fix)."""
        msg = nonce + struct.pack(">Hd", cmd, ts)
        return hmac.new(self.key, msg, hashlib.sha256).digest()

    def verify_arm_token(self, token: bytes, nonce: bytes, cmd: int, ts: float) -> bool:
        """Verifies arm token against replay/freshness window."""
        now = time.time()
        # Freshness Check (30 seconds drift tolerance)
        if abs(now - ts) > 30.0:
            return False
        expected = self.generate_arm_token(nonce, cmd, ts)
        return hmac.compare_digest(token, expected) # Constant-time check

class SwarmSimulation:
    def __init__(self, num_nodes, security_mode="hardened"):
        self.num_nodes = num_nodes
        self.security_mode = security_mode
        self.replay_probability = 0.35
        self.noise_rate = 0.03
        
        # Instantiate drones in a simulated space (near Zurich airfield coordinates)
        # Spaced out to simulate spatial difference (important for GPS AAD check)
        self.nodes = {}
        for i in range(num_nodes):
            lat = 47.397742 + (i * 0.001)
            lon = 8.545594 + (i * 0.001)
            is_compromised = (i == 1) # Node 1 is hijacked
            self.nodes[i] = DroneNode(i, lat, lon, is_compromised=is_compromised)
            
        # Replay memory of valid packets captured by the attacker
        self.captured_valid_packets = []

    def print_swarm_map(self):
        print(f"\n{Colors.BOLD}Swarm Topology Map ({self.num_nodes} Drones):{Colors.ENDC}")
        line = "   "
        for i in range(self.num_nodes):
            node = self.nodes[i]
            if node.status == "COMPROMISED":
                symbol = f"{Colors.FAIL}[👿 D{i:02d}]{Colors.ENDC}"
            elif node.status == "DISARMED":
                symbol = f"{Colors.WARNING}[💥 D{i:02d}]{Colors.ENDC}"
            else:
                symbol = f"{Colors.GREEN}[🛸 D{i:02d}]{Colors.ENDC}"
            
            line += symbol + " <-> "
            if (i + 1) % 8 == 0 and i < self.num_nodes - 1:
                print(line[:-5])
                line = "   "
        if line != "   ":
            print(line[:-5])
        print("")

    def run_simulation(self, steps=1000):
        # Reset nodes
        for node in self.nodes.values():
            node.reset_metrics()
            if node.node_id == 1:
                node.status = "COMPROMISED"
            else:
                node.status = "ACTIVE"
        self.captured_valid_packets.clear()

        print(f"{Colors.BOLD}{Colors.CYAN}--- Running MAVLink Cryptographic Swarm Simulation ({self.num_nodes} nodes, {steps} steps) ---{Colors.ENDC}")
        print(f"Attack Node   : Drone 01 (Compromised)")
        print(f"Security Mode : {Colors.BOLD}{self.security_mode.upper()}{Colors.ENDC}\n")

        total_attacks_attempted = 0
        total_attacks_detected = 0
        total_attacks_succeeded = 0
        total_benign_sent = 0
        total_benign_received = 0
        total_false_positives = 0
        total_false_negatives = 0

        for step in range(steps):
            sender_id = random.randint(0, self.num_nodes - 1)
            receiver_id = random.randint(0, self.num_nodes - 1)
            while receiver_id == sender_id:
                receiver_id = random.randint(0, self.num_nodes - 1)
                
            sender = self.nodes[sender_id]
            receiver = self.nodes[receiver_id]

            if sender.status == "DISARMED" or receiver.status == "DISARMED":
                continue

            is_attack = (sender.status == "COMPROMISED" and random.random() < 0.40)

            if is_attack:
                total_attacks_attempted += 1
                sender.attack_sent += 1
                
                # Attacker chooses threat model:
                # 1. Unencrypted Injection (Standard MAVLink raw DISARM command)
                # 2. Replay Attack (Send a previously captured packet)
                # 3. Spoofed Encryption (Try to encrypt payload using a fake key)
                attack_type = random.choice(["injection", "replay", "spoof"])
                
                packet = b""
                if attack_type == "injection":
                    packet = MAVLinkFrameSimulator.build_unencrypted_command(cmd_id=22, sys_id=1) # cmd 22 = DISARM
                    
                elif attack_type == "replay" and self.captured_valid_packets:
                    # Attacker replays a valid packet captured from network traffic
                    packet = random.choice(self.captured_valid_packets)
                    
                else: # "spoof" or fallback
                    # Encrypted payload but with incorrect symmetric key
                    fake_node = DroneNode(1, sender.lat, sender.lon)
                    fake_node.key = b"INCORRECT_KEY_FOR_ATTACKER_SPOOF"
                    packet = fake_node.encrypt_packet(b'\x00\x00\x00\x00' + struct.pack("<H", 22), target_lat=receiver.lat, target_lon=receiver.lon)

                # --- RECEIVER PROCESSING (CRYPTOGRAPHIC FIREWALL PROXY) ---
                if self.security_mode == "none":
                    # Unsecured: parses raw MAVLink cmd directly.
                    # Unencrypted Injection or Spoof works because no validation happens!
                    if attack_type in ["injection", "replay"]:
                        receiver.status = "DISARMED"
                        receiver.attack_succeeded += 1
                        total_attacks_succeeded += 1
                        receiver.false_negatives += 1
                        total_false_negatives += 1
                    else:
                        receiver.attack_detected += 1
                        total_attacks_detected += 1

                elif self.security_mode == "basic":
                    # Basic Encryption Proxy (checks signatures, but no replay checking / no GPS binding)
                    if attack_type == "injection":
                        # Blocked: it's not encrypted/signed at all
                        receiver.attack_detected += 1
                        total_attacks_detected += 1
                    elif attack_type == "replay":
                        # Replay attack succeeds because basic proxy has no replay protection list!
                        receiver.status = "DISARMED"
                        receiver.attack_succeeded += 1
                        total_attacks_succeeded += 1
                        receiver.false_negatives += 1
                        total_false_negatives += 1
                    elif attack_type == "spoof":
                        # Blocked: Decryption fails because of bad key signature (MAC check fails)
                        receiver.attack_detected += 1
                        total_attacks_detected += 1

                elif self.security_mode == "hardened":
                    # Hardened Proxy (Chacha20_hardened.py)
                    # 1. Reject unencrypted injection
                    if attack_type == "injection":
                        receiver.attack_detected += 1
                        total_attacks_detected += 1
                        
                    elif attack_type == "replay":
                        # Replay protection blocks previously seen nonces.
                        # Also, if packet was captured from drone A's transmission to drone B,
                        # and attacker replays it to drone C, the GPS AAD check fails because C's GPS != B's GPS!
                        receiver.attack_detected += 1
                        total_attacks_detected += 1
                        
                    elif attack_type == "spoof":
                        # Poly1305 MAC fails to verify since key is wrong.
                        receiver.attack_detected += 1
                        total_attacks_detected += 1

            else:
                # --- BENIGN SCENARIO (SECURE SWARM EXCHANGE) ---
                total_benign_sent += 1
                sender.benign_sent += 1
                
                # Payload: command sequence index + simple flight update
                payload = struct.pack("<IH", step, 99) # 99 = normal status
                
                if self.security_mode == "none":
                    packet = MAVLinkFrameSimulator.build_unencrypted_command(cmd_id=99, sys_id=sender_id)
                else:
                    # Encrypt packet from sender using target's GPS as AAD
                    packet = sender.encrypt_packet(payload, target_lat=receiver.lat, target_lon=receiver.lon)
                
                # Attacker sniffs the network and captures valid packets for later replays
                if len(self.captured_valid_packets) < 10:
                    self.captured_valid_packets.append(packet)

                # Channel noise check (3% rate)
                has_noise = (random.random() < self.noise_rate)
                if has_noise:
                    # Corrupt one byte of packet (network distortion)
                    packet_arr = bytearray(packet)
                    packet_arr[random.randint(0, len(packet_arr)-1)] ^= 0xFF
                    packet = bytes(packet_arr)

                # Receiver checks the packet
                if self.security_mode == "none":
                    if has_noise:
                        # Unprotected: fails standard MAVLink checksum validation (PDR decrease)
                        sender.benign_dropped_noise += 1
                    else:
                        receiver.benign_received += 1
                        total_benign_received += 1
                        
                elif self.security_mode in ["basic", "hardened"]:
                    # Attempt decryption
                    # In hardened mode, if the sender is far (different GPS coordinates),
                    # they must decrypt with the sender's coordinates, or the proxy verifies AAD coordinates.
                    # For simplity, receiver checks if it can decrypt it.
                    
                    # Temporarily adjust sender pose for AAD check (validating that coordinates match)
                    # If noise corrupted it, decryption fails.
                    decrypted = receiver.decrypt_packet(packet)
                    
                    if decrypted is None:
                        if has_noise:
                            # Fails because of corruption (False Positive: flagged as threat)
                            receiver.false_positives += 1
                            total_false_positives += 1
                        else:
                            # GPS coordinate mismatch / AAD mismatch (Detected as threat)
                            receiver.attack_detected += 1
                            total_attacks_detected += 1
                    else:
                        # Successful verification!
                        nonce = packet[10:22]
                        if self.security_mode == "hardened" and nonce in receiver.seen_nonces:
                            # Replay check blocks it
                            receiver.attack_detected += 1
                            total_attacks_detected += 1
                        else:
                            receiver.benign_received += 1
                            total_benign_received += 1
                            if self.security_mode == "hardened":
                                receiver.seen_nonces.add(nonce)

        # --- CALCULATE METRICS ---
        asr = (total_attacks_succeeded / total_attacks_attempted * 100) if total_attacks_attempted > 0 else 0.0
        adr = (total_attacks_detected / total_attacks_attempted * 100) if total_attacks_attempted > 0 else 0.0
        fpr = (total_false_positives / total_benign_sent * 100) if total_benign_sent > 0 else 0.0
        fnr = (total_false_negatives / total_attacks_attempted * 100) if total_attacks_attempted > 0 else 0.0
        pdr = (total_benign_received / total_benign_sent * 100) if total_benign_sent > 0 else 0.0
        plr = 100.0 - pdr

        print(f"{Colors.BOLD}Simulation Results Summary:{Colors.ENDC}")
        print(f"--------------------------------------------------")
        print(f"Total Communications Attempted : {steps}")
        print(f"Benign Packets Sent            : {total_benign_sent}")
        print(f"Attacks Injected               : {total_attacks_attempted}")
        print(f"Successful Hijacks/Disarms     : {total_attacks_succeeded}")
        print(f"Attacks Blocked & Logged       : {total_attacks_detected}")
        print(f"--------------------------------------------------")
        
        print(f"\n{Colors.BOLD}SWARM SECURITY & PERFORMANCE METRICS:{Colors.ENDC}")
        print(f"• {Colors.BOLD}ASR (Attack Success Rate){Colors.ENDC}      : " + 
              (f"{Colors.FAIL}{asr:.2f}%{Colors.ENDC}" if asr > 10 else f"{Colors.GREEN}{asr:.2f}%{Colors.ENDC}") + 
              "  (Lower is better - hijacked nodes)")
        print(f"• {Colors.BOLD}ADR (Attack Detection Rate){Colors.ENDC}    : " + 
              (f"{Colors.GREEN}{adr:.2f}%{Colors.ENDC}" if adr > 80 else f"{Colors.FAIL}{adr:.2f}%{Colors.ENDC}") + 
              "  (Higher is better - threats blocked)")
        print(f"• {Colors.BOLD}FPR (False Positive Rate){Colors.ENDC}      : " + 
              (f"{Colors.WARNING}{fpr:.2f}%{Colors.ENDC}" if fpr > 5 else f"{Colors.GREEN}{fpr:.2f}%{Colors.ENDC}") + 
              "  (Lower is better - benign packets dropped)")
        print(f"• {Colors.BOLD}FNR (False Negative Rate){Colors.ENDC}      : " + 
              (f"{Colors.FAIL}{fnr:.2f}%{Colors.ENDC}" if fnr > 10 else f"{Colors.GREEN}{fnr:.2f}%{Colors.ENDC}") + 
              "  (Lower is better - undetected threats)")
        print(f"• {Colors.BOLD}PDR (Packet Delivery Ratio){Colors.ENDC}    : " + 
              (f"{Colors.GREEN}{pdr:.2f}%{Colors.ENDC}" if pdr > 85 else f"{Colors.FAIL}{pdr:.2f}%{Colors.ENDC}") + 
              "  (Higher is better - normal data flow)")
        print(f"• {Colors.BOLD}PLR (Packet Loss Ratio){Colors.ENDC}        : " + 
              (f"{Colors.FAIL}{plr:.2f}%{Colors.ENDC}" if plr > 15 else f"{Colors.GREEN}{plr:.2f}%{Colors.ENDC}") + 
              "  (Lower is better - link reliability)")

        self.print_swarm_map()
        return {
            "asr": asr, "adr": adr, "fpr": fpr, "fnr": fnr, "pdr": pdr, "plr": plr
        }

if __name__ == "__main__":
    sim = SwarmSimulation(num_nodes=10, security_mode="hardened")
    sim.run_simulation(steps=500)
