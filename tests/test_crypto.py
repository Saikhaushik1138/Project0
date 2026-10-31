import json
import os
from pathlib import Path
import tempfile
import unittest

from swarm_security.crypto import EnvelopeCodec, PacketRejected, generate_keys, load_keys, save_keys


class CryptoTests(unittest.TestCase):
    def pair(self, mode, *, max_sessions=64):
        key = os.urandom(32)
        now = [1000.0]
        clock = lambda: now[0]
        tx = EnvelopeCodec(key, 1, "command", mode, clock=clock)
        rx = EnvelopeCodec(key, 1, "command", mode, clock=clock, max_sessions=max_sessions)
        return key, now, tx, rx

    def test_independent_endpoints_roundtrip_and_profile_visibility(self):
        payload = b"opaque MAVLink datagram including headers, checksums and signatures"
        for mode in ("hmac", "chacha20"):
            with self.subTest(mode=mode):
                _, _, tx, rx = self.pair(mode)
                packet = tx.encode(payload)
                self.assertEqual(rx.decode(packet), payload)
                self.assertEqual(payload in packet, mode == "hmac")
                with self.assertRaisesRegex(PacketRejected, "replay"):
                    rx.decode(packet)

    def test_forged_packet_cannot_burn_counter_or_fill_registry(self):
        for mode in ("hmac", "chacha20"):
            with self.subTest(mode=mode):
                _, _, tx, rx = self.pair(mode)
                packet = tx.encode(b"test")
                tampered = packet[:-1] + bytes([packet[-1] ^ 1])
                for _ in range(100):
                    with self.assertRaisesRegex(PacketRejected, "authentication"):
                        rx.decode(tampered)
                self.assertEqual(len(rx._windows), 0)
                self.assertEqual(rx.decode(packet), b"test")

    def test_wrong_identity_direction_and_key_rejected(self):
        for mode in ("hmac", "chacha20"):
            key, now, tx, _ = self.pair(mode)
            recipients = [EnvelopeCodec(key, 2, "command", mode, clock=lambda: now[0]),
                          EnvelopeCodec(key, 1, "telemetry", mode, clock=lambda: now[0]),
                          EnvelopeCodec(os.urandom(32), 1, "command", mode, clock=lambda: now[0])]
            packet = tx.encode(b"hello")
            for recipient in recipients:
                with self.assertRaises(PacketRejected):
                    recipient.decode(packet)

    def test_reordering_and_window_bounds(self):
        for mode in ("hmac", "chacha20"):
            _, _, tx, rx = self.pair(mode)
            packets = [tx.encode(bytes([i % 256])) for i in range(300)]
            self.assertEqual(rx.decode(packets[299]), bytes([299 % 256]))
            self.assertEqual(rx.decode(packets[298]), bytes([298 % 256]))
            with self.assertRaisesRegex(PacketRejected, "replay"):
                rx.decode(packets[0])
            tx.counter = 2**63
            self.assertEqual(rx.decode(tx.encode(b"large counter")), b"large counter")
            self.assertLessEqual(next(iter(rx._windows.values())).bitmap.bit_length(), 256)

    def test_session_capacity_fails_closed_then_expires(self):
        for mode in ("hmac", "chacha20"):
            key, now, tx, rx = self.pair(mode, max_sessions=1)
            other = EnvelopeCodec(key, 1, "command", mode, clock=lambda: now[0])
            original = tx.encode(b"first")
            rx.decode(original)
            with self.assertRaisesRegex(PacketRejected, "session_capacity"):
                rx.decode(other.encode(b"new session"))
            with self.assertRaisesRegex(PacketRejected, "replay"):
                rx.decode(original)
            now[0] += 31
            self.assertEqual(rx.decode(other.encode(b"fresh")), b"fresh")
            self.assertEqual(len(rx._windows), 1)
            with self.assertRaisesRegex(PacketRejected, "timestamp"):
                rx.decode(original)

    def test_receiver_restart_and_clock_bounds(self):
        for mode in ("hmac", "chacha20"):
            key, now, tx, rx = self.pair(mode)
            old = tx.encode(b"old")
            now[0] += 1
            restarted = EnvelopeCodec(key, 1, "command", mode, clock=lambda: now[0])
            with self.assertRaisesRegex(PacketRejected, "timestamp"):
                restarted.decode(old)
            self.assertEqual(restarted.decode(tx.encode(b"new")), b"new")
            tx.clock = lambda: now[0] + 60
            with self.assertRaisesRegex(PacketRejected, "timestamp"):
                rx.decode(tx.encode(b"future"))

    def test_malformed_and_size_limits(self):
        for mode in ("hmac", "chacha20"):
            _, _, tx, rx = self.pair(mode)
            for data in (b"", b"UAS1", b"x" * 65000):
                with self.assertRaises(PacketRejected):
                    rx.decode(data)
            for data in (b"", b"x" * 60001):
                with self.assertRaises(ValueError):
                    tx.encode(data)
            self.assertEqual(rx.decode(tx.encode(b"x" * 60000)), b"x" * 60000)

    def test_keys_distinct_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keys.json"
            keys = generate_keys(3)
            self.assertEqual(len(set(keys.values())), 3)
            save_keys(path, keys)
            self.assertEqual(load_keys(path, 3), keys)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                save_keys(path, generate_keys(3))
            with self.assertRaises(ValueError):
                load_keys(path, 4)
            raw = json.loads(path.read_text())
            raw["drones"]["2"] = raw["drones"]["1"]
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                load_keys(path)


if __name__ == "__main__":
    unittest.main()
