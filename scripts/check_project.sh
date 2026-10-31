#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  "") SIMULATION_CHECK=0 ;;
  --with-simulation) SIMULATION_CHECK=1 ;;
  -h|--help)
    echo "Usage: scripts/check_project.sh [--with-simulation]"
    echo "Run project tests; optionally also check PX4/Gazebo prerequisites."
    exit 0 ;;
  *) echo "Unknown option: $1" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then echo "Expected at most one option" >&2; exit 2; fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${UAV_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON=python3; fi
"$PYTHON" -m unittest discover -s tests -v
if [[ "$SIMULATION_CHECK" -eq 1 ]]; then
  "$PYTHON" -m swarm_security doctor
fi
