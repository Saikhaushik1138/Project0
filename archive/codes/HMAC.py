import time
import hmac
import hashlib
import struct
import socket
import sys

KEY = b"MySuperSecretSymmetricKey123_FC"

IP = "127.0.0.1"
PORT_GCS = 14550    
PORT_DRONE = 14540  

CMD_ARM = 22

def get_otp(lat, lon):
    t_step = int(time.time() / 30)
    
    lat_grid = int(round(lat, 3) * 1000)
    lon_grid = int(round(lon, 3) * 1000)
    
    payload = struct.pack(">iii", lat_grid, lon_grid, t_step)
    
    h = hmac.new(KEY, msg=payload, digestmod=hashlib.sha256)
    digest = h.digest()
    
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset+4])[0] & 0x7FFFFFFF
    otp = code % 1000000
    
    return otp

def process_packet(data, lat, lon):
    if len(data) < 12:
        return data

    if data[0] == 0xFD:
        msg_id = struct.unpack("<I", data[7:10] + b'\x00')[0] & 0xFFFFFF
        
        if msg_id == 76:
            cmd = struct.unpack("<H", data[30:32])[0]
            
            if cmd == CMD_ARM:
                print(f"Intercepted ARM command!")
                token = get_otp(lat, lon)
                print(f"Generated Token: {token:06d}")
                
                magic = b'\xFD'
                length = b'\x06'            
                flags1 = b'\x00'
                flags2 = b'\x00'
                seq = b'\x01'                  
                sys_id = b'\xFF'               
                comp_id = b'\xBE'              
                msg_id_bytes = b'\x02\xCB\x00'  
                
                payload = struct.pack("<IH", token, CMD_ARM)
                
                header_payload = length + flags1 + flags2 + seq + sys_id + comp_id + msg_id_bytes + payload
                
                crc = 0xFFFF
                for b in header_payload:
                    tmp = b ^ (crc & 0xFF)
                    tmp ^= (tmp << 4) & 0xFF
                    crc = (crc >> 8) ^ (tmp << 8) ^ (tmp << 1) ^ (tmp << 4)
                crc_bytes = struct.pack("<H", crc & 0xFFFF)
                
                return magic + header_payload + crc_bytes
                
    return data

def main():
    print("Proxy starting...")
    
    drone_lat = 47.397742
    drone_lon = 8.545594
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((IP, PORT_GCS))
        s.setblocking(False)
        drone_addr = (IP, PORT_DRONE)
        print("Listening for packets...")
    except Exception as e:
        print(f"Socket error: {e}")
        print("Running fallback demo:")
        run_demo()
        return

    while True:
        try:
            data, addr = s.recvfrom(4096)
            new_data = process_packet(data, drone_lat, drone_lon)
            s.sendto(new_data, drone_addr)
        except BlockingIOError:
            pass
            
        time.sleep(0.001)

def run_demo():
    lat, lon = 47.3977, 8.5455
    print(f"Testing with Lat={lat}, Lon={lon}")
    token = get_otp(lat, lon)
    print(f"Result Token: {token:06d}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
