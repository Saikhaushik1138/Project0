import os
import sys
import time
import hmac
import struct
import hashlib
import socket
import collections
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.exceptions import InvalidTag

_raw_key = os.environ.get("DRONE_CHACHA_KEY", "")
if not _raw_key:
    print("[FATAL] Set DRONE_CHACHA_KEY env var to a 32-byte hex string (64 hex chars).")
    print("        Generate one with:  python -c \"import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())\"")
    sys.exit(1)

try:
    KEY: bytes = bytes.fromhex(_raw_key)
    if len(KEY) != 32:
        raise ValueError
except ValueError:
    print("[FATAL] DRONE_CHACHA_KEY must be exactly 64 hex characters (32 bytes).")
    sys.exit(1)

IP         = "127.0.0.1"
PORT_GCS   = 14550
PORT_DRONE = 14540

CMD_ARM = 22


_RATE_WINDOW_SEC  = 30       # sliding window
_MAX_ATTEMPTS     = 3        # max ARM attempts in window
_LOCKOUT_SEC      = 300      # 5-minute lockout after exhaustion

_attempt_log: dict[str, collections.deque] = {}   # addr -> deque of timestamps
_lockout_until: dict[str, float]           = {}   # addr -> epoch unlock time

def _is_rate_limited(addr: str) -> bool:
    now = time.monotonic()

    if addr in _lockout_until:
        if now < _lockout_until[addr]:
            remaining = int(_lockout_until[addr] - now)
            print(f"[RATE] {addr} locked out for {remaining}s more")
            return True
        else:
            del _lockout_until[addr]

    dq = _attempt_log.setdefault(addr, collections.deque())
    cutoff = now - _RATE_WINDOW_SEC
    while dq and dq[0] < cutoff:
        dq.popleft()

    dq.append(now)

    if len(dq) > _MAX_ATTEMPTS:
        _lockout_until[addr] = now + _LOCKOUT_SEC
        print(f"[RATE] {addr} exceeded {_MAX_ATTEMPTS} attempts — locked out {_LOCKOUT_SEC}s")
        return True

    return False
def encrypt_payload(payload: bytes, lat: float, lon: float) -> tuple[bytes, bytes]:
    """
    Returns (nonce, ciphertext_with_tag).
    GPS coordinates bound as AAD — any tampering with position data
    causes MAC verification to fail on the receiver side.
    """
    nonce = os.urandom(12)                                    # V2 fix
    aad   = struct.pack(">dd", lat, lon)                      # V6 fix
    chacha = ChaCha20Poly1305(KEY)
    ct = chacha.encrypt(nonce=nonce, data=payload, associated_data=aad)  # V3 fix
    return nonce, ct

def decrypt_payload(nonce: bytes, ct: bytes, lat: float, lon: float) -> bytes | None:
    """
    Returns decrypted plaintext, or None if MAC verification fails.
    """
    aad = struct.pack(">dd", lat, lon)
    chacha = ChaCha20Poly1305(KEY)
    try:
        return chacha.decrypt(nonce=nonce, data=ct, associated_data=aad)
    except InvalidTag:
        return None                                           # MAC failed — drop


def generate_arm_token(nonce: bytes, cmd: int, ts: float) -> bytes:
    msg = nonce + struct.pack(">Hd", cmd, ts)
    return hmac.new(KEY, msg, hashlib.sha256).digest()        # 32 bytes

def verify_arm_token(token: bytes, nonce: bytes, cmd: int, ts: float,
                     tolerance_sec: float = 30.0) -> bool:
    now = time.time()
    if abs(now - ts) > tolerance_sec:
        print(f"[AUTH] Token timestamp too old/future: drift={abs(now-ts):.1f}s")
        return False
    expected = generate_arm_token(nonce, cmd, ts)
    return hmac.compare_digest(token, expected)              
_REPLAY_WINDOW = 1000   # remember last N nonces
_seen_nonces: collections.deque = collections.deque(maxlen=_REPLAY_WINDOW)
_seen_nonces_set: set = set()

def _check_replay(nonce: bytes) -> bool:
    """Returns True (= replay detected) if nonce was seen before."""
    if nonce in _seen_nonces_set:
        return True
    if len(_seen_nonces) == _REPLAY_WINDOW:
        evicted = _seen_nonces[0]
        _seen_nonces_set.discard(evicted)
    _seen_nonces.append(nonce)
    _seen_nonces_set.add(nonce)
    return False


