"""Summarize Gazebo world statistics without confusing update rate with GUI FPS."""
import argparse
import json
import re
from pathlib import Path


def summarize(text):
    # Text-format protobuf stats repeat in the stream without an outer delimiter.
    # Every message contains sim_time before real_time and iterations.
    records = []
    chunks = re.split(r"(?=\bsim_time\s*\{)", text)
    for chunk in chunks:
        def seconds(field):
            match = re.search(r"\b" + field + r"\s*\{([^}]*)\}", chunk)
            if not match:
                return None
            values = dict(re.findall(r"\b(sec|nsec)\s*:\s*(-?\d+)", match[1]))
            return int(values.get("sec", 0)) + int(values.get("nsec", 0)) / 1e9
        sim, real = seconds("sim_time"), seconds("real_time")
        it = re.search(r"\biterations\s*:\s*(\d+)", chunk)
        if sim is not None and real is not None and it:
            records.append((sim, real, int(it[1])))
    if not records:
        raise ValueError("No complete Gazebo stats records found")
    start, end = records[0], records[-1]
    elapsed_sim, elapsed_real = end[0] - start[0], end[1] - start[1]
    iterations = end[2] - start[2]
    reset = any(b[0] < a[0] or b[1] < a[1] or b[2] < a[2] for a, b in zip(records, records[1:]))
    if reset:
        raise ValueError("Stats contain a clock/iteration reset; analyze each simulation separately")
    return dict(samples=len(records), final_sim_seconds=end[0], final_real_seconds=end[1],
                final_iterations=end[2], observed_sim_seconds=elapsed_sim,
                observed_real_seconds=elapsed_real,
                real_time_factor=elapsed_sim / elapsed_real if elapsed_real > 0 else None,
                physics_updates_per_real_second=iterations / elapsed_real if elapsed_real > 0 else None,
                simulation_step_ms=elapsed_sim * 1000 / iterations if iterations > 0 else None,
                note="Physics updates and RTF are not rendering FPS. Rates use first-to-last observed samples.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = summarize(args.input.read_text())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output, end="")
    return 0
