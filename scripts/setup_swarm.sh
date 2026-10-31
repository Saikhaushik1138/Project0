#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${UAV_PYTHON:-python3}"
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m swarm_security --version
echo "Python tools installed. Activate with: source .venv/bin/activate"
echo "Run scripts/check_project.sh for project tests."
echo "For simulation setup, follow docs/setup.md and run: python -m swarm_security doctor"
