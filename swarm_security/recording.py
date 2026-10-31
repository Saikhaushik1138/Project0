"""Sample selected process CPU and memory; does not require root packet capture."""
import argparse
import json
import math
import time
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pids", type=int, nargs="+", required=True)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--output", type=Path, default=Path("runs/process_metrics.jsonl"))
    args = parser.parse_args(argv)
    if not all(math.isfinite(v) and v > 0 for v in (args.duration, args.interval)):
        parser.error("duration and interval must be finite and positive")
    import psutil
    processes = []
    for pid in dict.fromkeys(args.pids):
        if pid <= 0:
            parser.error("PIDs must be positive")
        try:
            proc = psutil.Process(pid)
            proc.cpu_percent()
            processes.append(proc)
        except psutil.Error as exc:
            parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        with args.output.open("x") as out:
            while time.monotonic() - start < args.duration:
                time.sleep(min(args.interval, max(0, args.duration - (time.monotonic() - start))))
                for proc in processes:
                    sample = dict(time_unix=time.time(), elapsed_seconds=time.monotonic() - start, pid=proc.pid)
                    try:
                        if not proc.is_running():
                            raise psutil.NoSuchProcess(proc.pid)
                        sample.update(name=proc.name(), cpu_percent=proc.cpu_percent(),
                                      rss_bytes=proc.memory_info().rss)
                    except psutil.Error as exc:
                        sample["error"] = str(exc)
                    out.write(json.dumps(sample) + "\n")
                out.flush()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        parser.error(str(exc))
    print(f"Saved process samples to {args.output}; CPU is per process and may exceed 100% across cores.")
    return 0
