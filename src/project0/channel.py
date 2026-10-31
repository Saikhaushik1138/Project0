"""Versioned AEAD envelope. This is not the MAVLink wire format."""

import os
import re
import struct
from collections import OrderedDict

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

MAGIC = b"P0SC"
VERSION = 1
HEADER = struct.Struct("!4sBH")
NONCE_SIZE = 12
TAG_SIZE = 16
MAX_PAYLOAD = 4096


class PacketError(ValueError):
    """Malformed, unauthenticated, or recently replayed envelope."""


def load_key(variable: str = "DRONE_CHACHA_KEY") -> bytes:
    """Load exactly 32 bytes of hex key material without import-time effects."""
    raw = os.environ.get(variable, "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        raise ValueError(f"{variable} must contain exactly 64 hexadecimal characters")
    return bytes.fromhex(raw)


class SecureChannel:
    """Single-threaded, single-peer research channel with bounded replay memory.

    Both peers must agree on context bytes. Use separate keys per direction.
    Replay protection ends on cache eviction or process restart.
    """

    def __init__(self, key: bytes, *, context: bytes, replay_capacity: int = 1024):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("key must be 32 bytes")
        if not isinstance(context, bytes) or not context:
            raise ValueError("context must be non-empty bytes")
        if not isinstance(replay_capacity, int) or replay_capacity < 1:
            raise ValueError("replay_capacity must be a positive integer")
        self._cipher = ChaCha20Poly1305(key)
        self._context = context
        self._capacity = replay_capacity
        self._seen: OrderedDict[bytes, None] = OrderedDict()

    def seal(self, payload: bytes) -> bytes:
        """Encrypt opaque bytes and authenticate the envelope header and context."""
        if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD:
            raise ValueError(f"payload must be bytes, at most {MAX_PAYLOAD} bytes")
        header = HEADER.pack(MAGIC, VERSION, len(payload))
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self._cipher.encrypt(nonce, payload, header + self._context)
        return header + nonce + ciphertext

    def open(self, packet: bytes) -> bytes:
        """Return authenticated plaintext; invalid packets never change replay state."""
        minimum = HEADER.size + NONCE_SIZE + TAG_SIZE
        if not isinstance(packet, bytes) or not minimum <= len(packet) <= minimum + MAX_PAYLOAD:
            raise PacketError("invalid packet size")
        header = packet[:HEADER.size]
        magic, version, length = HEADER.unpack(header)
        if magic != MAGIC or version != VERSION or len(packet) != minimum + length:
            raise PacketError("invalid header or declared length")
        nonce = packet[HEADER.size:HEADER.size + NONCE_SIZE]
        ciphertext = packet[HEADER.size + NONCE_SIZE:]
        try:
            plaintext = self._cipher.decrypt(nonce, ciphertext, header + self._context)
        except InvalidTag as exc:
            raise PacketError("authentication failed") from exc
        if nonce in self._seen:
            raise PacketError("replayed packet")
        self._seen[nonce] = None
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
        return plaintext
