# UAV swarm security research

PX4 and Gazebo simulation with multiple vehicles, QGroundControl telemetry,
and selectable MAVLink transport protection. This repository contains the PX4
source tree plus the project's own code in `swarm_security/`.

The original report, slides, scripts, and measurements are preserved. The
current workflow replaces inconsistent launch scripts with one launcher and
tests the actual transport in both directions.

## Start here

Run from this folder. The existing `.venv` has the required dependencies on this
Mac. On a fresh machine, follow [setup](docs/setup.md) first.

```bash
source .venv/bin/activate
python -m swarm_security doctor
test -f config/keys.local.json || python -m swarm_security keygen --drones 64
python -m swarm_security launch --drones 4 --security chacha20 --keys config/keys.local.json
```

The first-run command creates private keys only when they are absent. Keys are
kept locally and are never included in the GitHub upload. `keygen` refuses to
overwrite existing keys. Open
QGroundControl with its automatic UDP connection enabled on **14550**. The
launcher waits for vehicle heartbeats before announcing readiness. It does not
arm or fly vehicles automatically. Ctrl+C stops the processes started by that
run. A GUI launch starts Gazebo's interface; add `--headless` to omit it.

For the unprotected and authentication-only comparisons:

```bash
python -m swarm_security launch --drones 4 --security baseline
python -m swarm_security launch --drones 4 --security hmac --keys config/keys.local.json
```

Sizes **1–64** are accepted, including the study's 1, 4, 8, 16, 32, and 64.
Available CPU, memory, and simulator performance determine practical limits.
Use `--startup-timeout 300` when a larger swarm needs longer to initialize.
Configuration support for 64 vehicles is not a measured 64-vehicle performance
guarantee. See [validation](docs/validation.md) for what was actually exercised.

## Security layers

| Profile | Protected transport | Confidentiality | Replay checks |
| --- | --- | --- | --- |
| `baseline` | Ordinary MAVLink through the same relay topology | No | No |
| `hmac` | HMAC-SHA256 authenticated envelope | No | Yes |
| `chacha20` | ChaCha20-Poly1305 authenticated envelope | Yes | Yes |

Each drone has a separate key and separate ports. The relays preserve complete
MAVLink datagrams so PX4 and QGroundControl exchange ordinary MAVLink at their
endpoints. This is a **local transport experiment**. The trusted host still has
plaintext endpoints, and the stock PX4 UDP socket is not a firewall. See the
[architecture and trust boundary](docs/architecture.md).

The [research mapping](docs/research.md) explains the original case numbering and
which manuscript features have implementations. GPS anti-spoofing, X25519
exchange, persistent revocation, and formation control are not provided by the
three supported profiles.

## Project layout

| Location | Purpose |
| --- | --- |
| `swarm_security/` | Current launcher, transport, diagnostics, benchmarks, and analysis |
| `scripts/` | Environment setup and verification helpers |
| `config/` | Configuration notes and locally generated private keys |
| `tests/` | Tests for this project's code; PX4's original tests remain in `test/` |
| `docs/references/` | Original Word research paper and PowerPoint presentation |
| `docs/` | Setup, architecture, research mapping, validation, and cleanup records |
| `data/recordings/` | Original timestamped measurements |
| `data/historical/` | Original logs, parameter snapshot, and telemetry logs |
| `runs/` | New isolated run directories, manifests, logs, and metrics; Git-ignored |
| `archive/legacy/` | Original scripts retained for reference |
| `archive/previous-github/` | The earlier GitHub research package, preserved before this upload |
| `archive/automation/` | Inactive upstream and Gemini workflows retained for reference |
| `archive/reorganization/` | Move checksums, original Git diffs, and generated-file recovery archive |
| `src/`, `ROMFS/`, `Tools/`, `boards/`, `platforms/`, `cmake/` | PX4 source/build inputs, retained in PX4's required locations |
| `build/` | Existing PX4 build outputs, retained for use |

The original PX4 README is preserved at [docs/px4_upstream_readme.md](docs/px4_upstream_readme.md).
The upstream PX4 license and contribution files remain at the root.

## Check and measure

```bash
# Project tests, including real UDP routing tests
python -m unittest discover -s tests -v

# Inspect a 64-vehicle port/position plan without launching anything
python -m swarm_security launch --drones 64 --security chacha20 --dry-run

# Short simulation run, without a GUI or automatic flight
python -m swarm_security launch --drones 2 --security chacha20 \
  --keys config/keys.local.json --headless --duration 10

# In-memory protocol tests across sizes; these are not flight measurements
python -m swarm_security benchmark --sizes 1 4 8 16 32 64 \
  --steps 100 --seed 7 --output runs/benchmark.json

# Analyze actual recorded Gazebo timing
python -m swarm_security analyze data/recordings/20260715_062734/gazebo_stats.log
```

Each simulation run saves `manifest.json`, PX4 instance logs, Gazebo logs,
relay heartbeat status, and packet counters. `--duration` measures time after
startup readiness. The manifest records the owned process PIDs. Sample selected
PIDs with `python -m swarm_security record --pids 123 456 --duration 60`.
Replace the example PIDs with those from your run. This records process CPU
and memory without requiring privileged packet capture.

The retained `./launch_swarm_gazebo.sh 4 ...` entry point forwards to the new
launcher. Archived launchers are historical source and are not supported entry
points. See [reorganization](docs/reorganization.md) for the exact file mapping.

See [GitHub checkout notes](docs/github.md) for cloning with PX4 submodules and
the files intentionally kept local.
