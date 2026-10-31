"""In-memory protocol checks and timing; no sockets, flight, or SITL instances."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import statistics
import time

from pymavlink.dialects.v20 import common as mavlink

from .crypto import EnvelopeCodec, PacketRejected, generate_keys

SIZES = (1, 2, 4, 8, 16, 32, 64)
MODES = ("baseline", "hmac", "chacha20")
ATTACKS = ("replay", "tamper", "wrong_key", "raw_injection")


def heartbeat(drone_id: int, sequence: int) -> bytes:
    """Construct a genuine MAVLink 2 heartbeat, including the dialect CRC."""
    writer = mavlink.MAVLink(None, srcSystem=drone_id, srcComponent=1)
    writer.seq = sequence % 256
    return writer.heartbeat_encode(
        mavlink.MAV_TYPE_QUADROTOR, mavlink.MAV_AUTOPILOT_PX4, 0,
        sequence % (2**32), mavlink.MAV_STATE_STANDBY,
    ).pack(writer)


def validate_heartbeat(packet: bytes) -> bytes:
    """Require exactly one CRC-valid heartbeat, not an arbitrary byte string."""
    parser = mavlink.MAVLink(None)
    try:
        messages = parser.parse_buffer(packet)
    except (mavlink.MAVError, ValueError) as error:
        raise PacketRejected("mavlink_crc_or_framing") from error
    if (not messages or len(messages) != 1
            or messages[0].get_type() != "HEARTBEAT"
            or bytes(messages[0].get_msgbuf()) != packet):
        raise PacketRejected("expected_one_complete_heartbeat")
    return packet


def _percent(numerator: int, denominator: int) -> float | None:
    return 100.0 * numerator / denominator if denominator else None


def _timing(samples_ns: list[int]) -> dict:
    if not samples_ns:
        return {"samples": 0, "mean_us": None, "median_us": None,
                "p95_us": None, "min_us": None, "max_us": None}
    ordered = sorted(value / 1000.0 for value in samples_ns)
    return {
        "samples": len(ordered), "mean_us": statistics.mean(ordered),
        "median_us": statistics.median(ordered),
        "p95_us": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "min_us": ordered[0], "max_us": ordered[-1],
    }


def _profile(mode: str, keys: dict[int, bytes], schedule: list[int]) -> dict:
    # All endpoints exist before encoding; codec startup freshness is enforced.
    senders, receivers, forgers = {}, {}, {}
    if mode != "baseline":
        foreign_keys = generate_keys(len(keys))
        for identity, key in keys.items():
            arguments = {"drone_id": identity, "direction": "telemetry", "security": mode}
            senders[identity] = EnvelopeCodec(key, **arguments)
            receivers[identity] = EnvelopeCodec(key, **arguments)
            forgers[identity] = EnvelopeCodec(foreign_keys[identity], **arguments)

    def encode(identity, payload):
        return bytes(payload) if mode == "baseline" else senders[identity].encode(payload)

    def receive(identity, packet):
        plain = packet if mode == "baseline" else receivers[identity].decode(packet)
        return validate_heartbeat(plain)

    def attempt(identity, packet):
        started = time.perf_counter_ns()
        try:
            receive(identity, packet)
            accepted = True
        except PacketRejected:
            accepted = False
        return accepted, time.perf_counter_ns() - started

    counts = {name: {"attempts": 0, "accepted": 0, "rejected": 0}
              for name in ATTACKS}
    attack_times = {name: [] for name in ATTACKS}
    encode_times, decode_times = [], []
    sent = accepted = raw_bytes = wire_bytes = 0
    node_counts = {identity: 0 for identity in keys}
    for step, identity in enumerate(schedule):
        node_counts[identity] += 1
        payload = heartbeat(identity, step)
        started = time.perf_counter_ns()
        packet = encode(identity, payload)
        encode_times.append(time.perf_counter_ns() - started)
        delivered, elapsed = attempt(identity, packet)
        decode_times.append(elapsed)
        sent += 1
        accepted += int(delivered)
        raw_bytes += len(payload)
        wire_bytes += len(packet)

        # Fresh tamper probe: rejection cannot merely be caused by replaying
        # the accepted benign packet. Flip its checksum/tag, not its length.
        untouched = encode(identity, heartbeat(identity, step + len(schedule)))
        tampered = untouched[:-1] + bytes([untouched[-1] ^ 1])
        probes = {
            "replay": packet,
            "tamper": tampered,
            "raw_injection": heartbeat(identity, step + 2 * len(schedule)),
        }
        if mode != "baseline":
            probes["wrong_key"] = forgers[identity].encode(payload)
        for name, probe in probes.items():
            passed, duration = attempt(identity, probe)
            counts[name]["attempts"] += 1
            counts[name]["accepted" if passed else "rejected"] += 1
            attack_times[name].append(duration)

    for name, count in counts.items():
        count["applicable"] = name != "wrong_key" or mode != "baseline"
        count["acceptance_percent"] = _percent(count["accepted"], count["attempts"])
        count["rejection_percent"] = _percent(count["rejected"], count["attempts"])
        count["receive_timing"] = _timing(attack_times[name])
    return {
        "mode": mode, "nodes": len(keys), "steps": len(schedule),
        "node_trials": {str(identity): count for identity, count in node_counts.items()},
        "benign": {
            "sent": sent, "accepted": accepted, "rejected": sent - accepted,
            "acceptance_percent": _percent(accepted, sent),
            "false_rejection_percent": _percent(sent - accepted, sent),
        },
        "attacks": counts,
        "timing": {"encode": _timing(encode_times),
                   "decode_and_mavlink_validation": _timing(decode_times)},
        "wire": {
            "benign_plain_bytes": raw_bytes, "benign_wire_bytes": wire_bytes,
            "overhead_bytes": wire_bytes - raw_bytes,
            "mean_overhead_bytes_per_packet": (wire_bytes - raw_bytes) / sent if sent else None,
        },
    }


def run_benchmark(sizes=SIZES, steps: int = 100, seed: int = 7) -> dict:
    """Run actual protocol validation for each size with a shared schedule."""
    sizes = list(sizes)
    if not sizes or any(not isinstance(size, int) or isinstance(size, bool)
                        or not 1 <= size <= 64 for size in sizes):
        raise ValueError("sizes must contain vehicle counts between 1 and 64")
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    results = []
    for size in sizes:
        rng = random.Random(seed)
        # One node is a GCS-to-vehicle link; no distinct peer selection loop.
        schedule = [rng.randrange(1, size + 1) for _ in range(steps)]
        keys = generate_keys(size)
        results.extend(_profile(mode, keys, schedule) for mode in MODES)
    return {
        "schema_version": 1,
        "experiment": "in_memory_protocol_microbenchmark",
        "scope": "MAVLink heartbeat validation and transport-envelope acceptance; no sockets, PX4, Gazebo, or flight",
        "seed": seed, "sizes": sizes, "steps_per_size_and_mode": steps,
        "notes": [
            "Steps are total scheduled benign datagrams, not steps per vehicle; node_trials records actual coverage.",
            "Every mode uses the same seeded node schedule. Cryptographic keys and sessions use unseeded secure randomness.",
            "Attack success means receiver acceptance only, not command execution or a flight outcome.",
            "Baseline has no key, so wrong_key is not applicable and its rates are null.",
            "Replay repeats an accepted datagram; tamper changes a fresh datagram; raw injection is a CRC-valid plain heartbeat.",
            "All receivers validate complete MAVLink heartbeats after any envelope verification.",
            "Timing uses perf_counter_ns; encode excludes heartbeat creation and key setup; receive includes MAVLink parsing.",
            "Wire byte totals include benign datagrams only. Acceptance rates are not network PDR, RF behavior, or a security certification.",
        ],
        "results": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", choices=SIZES, default=list(SIZES))
    parser.add_argument("--steps", type=int, default=100, help="Total benign trials per size/mode (default: 100)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("runs/benchmark.json"))
    args = parser.parse_args(argv)
    if args.steps < 0:
        parser.error("--steps must be nonnegative")
    result = run_benchmark(args.sizes, args.steps, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"Protocol microbenchmark saved to {args.output}")
    print("This measures in-memory packet validation, not SITL or flight performance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
