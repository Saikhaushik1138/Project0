import os
import unittest
from unittest.mock import patch

from project0 import PacketError, SecureChannel, load_key
from project0.channel import MAX_PAYLOAD


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))
        self.sender = SecureChannel(self.key, context=b'test/gcs-to-uav')
        self.receiver = SecureChannel(self.key, context=b'test/gcs-to-uav')

    def test_round_trip_boundaries(self):
        for payload in (b'', b'telemetry', bytes(range(256)), b'x' * MAX_PAYLOAD):
            with self.subTest(size=len(payload)):
                packet = self.sender.seal(payload)
                self.assertEqual(len(packet), len(payload) + 35)
                self.assertEqual(self.receiver.open(packet), payload)

    def test_every_byte_is_protected(self):
        packet = self.sender.seal(b'flight telemetry')
        for i in range(len(packet)):
            with self.subTest(byte=i):
                changed = bytearray(packet)
                changed[i] ^= 1
                with self.assertRaises(PacketError):
                    self.receiver.open(bytes(changed))
        self.assertEqual(self.receiver.open(packet), b'flight telemetry')

    def test_wrong_key_and_context(self):
        packet = self.sender.seal(b'hello')
        for key, context in [(b'x' * 32, b'test/gcs-to-uav'), (self.key, b'other-direction')]:
            with self.assertRaises(PacketError):
                SecureChannel(key, context=context).open(packet)

    def test_replay_rejected(self):
        packet = self.sender.seal(b'hello')
        self.receiver.open(packet)
        with self.assertRaisesRegex(PacketError, 'replayed'):
            self.receiver.open(packet)

    def test_invalid_packet_does_not_poison_cache(self):
        packet = self.sender.seal(b'valid')
        forged = packet[:-1] + bytes([packet[-1] ^ 1])
        with self.assertRaises(PacketError):
            self.receiver.open(forged)
        self.assertEqual(self.receiver.open(packet), b'valid')

    def test_truncation_and_extra_bytes(self):
        packet = self.sender.seal(b'hello')
        for candidate in [packet[:i] for i in range(len(packet))] + [packet + b'x', b'x' * 5000]:
            with self.assertRaises(PacketError):
                self.receiver.open(candidate)

    def test_documented_cache_eviction_limit(self):
        receiver = SecureChannel(self.key, context=b'test/gcs-to-uav', replay_capacity=1)
        first, second = self.sender.seal(b'1'), self.sender.seal(b'2')
        receiver.open(first)
        receiver.open(second)
        self.assertEqual(receiver.open(first), b'1')

    def test_invalid_input(self):
        for key in (b'', b'x' * 31, b'x' * 33, 'x' * 32):
            with self.assertRaises(ValueError):
                SecureChannel(key, context=b'test')
        for capacity in (0, -1, 1.5):
            with self.assertRaises(ValueError):
                SecureChannel(self.key, context=b'test', replay_capacity=capacity)
        with self.assertRaises(ValueError):
            SecureChannel(self.key, context=b'')
        with self.assertRaises(ValueError):
            self.sender.seal(b'x' * (MAX_PAYLOAD + 1))
        with self.assertRaises(ValueError):
            self.sender.seal('text')

    def test_key_environment_validation(self):
        for value in ('', 'z' * 64, 'a' * 63, 'aa ' * 32):
            with patch.dict(os.environ, {'DRONE_CHACHA_KEY': value}):
                with self.assertRaises(ValueError):
                    load_key()
        with patch.dict(os.environ, {'DRONE_CHACHA_KEY': self.key.hex()}):
            self.assertEqual(load_key(), self.key)

    def test_fresh_nonce_each_message(self):
        self.assertNotEqual(self.sender.seal(b'same'), self.sender.seal(b'same'))


if __name__ == '__main__':
    unittest.main()
