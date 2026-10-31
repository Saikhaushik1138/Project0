#!/usr/bin/env bash
# Compatibility entry point: ./launch_swarm_gazebo.sh 4 --security chacha20 ...
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${UAV_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON=python3; fi
COUNT=1
if [[ $# -gt 0 && "$1" != -* ]]; then COUNT="$1"; shift; fi
exec "$PYTHON" -m swarm_security launch --drones "$COUNT" "$@"
