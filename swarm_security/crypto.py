"""Authenticated datagram envelopes for local swarm security experiments.

This is a research tunnel protocol, not MAVLink signing or a flight controller
security implementation. Plain MAVLink datagrams are opaque payloads. Receivers
reject packets predating their startup; replay state is otherwise held in memory.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import struct
import time
from dataclasses import dataclass
from typing import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HEADER = struct.Struct("!4sBBH16sQd")
MAGIC = b"UAS1"
PROFILES = {"hmac": 1, "chacha20": 2}
DIRECTIONS = {"command": 0, "telemetry": 1}
MAX_PAYLOAD = 60000
WINDOW_SIZE = 256


class PacketRejected(ValueError):
    """A malformed, unauthenticated, stale, or replayed envelope."""


def generate_keys(count: int) -> dict[int, bytes]:
    if not 1 <= count <= 254:
        raise ValueError("drone count must be between 1 and 254")
    return {i: secrets.token_bytes(32) for i in range(1, count + 1)}


def save_keys(path: str | Path, keys: dict[int, bytes]) -> None:
    """Create a key file without overwriting an existing enrollment."""
    data = {"version": 1, "drones": {str(i): key.hex() for i, key in keys.items()}}
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def load_keys(path: str | Path, count: int | None = None) -> dict[int, bytes]:
    try:
        raw = json.loads(Path(path).read_text())
        if raw["version"] != 1 or not isinstance(raw["drones"], dict):
            raise ValueError
        keys = {}
        for identity, key in raw["drones"].items():
            number = int(identity)
            if str(number) != identity or not 1 <= number <= 254:
                raise ValueError
            decoded = bytes.fromhex(key)
            if len(decoded) != 32:
                raise ValueError
            keys[number] = decoded
        if not keys or len(set(keys.values())) != len(keys):
            raise ValueError("each drone needs its own distinct key")
        if count is not None:
            if not 1 <= count <= 254 or not set(range(1, count + 1)) <= keys.keys():
                raise ValueError("key file is missing a requested drone")
        return keys
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid key file: expected version 1 and distinct 32-byte hex keys under drones") from error


def _stable_clock() -> Callable[[], float]:
    wall, monotonic = time.time(), time.monotonic()
    return lambda: wall + time.monotonic() - monotonic


@dataclass
class _ReplayWindow:
    highest: int
    bitmap: int
    latest_timestamp: float


class EnvelopeCodec:
    """One drone, one direction, one profile, with independent sender/receiver state.

    Each sender chooses a random 128-bit session ID. HKDF binds session, drone,
    direction and profile; a monotonically increasing 64-bit counter forms the
    AEAD nonce. No key is reused across opposite directions. Authenticated replay
    windows tolerate 255 packets of reordering and fail closed at the session cap.
    Instantiate both endpoints before sending. Startup freshness assumes the
    same host clock, as used by this localhost-only relay.
    """

    def __init__(self, key: bytes, drone_id: int, direction: str, security: str,
                 *, clock: Callable[[], float] | None = None, max_age: float = 30.0,
                 max_sessions: int = 64):
        if len(key) != 32 or not 1 <= drone_id <= 254:
            raise ValueError("expected a 32-byte key and drone ID 1..254")
        if security not in PROFILES or direction not in DIRECTIONS:
            raise ValueError("unsupported profile or direction")
        if max_age <= 0 or max_sessions < 1:
            raise ValueError("invalid replay bounds")
        self.key = key
        self.drone_id = drone_id
        self.direction = DIRECTIONS[direction]
        self.security = security
        self.profile = PROFILES[security]
        self.clock = clock or _stable_clock()
        self.started_at = self.clock()
        self.max_age = max_age
        self.max_sessions = max_sessions
        self.session = secrets.token_bytes(16)
        self.counter = 0
        self._windows: dict[bytes, _ReplayWindow] = {}
        self._send_key = self._derive(self.session)

    def _derive(self, session: bytes) -> bytes:
        info = b"uav-swarm-envelope-v1" + struct.pack("!HBB", self.drone_id, self.direction, self.profile)
        return HKDF(algorithm=SHA256(), length=32, salt=session, info=info).derive(self.key)

    def encode(self, payload: bytes) -> bytes:
        if not payload or len(payload) > MAX_PAYLOAD:
            raise ValueError("payload must contain 1..60000 bytes")
        if self.counter >= 2**64:
            raise OverflowError("session counter exhausted; restart sender")
        counter = self.counter
        self.counter += 1
        header = HEADER.pack(MAGIC, self.profile, self.direction, self.drone_id,
                             self.session, counter, self.clock())
        if self.security == "hmac":
            body = header + payload
            return body + hmac.new(self._send_key, body, hashlib.sha256).digest()
        nonce = b"\x00" * 4 + struct.pack("!Q", counter)
        return header + ChaCha20Poly1305(self._send_key).encrypt(nonce, payload, header)

    def decode(self, packet: bytes) -> bytes:
        tag_size = 32 if self.security == "hmac" else 16
        if not HEADER.size + tag_size < len(packet) <= HEADER.size + tag_size + MAX_PAYLOAD:
            raise PacketRejected("length")
        header = packet[:HEADER.size]
        magic, profile, direction, identity, session, counter, timestamp = HEADER.unpack(header)
        if (magic, profile, direction, identity) != (MAGIC, self.profile, self.direction, self.drone_id):
            raise PacketRejected("context")
        now = self.clock()
        if not math.isfinite(timestamp) or timestamp < max(self.started_at, now - self.max_age) or timestamp > now + 5:
            raise PacketRejected("timestamp")
        # Authentication precedes all replay-state changes. Forged session IDs
        # cannot fill the bounded replay registry or burn legitimate counters.
        subkey = self._derive(session)
        if self.security == "hmac":
            if not hmac.compare_digest(packet[-32:], hmac.new(subkey, packet[:-32], hashlib.sha256).digest()):
                raise PacketRejected("authentication")
            payload = packet[HEADER.size:-32]
        else:
            nonce = b"\x00" * 4 + struct.pack("!Q", counter)
            try:
                payload = ChaCha20Poly1305(subkey).decrypt(nonce, packet[HEADER.size:], header)
            except InvalidTag as error:
                raise PacketRejected("authentication") from error
        self._windows = {sid: state for sid, state in self._windows.items()
                         if state.latest_timestamp >= now - self.max_age}
        state = self._windows.get(session)
        if state is None:
            if len(self._windows) >= self.max_sessions:
                raise PacketRejected("session_capacity")
            self._windows[session] = _ReplayWindow(counter, 1, timestamp)
        elif counter > state.highest:
            delta = counter - state.highest
            state.bitmap = ((state.bitmap << delta) | 1) & ((1 << WINDOW_SIZE) - 1) if delta < WINDOW_SIZE else 1
            state.highest = counter
            state.latest_timestamp = max(timestamp, state.latest_timestamp)
        else:
            delta = state.highest - counter
            if delta >= WINDOW_SIZE or state.bitmap & (1 << delta):
                raise PacketRejected("replay")
            state.bitmap |= 1 << delta
            state.latest_timestamp = max(timestamp, state.latest_timestamp)
        return payload
