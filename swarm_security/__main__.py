"""Project command line. Run from the repository root."""
import argparse
import importlib
import sys
from pathlib import Path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {
        "launch": "launcher", "relay": "relay", "doctor": "doctor",
        "benchmark": "benchmark", "analyze": "analysis", "record": "recording",
    }
    if argv and argv[0] in commands:
        module = importlib.import_module(f"swarm_security.{commands[argv[0]]}")
        return module.main(argv[1:])
    parser = argparse.ArgumentParser(description="PX4 swarm security research tools")
    subs = parser.add_subparsers(dest="command", required=True)
    for name in commands:
        subs.add_parser(name, help=f"See {name} --help")
    keys = subs.add_parser("keygen", help="Create private per-drone keys without overwriting")
    keys.add_argument("--drones", type=int, default=64)
    keys.add_argument("--output", type=Path, default=Path("config/keys.local.json"))
    args = parser.parse_args(argv)
    if args.command == "keygen":
        if not 1 <= args.drones <= 64:
            parser.error("--drones must be between 1 and 64")
        from .crypto import generate_keys, save_keys
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            save_keys(args.output, generate_keys(args.drones))
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Created {args.drones} per-drone keys: {args.output} (keep private)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
