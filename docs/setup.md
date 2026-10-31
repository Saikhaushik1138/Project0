# Setup and QGroundControl connection

## This workspace

The checkout is PX4 v1.15 lineage at `99c40407ff`, with existing local PX4
changes. Its executable is an Apple Silicon binary. Gazebo Harmonic 8.14.0,
QGroundControl 5.0.3, Python 3.13.14, and the Python runtime dependencies were
found locally. The environment activation scripts were repaired after the
folder moved from an older path. Use `python -m pip` inside this environment.

```bash
cd /Users/saikhaushik/UAV
source .venv/bin/activate
python -m swarm_security doctor
python -m unittest discover -s tests -v
```

See [validation](validation.md) for the actual integration checks and limits.
The native Mac Harmonic combination is this workspace's tested configuration;
PX4 v1.15's published macOS setup instructions primarily describe Gazebo Classic.

## Fresh environments

Install Python 3.10 or newer and the platform-appropriate PX4 build and Gazebo
dependencies. Use the official instructions for the selected PX4 revision:
[development environment](https://docs.px4.io/v1.15/en/dev_setup/dev_env.html) and
[Gazebo simulation](https://docs.px4.io/v1.15/en/sim_gazebo_gz/).
Linux is the usual reproducible environment for modern PX4 Gazebo simulation.
The launcher uses POSIX process groups and `fcntl`, so use Linux/WSL or macOS,
not native Windows Python.

From the repository root:

```bash
git submodule update --init --recursive
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-swarm.txt
# Also needed when rebuilding PX4, separate from this project's runtime:
python -m pip install -r Tools/setup/requirements.txt
make px4_sitl_default
python -m swarm_security doctor
```

Do not reuse this Mac's build binary on Linux. If the checkout has moved and
CMake reports a stale source path, move `build/px4_sitl_default` to a backup
location and build again. Do not move PX4's source directories into new parents.
`scripts/setup_swarm.sh` automates only the Python environment and doctor check;
it does not install operating-system packages or build PX4.

## Keys and first run

```bash
python -m swarm_security keygen --drones 64
python -m swarm_security launch --drones 2 --security chacha20 \
  --keys config/keys.local.json
```

Keys are generated with OS randomness, stored with owner-only permissions, and
ignored by Git. There are no default shared development keys in the supported
code. Preserve a key file if you want to reuse the same experiment credentials.
Generate a new file at a different `--output` path to create a separate set.

## QGroundControl

Start QGroundControl on the same machine. Enable automatic UDP connection on
port **14550**. Each vehicle's decrypted telemetry arrives from a distinct
`127.0.0.1:21000+i` source, where `i` starts at zero. QGroundControl can reply
to those learned endpoints. For an explicit UDP Comm Link, set local port
14550 and add those target endpoints. Avoid creating a second connection that
also binds 14550. Do not add direct PX4 18570 targets when comparing the protected
path. See the official [Comm Links guide](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/settings_view/comm_links.html).

Select the active vehicle in QGroundControl to inspect or operate it. Multiple
vehicles appearing in QGroundControl does not provide a coordinated swarm
mission or formation controller. The launcher only spawns vehicles.

MAVProxy or another GCS must not compete with QGroundControl for UDP 14550.
The included headless smoke client also needs that port, so close QGroundControl
before using it. A manually configured GCS must send from local UDP 14550 because
the relay validates its configured peer endpoint.

## Troubleshooting

- **Port unavailable:** stop the earlier experiment in its own terminal. The
  launcher deliberately does not kill unrelated PX4, Gazebo, or Ruby processes.
- **Gazebo starts but no heartbeats:** inspect `runs/<run>/gazebo_server.log`,
  `instance_*/px4.log`, and `relay.log`. A startup timeout exits with failure.
- **No QGC vehicles:** check automatic UDP, local 14550, firewall rules, and that
  another GCS is not using the port. Inspect `relay_status.json` and packet
  counters to distinguish PX4 startup from GCS delivery.
- **Keys missing or invalid:** run `keygen` and pass the file with `--keys`.
- **Large swarm startup:** use headless mode and a longer startup timeout;
  review CPU/memory and Gazebo real-time factor before reporting throughput.
- **Plain `make ... gz_x500`:** this uses the original PX4 startup configuration,
  not the project's relay. Use the unified launcher for security comparisons.

No GUI application is launched by `doctor` or the test suite.
