# Validation on 31 October 2026

The reorganized code passed **25 project tests** and real native PX4/Gazebo
smoke runs. The integration tests used a MAVLink client on QGroundControl's
UDP port, received vehicle heartbeats, and requested harmless PING replies
through each vehicle's relay. No arm, takeoff, or flight commands were sent.

## Native simulation checks

| Profile | Vehicles | Heartbeat system IDs | PING reply system IDs | Result |
| --- | --- | --- | --- | --- |
| Baseline | 2 | 1, 2 | 1, 2 | Passed, exit 0 |
| HMAC | 2 | 1, 2 | 1, 2 | Passed, exit 0 |
| ChaCha20-Poly1305 | 2 | 1, 2 | 1, 2 | Passed, exit 0 |
| ChaCha20-Poly1305 | 4 | 1, 2, 3, 4 | 1, 2, 3, 4 | Passed, exit 0 |

All owned relay, PX4, and Gazebo processes exited cleanly. Runs lasted five
seconds after readiness; elapsed startup-plus-run time was approximately
16.6–17.2 seconds. These are connectivity smoke tests, not sustained performance
or flight validation. An initial test exposed a PX4 CLI incompatibility with
explicit `-m normal`; the corrected launcher uses PX4's implicit normal mode.

Machine-readable results and evidence locations are retained in
[data/validation/2026-10-31.json](../data/validation/2026-10-31.json).
Detailed logs, per-run manifests, benchmark output, and vehicle ULog files are
retained in [the uploaded evidence directory](../data/validation/session-2026-10-31/).
Their byte-for-byte copy checksums are listed in
[evidence-manifest.json](../data/validation/session-2026-10-31/evidence-manifest.json).
The original local outputs remain under `runs/` on this machine.

To repeat a check, close QGroundControl so the probe can bind UDP 14550:

```bash
.venv/bin/python scripts/smoke_sitl.py --drones 4 --security chacha20 \
  --keys config/keys.local.json
```

## Project tests and protocol benchmark

The tests cover authenticated packet round trips, wrong keys and contexts,
tampering, replays, out-of-order packets, freshness, bounded replay state,
private key creation, actual two-drone UDP routing, invalid startup arguments,
unique 64-vehicle ports and poses, isolated ROMFS setup, and Gazebo timing analysis.

The in-memory benchmark used sizes **1, 2, 4, 8, 16, 32, 64**, three profiles,
and 100 scheduled benign datagrams per size/profile. It observed:

- 2,100 out of 2,100 benign packets accepted.
- 5,600 protected attack probes rejected by HMAC/ChaCha20 receivers.
- Baseline accepted 1,400 replay/raw-injection probes, as expected without
  authentication or replay protection.
- All 2,100 tamper probes failed CRC or authentication checks.

These probes use real cryptographic verification and MAVLink parsing. They
measure packet acceptance in memory, not disarm success, network delivery,
RF behavior, or swarm flight performance. The retained
[benchmark.json](../data/validation/session-2026-10-31/benchmark.json) contains the
full denominators, node sampling counts, measured timings, and byte overhead.

## Repository integrity

SHA256 verification matched all **340 retained original files** against the
reorganization manifest, including files inside the build-residue archive.
One bytecode-cache file listed in the move manifest was subsequently removed
as reproducible data and is recorded as such. The original staged Git diff is
unchanged. No preexisting PX4 source modifications were overwritten.

The environment doctor found a runnable native Apple Silicon PX4 binary,
Gazebo Sim 8.14.0, and the required Python packages. QGroundControl 5.0.3 was
found installed. Shell syntax, Python compilation, local documentation links,
and private-key Git exclusions were checked.

## Remaining validation limits

QGroundControl's graphical interface was not opened during testing. Its
standard UDP interface was exercised with the protocol client. No 8–64 vehicle
Gazebo workload, sustained flight, hardware vehicle, fresh OS installation,
full PX4 rebuild, or remote CI run was performed. The existing native build was
used. Larger sizes are supported in configuration and tested at the protocol
level, with actual simulation capacity still dependent on the host.

This is a trusted-host research transport. The [security boundary](architecture.md)
explains raw PX4 ports and plaintext endpoints. Historical manuscript results
were not reclassified as newly reproduced measurements.
