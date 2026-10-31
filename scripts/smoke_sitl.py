#!/usr/bin/env python3
"""Check real PX4 telemetry and PING replies through the experiment relay.

Close QGroundControl before running: this probe temporarily owns its UDP port.
It sends only GCS heartbeats and PING requests, never flight commands.
"""

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

from pymavlink.dialects.v20 import common as mavlink


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drones", type=int, default=2)
    parser.add_argument("--security", choices=("baseline", "hmac", "chacha20"), default="baseline")
    parser.add_argument("--keys", type=Path)
    parser.add_argument("--startup-timeout", type=float, default=120)
    args = parser.parse_args()
    if not 1 <= args.drones <= 64 or args.startup_timeout <= 0:
        parser.error("drones must be 1..64 and startup-timeout must be positive")
    endpoint = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        endpoint.bind(("127.0.0.1", 14550))
    except OSError as exc:
        endpoint.close()
        parser.exit(1, f"Cannot bind QGC UDP 14550: {exc}. Close QGroundControl before this check.\n")
    endpoint.settimeout(0.2)
    output = ROOT / "runs" / ("smoke_" + time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    command = [sys.executable, "-m", "swarm_security.launcher", "--drones", str(args.drones),
               "--security", args.security, "--headless", "--duration", "5",
               "--startup-timeout", str(args.startup_timeout)]
    if args.keys:
        command += ["--keys", str(args.keys.resolve())]
    parsers = {}
    encoder = mavlink.MAVLink(None, srcSystem=255, srcComponent=190)
    heartbeats, replies = set(), set()
    started = time.monotonic()
    deadline = started + args.startup_timeout * 2 + args.drones * 3 + 30
    timed_out = False
    process = None
    try:
        with (output / "launcher.log").open("w") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    timed_out = True
                    process.terminate()
                    break
                try:
                    packet, address = endpoint.recvfrom(65535)
                except socket.timeout:
                    continue
                if address[0] != "127.0.0.1" or not 21000 <= address[1] < 21000 + args.drones:
                    continue
                decoder = parsers.setdefault(address, mavlink.MAVLink(None))
                decoder.robust_parsing = True
                for message in decoder.parse_buffer(packet) or []:
                    identity = message.get_srcSystem()
                    if identity != address[1] - 21000 + 1:
                        continue
                    if message.get_type() == "HEARTBEAT" and message.get_srcComponent() == 1:
                        heartbeats.add(identity)
                        endpoint.sendto(encoder.heartbeat_encode(mavlink.MAV_TYPE_GCS,
                                        mavlink.MAV_AUTOPILOT_INVALID, 0, 0,
                                        mavlink.MAV_STATE_ACTIVE).pack(encoder), address)
                        endpoint.sendto(encoder.ping_encode(time.time_ns() // 1000, identity,
                                                            0, 0).pack(encoder), address)
                    elif message.get_type() == "PING" and message.target_system == 255 and message.target_component == 190:
                        if message.seq == identity:
                            replies.add(identity)
            try:
                code = process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    finally:
        endpoint.close()
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
    expected = set(range(1, args.drones + 1))
    report = {"security": args.security, "drones": args.drones,
              "heartbeat_system_ids": sorted(heartbeats), "ping_reply_system_ids": sorted(replies),
              "launcher_exit_code": code, "timed_out": timed_out,
              "passed": code == 0 and heartbeats == expected and replies == expected,
              "elapsed_seconds": round(time.monotonic() - started, 3)}
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"Evidence: {output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
