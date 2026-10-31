"""Local bidirectional PX4/QGroundControl relay with one isolated path per drone."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import selectors
import signal
import socket
import threading
import time

from pymavlink.dialects.v20 import common as mavlink

from .crypto import EnvelopeCodec, MAX_PAYLOAD, PacketRejected, load_keys

LOCALHOST = "127.0.0.1"


def _ensure_descriptor_limit(drones: int) -> None:
    """A 64-drone experiment needs more than macOS's common 256-fd limit."""
    try:
        import resource
    except ImportError:
        return
    required = 4 * drones + 128
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft == resource.RLIM_INFINITY or soft >= required:
        return
    if hard != resource.RLIM_INFINITY and hard < required:
        raise ValueError(f"file descriptor hard limit {hard} is too low; need at least {required}")
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (required, hard))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot raise file descriptor limit to {required}: {error}") from error


@dataclass(frozen=True)
class PortMap:
    px4: int
    px4_ingress: int
    gcs_source: int
    encrypted_vehicle: int
    encrypted_gcs: int
    qgc: int = 14550

    @classmethod
    def for_instance(cls, instance: int) -> "PortMap":
        return cls(18570 + instance, 20000 + instance, 21000 + instance,
                   22000 + instance, 23000 + instance)


@dataclass
class _Link:
    identity: int
    ports: PortMap
    sockets: dict[str, socket.socket] = field(default_factory=dict)
    codecs: dict[str, EnvelopeCodec] = field(default_factory=dict)
    parser: object = None
    tokens: float = 2000.0
    token_time: float = field(default_factory=time.monotonic)


