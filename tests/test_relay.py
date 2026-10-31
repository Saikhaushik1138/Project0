import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from pymavlink.dialects.v20 import common as mavlink

from swarm_security.crypto import generate_keys
from swarm_security.relay import LOCALHOST, PortMap, Relay


def udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCALHOST, 0))
    sock.settimeout(2)
    return sock


def heartbeat(identity, *, v1=False):
    encoder = mavlink.MAVLink(None, srcSystem=identity, srcComponent=1)
    message = encoder.heartbeat_encode(mavlink.MAV_TYPE_QUADROTOR, mavlink.MAV_AUTOPILOT_PX4,
                                       0, 0, mavlink.MAV_STATE_STANDBY)
    return message.pack(encoder, force_mavlink1=v1)


class RelayTests(unittest.TestCase):
    def launch(self, mode, count=1, directory=None):
        qgc = udp_socket()
        vehicles = [udp_socket() for _ in range(count)]
        reserved = [udp_socket() for _ in range(4 * count)]
        maps = [PortMap(vehicles[i].getsockname()[1],
                        *(sock.getsockname()[1] for sock in reserved[4*i:4*i+4]),
                        qgc=qgc.getsockname()[1]) for i in range(count)]
        for sock in reserved:
            sock.close()
        options = {}
        if directory:
            options = {"ready_file": Path(directory) / "ready.json",
                       "status_file": Path(directory) / "status.json",
                       "metrics": Path(directory) / "metrics.json"}
        relay = Relay(count, mode, generate_keys(count), port_maps=maps, **options)
        thread = threading.Thread(target=relay.run)
        thread.start()
        def cleanup():
            relay.stop()
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            qgc.close()
            for sock in vehicles:
                sock.close()
        self.addCleanup(cleanup)
        return relay, qgc, vehicles, maps

    def test_real_udp_two_drone_roundtrip_all_profiles(self):
        for mode in ("baseline", "hmac", "chacha20"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                relay, qgc, vehicles, maps = self.launch(mode, 2, directory)
                for index in range(2):
                    payload = heartbeat(index + 1, v1=True) + heartbeat(index + 1)
                    vehicles[index].sendto(payload, (LOCALHOST, maps[index].px4_ingress))
                    received, source = qgc.recvfrom(65535)
                    self.assertEqual(received, payload)
                    self.assertEqual(source, (LOCALHOST, maps[index].gcs_source))
                    # Opaque bytes model the full MAVLink frame including any
                    # signature trailer; the relay must never rewrite them.
                    command = b"\xfd\x21opaque-command-with-signature" + bytes([index])
                    qgc.sendto(command, source)
                    response, sender = vehicles[index].recvfrom(65535)
                    self.assertEqual(response, command)
                    self.assertEqual(sender, (LOCALHOST, maps[index].px4_ingress))
                relay.stop()
                deadline = time.monotonic() + 3
                while not relay._closed and time.monotonic() < deadline:
                    time.sleep(0.01)
                status = json.loads((Path(directory) / "status.json").read_text())
                self.assertEqual(status["heartbeat_system_ids"], [1, 2])
                self.assertFalse((Path(directory) / "ready.json").exists())
                metrics = json.loads((Path(directory) / "metrics.json").read_text())
                self.assertEqual(metrics["counts"]["command_delivered_packets"], 2)

    def test_authentication_and_replay_enforced_on_real_udp(self):
        for mode in ("hmac", "chacha20"):
            with self.subTest(mode=mode):
                relay, _, vehicles, maps = self.launch(mode)
                link = relay.links[0]
                packet = link.codecs["command_send"].encode(b"accepted exactly once")
                wire = link.sockets["encrypted_gcs"]
                destination = (LOCALHOST, maps[0].encrypted_vehicle)
                wire.sendto(packet[:-1] + bytes([packet[-1] ^ 1]), destination)
                wire.sendto(packet, destination)
                wire.sendto(packet, destination)
                self.assertEqual(vehicles[0].recvfrom(65535)[0], b"accepted exactly once")
                vehicles[0].settimeout(0.25)
                with self.assertRaises(socket.timeout):
                    vehicles[0].recvfrom(65535)
                self.assertEqual(relay.counts["rejected_authentication"], 1)
                self.assertEqual(relay.counts["rejected_replay"], 1)

    def test_unknown_source_cannot_change_route(self):
        relay, qgc, vehicles, maps = self.launch("baseline")
        attacker = udp_socket()
        self.addCleanup(attacker.close)
        attacker.sendto(b"wrong sender", (LOCALHOST, maps[0].gcs_source))
        qgc.sendto(b"correct sender", (LOCALHOST, maps[0].gcs_source))
        self.assertEqual(vehicles[0].recvfrom(65535)[0], b"correct sender")
        self.assertEqual(relay.counts["rejected_source"], 1)

    def test_wrong_system_heartbeat_does_not_satisfy_readiness(self):
        relay, qgc, vehicles, maps = self.launch("baseline")
        vehicles[0].sendto(heartbeat(2), (LOCALHOST, maps[0].px4_ingress))
        qgc.recvfrom(65535)
        self.assertEqual(relay.heartbeats, {})


if __name__ == "__main__":
    unittest.main()
