# Setup and first run

Run commands from the repository root. The Python tools require Python 3.10 or
later. The launcher uses POSIX process groups and `fcntl`: use Linux, macOS, or
WSL rather than native Windows Python.

## 1. Install the Python tools

```bash
git clone https://github.com/Saikhaushik1138/Project0.git
cd Project0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m swarm_security launch --drones 4 --security chacha20 --dry-run
```

These checks do not require a simulator, vehicle, or graphical application.
`swarm-security` is also available after installation and accepts the same
subcommands as `python -m swarm_security`.
Use the editable checkout for simulation and `doctor`; installing the Python
wheel alone does not supply PX4 or the repository-relative simulator assets.

Runtime versions are pinned in `requirements-swarm.txt` and package metadata.
The helper `scripts/setup_swarm.sh` creates the local Python environment and
installs the research tools. It does not install operating-system packages or
build PX4. Use `scripts/check_project.sh` to run the project checks, and add
`--with-simulation` to include the full environment doctor. The doctor reports
missing simulator prerequisites and exits with a nonzero status until the SITL
environment is ready.

## 2. Prepare PX4 and Gazebo

Install the platform-appropriate PX4 build tools and Gazebo dependencies for
the selected PX4 revision. Follow the official [PX4 v1.15 development environment](https://docs.px4.io/v1.15/en/dev_setup/dev_env.html)
and [Gazebo simulation guide](https://docs.px4.io/v1.15/en/sim_gazebo_gz/).

```bash
git submodule update --init --recursive
git fetch --tags
# PX4 build dependencies are separate from the research tools' runtime.
python -m pip install -r Tools/setup/requirements.txt
make px4_sitl_default
python -m swarm_security doctor
```

The executable must be built for the current machine. Build products and
virtual environments are not included in a fresh checkout. Do not move PX4's
source directories into new parents: its build scripts expect their existing
locations. If a previously generated CMake build refers to another checkout,
back up `build/px4_sitl_default` and rebuild it.

See [checkout notes](github.md) for pinned submodules, the source snapshot
revision, the project version tag, and retained local patches.

## 3. Generate credentials and start a run

```bash
# Run once. The command refuses to overwrite an existing file.
python -m swarm_security keygen --drones 64
python -m swarm_security launch --drones 2 --security chacha20 \
  --keys config/keys.local.json
```

Keys use OS randomness and owner-only file permissions. The default key file is
excluded from Git. Keep it private, and reuse it for subsequent experiments.
Use a different `--output` path when generating another credential set.

The launcher starts Gazebo and waits for a heartbeat from every requested
vehicle. It does not automatically arm or fly them. Ctrl+C stops the processes
started for the run. For a timed headless check, append
`--headless --duration 10`; the duration begins after startup readiness.

Supported counts are 1–64. Capacity depends on the host and workload. Use
`--startup-timeout 300` when a larger experiment needs more initialization time,
and inspect CPU/memory and Gazebo real-time factor before drawing performance
conclusions.

## 4. Connect QGroundControl

Start QGroundControl on the same machine. Enable automatic UDP connection on
port **14550**. Each vehicle's decrypted telemetry arrives from a distinct
`127.0.0.1:21000+i` source, where `i` starts at zero. QGroundControl can reply
to those learned endpoints. For an explicit UDP Comm Link, set local port
14550 and add those target endpoints. Avoid creating a second connection that
also binds 14550. Do not add direct PX4 18570 targets when comparing the protected
path. See the official [Comm Links guide](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/settings_view/comm_links.html).

Select the active vehicle in QGroundControl to inspect it. Multiple vehicles
in QGroundControl do not provide a coordinated swarm mission or formation
controller; the launcher spawns independent vehicles.

MAVProxy or another GCS must not compete with QGroundControl for UDP 14550.
The included headless smoke client also needs that port, so close QGroundControl
before using it. A manually configured GCS must send from local UDP 14550 because
the relay validates its configured peer endpoint.

## 5. Review outputs and validate connectivity

Each experiment creates an isolated directory under `runs/` with a manifest,
PX4 and Gazebo logs, relay status, and packet counters. Keep the manifest with
any measurements reported from the run.

With QGroundControl closed, a protocol client can verify heartbeats and harmless
PING replies through the relay:

```bash
python scripts/smoke_sitl.py --drones 2 --security chacha20 \
  --keys config/keys.local.json
```

See [validation](validation.md) for retained historical results and their
limits. Running the project tests does not rebuild PX4 or reproduce a physical
flight experiment.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Port unavailable | Stop the earlier experiment in its own terminal; the launcher does not kill unrelated processes. |
| Gazebo starts without heartbeats | Inspect `gazebo_server.log`, `instance_*/px4.log`, and `relay.log` in the run directory. Startup timeout exits with failure. |
| No vehicles in QGroundControl | Check automatic UDP, port 14550, firewall rules, and competing GCS processes. Inspect `relay_status.json` and packet counters. |
| Missing or invalid keys | Generate a new key file and pass its path with `--keys`; do not overwrite credentials used by another run. |
| Large swarm starts slowly | Use headless mode, increase the startup timeout, and inspect host resources. |
| Stale CMake source path or incompatible binary | Back up local build output and rebuild for the current machine. |
| Direct `make ... gz_x500` behaves differently | That entry point uses ordinary PX4 startup; use the unified launcher for the research relay profiles. |

## Previously recorded environment

The retained 31 October 2026 validation used a native Apple Silicon PX4 binary,
Gazebo Harmonic 8.14.0, QGroundControl 5.0.3, and Python 3.13.14. This records the
original test environment; a fresh clone does not contain that machine's build
or virtual environment. See the [validation record](validation.md) before
comparing new results with those runs.