def process_packet(data: bytes, lat: float, lon: float,
                   src_addr: str = "unknown") -> bytes | None:
    """
    Returns the (possibly rewritten) packet bytes to forward,
    or None to drop the packet silently.

    Wire format expected (encrypted MAVLink 2.0):
        [0]      MAVLink magic  0xFD
        [1]      payload_len    (encrypted payload length excluding 16-byte tag)
        [2..9]   MAVLink header fields (incompat_flags, compat_flags, seq,
                 sysid, compid, msgid[3])
        [10..21] nonce          12 bytes
        [22..]   ciphertext + 16-byte Poly1305 tag
    """
    MIN_LEN = 1 + 9 + 12 + 16   # magic + header + nonce + tag (zero-length payload)
    if len(data) < MIN_LEN:
        return None

    # Only handle MAVLink v2 frames
    if data[0] != 0xFD:
        return None

    # Extract nonce (bytes 10..21)
    nonce = data[10:22]
    if len(nonce) != 12:
        return None

    # V4 replay check — before decryption to save CPU
    if _check_replay(nonce):
        print(f"[SEC] Replay detected from {src_addr} — dropping")
        return None

    # V4 FIX: Decrypt + verify MAC before touching any field
    ciphertext = data[22:]
    plaintext  = decrypt_payload(nonce, ciphertext, lat, lon)
    if plaintext is None:
        print(f"[SEC] MAC verification FAILED from {src_addr} — dropping")
        return None

    # ---- safe to parse plaintext now ----
    if len(plaintext) < 4:
        return None

    msg_id = struct.unpack("<I", data[7:10] + b'\x00')[0] & 0xFFFFFF

    if msg_id == 76 and len(plaintext) >= 6:
        cmd = struct.unpack("<H", plaintext[4:6])[0]

        if cmd == CMD_ARM:
            # Rate-limit check (V5)
            if _is_rate_limited(src_addr):
                return None

            print(f"[OK] ARM command authenticated from {src_addr}")
            ts = time.time()

            # Build response token — full HMAC, not a 6-digit int
            resp_nonce, _ = encrypt_payload(b'', lat, lon)   # fresh nonce for response
            token = generate_arm_token(resp_nonce, CMD_ARM, ts)

            # Build authenticated response payload
            resp_payload = struct.pack(">d", ts) + token     # 8 + 32 = 40 bytes
            out_nonce, out_ct = encrypt_payload(resp_payload, lat, lon)

            # Re-assemble MAVLink 2.0 frame with encrypted payload
            header = (
                b'\xFD'                          # magic
                + struct.pack("B", len(out_ct))  # payload length
                + b'\x00\x00'                    # incompat/compat flags
                + b'\x01'                        # sequence
                + b'\xFF'                        # sysid
                + b'\xBE'                        # compid
                + b'\x02\xCB\x00'               # msg_id (custom)
            )
            return header + out_nonce + out_ct

    # Non-ARM packet: re-encrypt with a fresh nonce and forward
    out_nonce, out_ct = encrypt_payload(plaintext, lat, lon)
    header = data[:10]
    return header + out_nonce + out_ct
def main():
    print("[START] Hardened MAVLink proxy starting...")
    print(f"[OK]   Key loaded from environment ({len(KEY)} bytes)")

    drone_lat = 47.397742
    drone_lon = 8.545594

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((IP, PORT_GCS))
        s.setblocking(False)
        drone_addr = (IP, PORT_DRONE)
        print(f"[OK]   Listening on {IP}:{PORT_GCS} → forwarding to {IP}:{PORT_DRONE}")
    except Exception as e:
        print(f"[ERR]  Socket error: {e}")
        run_demo()
        return

    while True:
        try:
            data, addr = s.recvfrom(4096)
            src = f"{addr[0]}:{addr[1]}"
            result = process_packet(data, drone_lat, drone_lon, src_addr=src)
            if result is not None:
                s.sendto(result, drone_addr)
        except BlockingIOError:
            pass
        time.sleep(0.001)

def run_demo():
    print("\n[DEMO] Running self-test...")
    lat, lon = 47.397742, 8.545594

    # Simulate an ARM command payload
    dummy_payload = struct.pack("<IIHH", 0, 0, CMD_ARM, 1)   # minimal COMMAND_LONG body
    nonce, ct = encrypt_payload(dummy_payload, lat, lon)
    print(f"[DEMO] Encrypted ARM payload: nonce={nonce.hex()[:16]}... ct_len={len(ct)}")

    # Verify decryption
    pt = decrypt_payload(nonce, ct, lat, lon)
    assert pt == dummy_payload, "Decryption mismatch!"
    print("[DEMO] Decrypt + MAC verify: PASSED")

    # Verify tampered ciphertext is rejected
    tampered = bytearray(ct)
    tampered[5] ^= 0xFF
    result = decrypt_payload(nonce, bytes(tampered), lat, lon)
    assert result is None, "Tamper detection failed!"
    print("[DEMO] Tamper detection: PASSED")

    # Verify replay detection
    assert not _check_replay(nonce), "First use should pass"
    assert _check_replay(nonce),     "Second use should be rejected"
    print("[DEMO] Replay detection: PASSED")

    # Verify ARM token HMAC
    ts = time.time()
    token = generate_arm_token(nonce, CMD_ARM, ts)
    assert verify_arm_token(token, nonce, CMD_ARM, ts), "Valid token rejected!"
    bad_token = bytes([b ^ 0x01 for b in token])
    assert not verify_arm_token(bad_token, nonce, CMD_ARM, ts), "Bad token accepted!"
    print("[DEMO] HMAC token generation + verification: PASSED")

    # Verify stale token is rejected
    old_ts = time.time() - 60
    stale_token = generate_arm_token(nonce, CMD_ARM, old_ts)
    assert not verify_arm_token(stale_token, nonce, CMD_ARM, old_ts), "Stale token accepted!"
    print("[DEMO] Stale token rejection: PASSED")

    print("\n[DEMO] All tests passed. Set DRONE_CHACHA_KEY and run normally.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[EXIT] Shutting down.")
        sys.exit(0)
