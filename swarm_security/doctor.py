"""Read-only environment diagnostics; never installs software or starts vehicles."""
import argparse
import importlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_environment():
    checks = []

    def add(name, ok, detail, required=True):
        checks.append(dict(name=name, ok=bool(ok), required=required, detail=str(detail)))

    add("Python", sys.version_info >= (3, 10), sys.version.split()[0])
    for name in ("cryptography", "pymavlink", "psutil"):
        try:
            mod = importlib.import_module(name)
            add(name, True, getattr(mod, "__version__", "installed"))
        except ImportError as exc:
            add(name, False, exc)
    for name in ("cmake", "ninja", "make", "gz"):
        add(name, shutil.which(name), shutil.which(name) or "not on PATH")
    px4 = ROOT / "build/px4_sitl_default/bin/px4"
    add("PX4 SITL binary", px4.is_file(), px4)
    if px4.is_file():
        try:
            result = subprocess.run([str(px4), "-h"], capture_output=True, timeout=10)
            add("PX4 can execute", result.returncode == 0,
                "native executable works" if result.returncode == 0 else result.stderr.decode(errors="replace")[-500:])
        except (OSError, subprocess.TimeoutExpired) as exc:
            add("PX4 can execute", False, exc)
    for name in ("models/x500/model.sdf", "worlds/default.sdf"):
        path = ROOT / "Tools/simulation/gz" / name
        add("Gazebo " + name, path.is_file(), path)
    if shutil.which("gz"):
        try:
            result = subprocess.run(["gz", "sim", "--versions"], capture_output=True, text=True, timeout=15)
            add("Gazebo Sim", result.returncode == 0, result.stdout.strip() or result.stderr.strip())
        except (OSError, subprocess.TimeoutExpired) as exc:
            add("Gazebo Sim", False, exc)
    qgc = Path("/Applications/QGroundControl.app")
    add("QGroundControl", qgc.exists() or shutil.which("QGroundControl") or shutil.which("qgroundcontrol"),
        str(qgc) if qgc.exists() else "Optional for headless tests; install separately", required=False)
    cfg = ROOT / "build/px4_sitl_default/CMakeCache.txt"
    if cfg.exists():
        lines = cfg.read_text(errors="replace").splitlines()
        cached = next((x.split("=", 1)[1] for x in lines if x.startswith("CMAKE_HOME_DIRECTORY:INTERNAL=")), "")
        add("Build location", cached == str(ROOT), cached)
    return dict(platform=platform.platform(), repository=str(ROOT), checks=checks,
                ok=all(c["ok"] for c in checks if c["required"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = inspect_environment()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for row in report["checks"]:
            status = "OK" if row["ok"] else "MISSING" if row["required"] else "OPTIONAL"
            print(f"{status:8s} {row['name']}: {row['detail']}")
        print("A successful doctor check does not replace a simulation smoke test.")
    return 0 if report["ok"] else 1
