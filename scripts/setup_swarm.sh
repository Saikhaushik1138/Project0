#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${UAV_PYTHON:-python3}"
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements-swarm.txt
.venv/bin/python -m swarm_security doctor
