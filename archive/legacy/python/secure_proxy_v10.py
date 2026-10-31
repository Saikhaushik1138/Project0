#!/usr/bin/env python3
import os
import sys
import json
import socket
import threading
import time

# --- Setup configuration and keys ---
keystore_json = os.environ.get("DRONE_KEYSTORE")
token_key_hex = os.environ.get("DRONE_GCS_TOKEN_KEY")
lat_val = os.environ.get("DRONE_LAT", "47.397742")
lon_val = os.environ.get("DRONE_LON", "8.545594")

# If keys are not set, generate static development keys
if not keystore_json or not token_key_hex:
    drone_key = "a1" * 32
    token_key = "b2" * 32
    keystore_json = json.dumps({"drone_A": drone_key})
    token_key_hex = token_key

os.environ["DRONE_KEYSTORE"] = keystore_json
os.environ["DRONE_GCS_TOKEN_KEY"] = token_key_hex
os.environ["DRONE_LAT"] = lat_val
os.environ["DRONE_LON"] = lon_val

# Import the ultra-hardened V10 implementation
import Chacha20_ultra_hardened_V10 as v10

# Configure the drone key in the live keystore
drone_keys_parsed = json.loads(keystore_json)
for k, v in drone_keys_parsed.items():
    v10._DRONE_KEYS[k] = bytes.fromhex(v)

# Port configuration
PORT_QGC_CMD       = 14560  # QGC sends unencrypted commands here
PORT_DRONE_ENC     = 14570  # Drone-side proxy receives encrypted commands here
PORT_GCS_ENC       = 14585  # GCS-side proxy receives encrypted telemetry here
PORT_PX4_TELEMETRY = 14590  # PX4 sends unencrypted telemetry here

PORT_QGC           = 14550  # QGC listens here
PORT_PX4           = 18570  # PX4 listens here

DRONE_ID = "drone_A"

print(f"[KEYS] Active drone_A key: {v10._DRONE_KEYS['drone_A'].hex()}")
print(f"[KEYS] Active token key: {token_key_hex}")

def encrypt_packet(packet: bytes) -> bytes:
    if len(packet) < 10:
        return packet
    header = packet[:10]
    payload = packet[10:]
    lat = float(os.environ["DRONE_LAT"])
    lon = float(os.environ["DRONE_LON"])
    nonce, ct, ts = v10.encrypt_payload(payload, lat, lon, header, DRONE_ID)
    return header + v10._encode_drone_id(DRONE_ID) + nonce + ts + ct

def decrypt_packet(packet: bytes) -> bytes | None:
    if len(packet) < v10._MIN_LEN:
        return None
    header = packet[:10]
    id_raw = packet[v10._HDR_DRONEID_OFF:v10._HDR_NONCE_OFF]
    nonce  = packet[v10._HDR_NONCE_OFF:v10._HDR_PKTTS_OFF]
    pkt_ts = packet[v10._HDR_PKTTS_OFF:v10._HDR_CT_OFF]
    ct     = packet[v10._HDR_CT_OFF:]
    
    d_id = v10._decode_drone_id(id_raw)
    lat = float(os.environ["DRONE_LAT"])
    lon = float(os.environ["DRONE_LON"])
    
    payload = v10.decrypt_payload(nonce, ct, lat, lon, header, pkt_ts, d_id)
    if payload is None:
        return None
    return header + payload

def gcs_proxy_loop():
    print(f"[Proxy GCS] Starting GCS-side proxy...")
    
    # gcs_sock listens on 14560 for unencrypted command packets from QGC
    # and is also used to send telemetry to QGC at 14550 so replies come back here
    gcs_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gcs_sock.bind(("0.0.0.0", PORT_QGC_CMD))
    
    # gcs_enc_sock listens on 14580 for encrypted telemetry from Drone-side proxy
    gcs_enc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gcs_enc_sock.bind(("0.0.0.0", PORT_GCS_ENC))
    
    # General output socket for forwarding to Drone-side proxy
    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    qgc_addr = ("127.0.0.1", PORT_QGC)
    
    def qgc_to_drone():
        nonlocal qgc_addr
        while True:
            try:
                data, addr = gcs_sock.recvfrom(4096)
                qgc_addr = (addr[0], PORT_QGC)
                enc = encrypt_packet(data)
                out_sock.sendto(enc, ("127.0.0.1", PORT_DRONE_ENC))
            except Exception as e:
                print(f"[Proxy GCS -> Drone Error] {e}")
                
    def drone_to_qgc():
        while True:
            try:
                data, addr = gcs_enc_sock.recvfrom(4096)
                dec = decrypt_packet(data)
                if dec:
                    gcs_sock.sendto(dec, qgc_addr)
            except Exception as e:
                print(f"[Proxy Drone -> GCS Error] {e}")
                
    t1 = threading.Thread(target=qgc_to_drone, daemon=True)
    t2 = threading.Thread(target=drone_to_qgc, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

def drone_proxy_loop():
    print(f"[Proxy Drone] Starting Drone-side proxy...")
    
    # drone_enc_sock listens on 14570 for encrypted commands from GCS-side proxy
    drone_enc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    drone_enc_sock.bind(("0.0.0.0", PORT_DRONE_ENC))
    
    # px4_tel_sock listens on 14590 for unencrypted telemetry from PX4
    px4_tel_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    px4_tel_sock.bind(("0.0.0.0", PORT_PX4_TELEMETRY))
    
    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def gcs_to_px4():
        while True:
            try:
                data, addr = drone_enc_sock.recvfrom(4096)
                dec = decrypt_packet(data)
                if dec:
                    px4_tel_sock.sendto(dec, ("127.0.0.1", PORT_PX4))
            except Exception as e:
                print(f"[Proxy GCS -> PX4 Error] {e}")
                
    def px4_to_gcs():
        while True:
            try:
                data, addr = px4_tel_sock.recvfrom(4096)
                enc = encrypt_packet(data)
                out_sock.sendto(enc, ("127.0.0.1", PORT_GCS_ENC))
            except Exception as e:
                print(f"[Proxy PX4 -> GCS Error] {e}")
                
    t1 = threading.Thread(target=gcs_to_px4, daemon=True)
    t2 = threading.Thread(target=px4_to_gcs, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

if __name__ == "__main__":
    t_gcs = threading.Thread(target=gcs_proxy_loop, daemon=True)
    t_drone = threading.Thread(target=drone_proxy_loop, daemon=True)
    t_gcs.start()
    t_drone.start()
    print("[Proxy] Bidirectional V10 Secure Proxy active and running.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Proxy] Exiting.")