def _write_json(path: Path | None, value: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


class Relay:
    """Own all four sockets on each local drone path.

    The source port at each edge is fixed. No unauthenticated datagram can change
    a route. This is a same-host experiment: processes with access to the host's
    plaintext PX4 ports remain outside the tunnel's protection.
    """

    def __init__(self, drones: int, security: str, keys: dict[int, bytes] | None = None,
                 *, port_maps: list[PortMap] | None = None,
                 ready_file: str | Path | None = None, status_file: str | Path | None = None,
                 metrics: str | Path | None = None):
        if not 1 <= drones <= 254 or security not in ("baseline", "hmac", "chacha20"):
            raise ValueError("invalid drone count or security profile")
        if security != "baseline" and (keys is None or not set(range(1, drones + 1)) <= keys.keys()):
            raise ValueError("keys are required for every drone in secured profiles")
        _ensure_descriptor_limit(drones)
        self.security = security
        self.selector = selectors.DefaultSelector()
        self.stop_event = threading.Event()
        self.ready_file = Path(ready_file) if ready_file else None
        self.status_file = Path(status_file) if status_file else None
        self.metrics_file = Path(metrics) if metrics else None
        self.started_at = time.time()
        self.heartbeats: dict[str, dict] = {}
        self.counts: Counter = Counter()
        self.links: list[_Link] = []
        self._last_report = 0.0
        self._closed = False
        mappings = port_maps or [PortMap.for_instance(i) for i in range(drones)]
        if len(mappings) != drones:
            raise ValueError("one port mapping is required per drone")
        all_bind_ports = [getattr(p, name) for p in mappings for name in
                          ("px4_ingress", "gcs_source", "encrypted_vehicle", "encrypted_gcs")]
        endpoint_ports = {p.px4 for p in mappings} | {p.qgc for p in mappings}
        if len(all_bind_ports) != len(set(all_bind_ports)) or set(all_bind_ports) & endpoint_ports:
            raise ValueError("relay and endpoint UDP ports must not overlap")
        if any(not 1 <= value <= 65535 for value in all_bind_ports + list(endpoint_ports)):
            raise ValueError("UDP ports must be in 1..65535")
        try:
            for index, ports in enumerate(mappings):
                link = _Link(index + 1, ports)
                self.links.append(link)
                link.parser = mavlink.MAVLink(None)
                link.parser.robust_parsing = True
                if security != "baseline":
                    for role, direction in (("command_send", "command"), ("command_receive", "command"),
                                            ("telemetry_send", "telemetry"), ("telemetry_receive", "telemetry")):
                        link.codecs[role] = EnvelopeCodec(keys[index + 1], index + 1, direction, security)
                for channel in ("px4_ingress", "gcs_source", "encrypted_vehicle", "encrypted_gcs"):
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    link.sockets[channel] = sock
                    sock.bind((LOCALHOST, getattr(ports, channel)))
                    sock.setblocking(False)
                    self.selector.register(sock, selectors.EVENT_READ, (link, channel))
            self.report(force=True)
            _write_json(self.ready_file, {"ready": True, "drones": drones, "security": security})
        except BaseException:
            self.close()
            raise

    def _observe(self, link: _Link, payload: bytes) -> None:
        try:
            messages = link.parser.parse_buffer(payload) or []
            for message in messages:
                if (message.get_type() == "HEARTBEAT" and message.get_srcSystem() == link.identity
                        and message.get_srcComponent() == 1 and message.autopilot == mavlink.MAV_AUTOPILOT_PX4):
                    new = str(link.identity) not in self.heartbeats
                    self.heartbeats[str(link.identity)] = {"instance": link.identity - 1, "received_at": time.time()}
                    if new:
                        self.report(force=True)
        except (ValueError, mavlink.MAVError):
            self.counts["observation_errors"] += 1

    def _process(self, link: _Link, channel: str, packet: bytes, source: tuple[str, int]) -> None:
        expected = {"px4_ingress": link.ports.px4, "gcs_source": link.ports.qgc,
                    "encrypted_vehicle": link.ports.encrypted_gcs,
                    "encrypted_gcs": link.ports.encrypted_vehicle}[channel]
        if source != (LOCALHOST, expected):
            self.counts["rejected_source"] += 1
            return
        if not packet:
            self.counts["rejected_length"] += 1
            return
        if channel in ("px4_ingress", "gcs_source") and len(packet) > MAX_PAYLOAD:
            self.counts["rejected_length"] += 1
            return
        try:
            if channel == "px4_ingress":
                wire = link.codecs["telemetry_send"].encode(packet) if link.codecs else packet
                link.sockets["encrypted_vehicle"].sendto(wire, (LOCALHOST, link.ports.encrypted_gcs))
                self.counts["telemetry_input_packets"] += 1
                self.counts["telemetry_plaintext_bytes"] += len(packet)
                self.counts["telemetry_wire_bytes"] += len(wire)
            elif channel == "gcs_source":
                wire = link.codecs["command_send"].encode(packet) if link.codecs else packet
                link.sockets["encrypted_gcs"].sendto(wire, (LOCALHOST, link.ports.encrypted_vehicle))
                self.counts["command_input_packets"] += 1
                self.counts["command_plaintext_bytes"] += len(packet)
                self.counts["command_wire_bytes"] += len(wire)
            else:
                # Bound expensive authentication work per drone, including
                # unauthenticated input. This does not claim network DoS safety.
                now = time.monotonic()
                link.tokens = min(2000.0, link.tokens + (now - link.token_time) * 1000)
                link.token_time = now
                if link.tokens < 1:
                    self.counts["rejected_rate"] += 1
                    return
                link.tokens -= 1
                direction = "command" if channel == "encrypted_vehicle" else "telemetry"
                plaintext = link.codecs[direction + "_receive"].decode(packet) if link.codecs else packet
                destination = link.ports.px4 if direction == "command" else link.ports.qgc
                outbound = "px4_ingress" if direction == "command" else "gcs_source"
                link.sockets[outbound].sendto(plaintext, (LOCALHOST, destination))
                self.counts[direction + "_delivered_packets"] += 1
                if direction == "telemetry":
                    self._observe(link, plaintext)
        except PacketRejected as error:
            self.counts["rejected_" + str(error)] += 1
        except (OSError, ValueError):
            self.counts["transport_errors"] += 1

    def report(self, force: bool = False) -> None:
        if not force and time.monotonic() - self._last_report < 1:
            return
        self._last_report = time.monotonic()
        _write_json(self.status_file, {"heartbeat_system_ids": sorted(int(i) for i in self.heartbeats),
                                      "heartbeats": self.heartbeats, "updated_at": time.time()})
        _write_json(self.metrics_file, {"security": self.security, "drones": len(self.links),
                                       "started_at": self.started_at, "updated_at": time.time(),
                                       "counts": dict(self.counts)})

    def run(self) -> None:
        try:
            while not self.stop_event.is_set():
                for selected, _ in self.selector.select(timeout=0.2):
                    try:
                        packet, source = selected.fileobj.recvfrom(65535)
                    except BlockingIOError:
                        continue
                    link, channel = selected.data
                    start = time.perf_counter_ns()
                    self._process(link, channel, packet, source)
                    self.counts["handler_calls"] += 1
                    self.counts["handler_nanoseconds"] += time.perf_counter_ns() - start
                self.report()
        finally:
            self.close()

    def stop(self) -> None:
        self.stop_event.set()

    def close(self) -> None:
        if self._closed:
            return
        for link in self.links:
            for sock in link.sockets.values():
                sock.close()
        self.selector.close()
        self.report(force=True)
        if self.ready_file:
            self.ready_file.unlink(missing_ok=True)
        self._closed = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drones", type=int, required=True)
    parser.add_argument("--security", choices=("baseline", "hmac", "chacha20"), required=True)
    parser.add_argument("--keys", type=Path)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--metrics", type=Path)
    args = parser.parse_args(argv)
    if args.security != "baseline" and args.keys is None:
        parser.error("--keys is required for hmac and chacha20")
    try:
        keys = load_keys(args.keys, args.drones) if args.keys else None
        relay = Relay(args.drones, args.security, keys, ready_file=args.ready_file,
                      status_file=args.status_file, metrics=args.metrics)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: relay.stop())
    print(f"Relay ready: {args.drones} drone(s), {args.security}, QGroundControl UDP 14550", flush=True)
    relay.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
