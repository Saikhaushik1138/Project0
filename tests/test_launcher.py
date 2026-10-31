"""Checks for experiment isolation, port allocation and startup configuration."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_security import launcher


class LauncherTests(unittest.TestCase):
    def test_large_swarm_has_unique_ports_system_ids_and_positions(self):
        plan = launcher.make_plan(launcher.parser().parse_args(["--drones", "64"]))
        ports, poses, systems = [], set(), set()
        for vehicle in plan["vehicles"]:
            ports.extend(vehicle[field] for field in (
                "px4_port", "relay_ingress", "qgc_reply_port", "vehicle_tunnel_port", "gcs_tunnel_port"))
            poses.add(vehicle["pose"])
            systems.add(vehicle["system_id"])
        self.assertEqual(len(ports), len(set(ports)))
        self.assertEqual(len(poses), 64)
        self.assertEqual(systems, set(range(1, 65)))
        self.assertNotIn(14550, ports)  # QGC owns this socket.

    def test_invalid_sizes_and_durations_are_rejected(self):
        for argv in (["--drones", "0"], ["--drones", "65"], ["--drones", "2.5"],
                     ["--duration", "0"], ["--duration", "nan"], ["--duration", "inf"],
                     ["--spacing", "-1"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    launcher.parser().parse_args(argv)

    def test_dry_run_never_checks_runtime_or_launches(self):
        with patch.object(launcher, "run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launcher.main(["--drones", "16", "--security", "chacha20", "--dry-run"]), 0)
            run.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["drones"], 16)

    def test_overlay_keeps_build_resources_and_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "build/px4_sitl_default/etc"
            generated.mkdir(parents=True)
            (generated / "generated_config").write_text("retained")
            relative_paths = ("init.d-posix/rcS", "init.d-posix/px4-rc.simulator",
                              "init.d-posix/airframes/4001_gz_x500")
            for relative in relative_paths:
                source = root / "ROMFS/px4fmu_common" / relative
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("current source")
                stale = generated / relative
                stale.parent.mkdir(parents=True, exist_ok=True)
                stale.write_text("stale build")
            original = generated / "init.d-posix/px4-rc.mavlink"
            original.write_text("original links")
            run = root / "run"
            run.mkdir()
            overlay = launcher.prepare_romfs(run, root)
            self.assertEqual(original.read_text(), "original links")
            self.assertEqual((overlay / "generated_config").read_text(), "retained")
            self.assertEqual((overlay / "init.d-posix/rcS").read_text(), "current source")
            script = (overlay / "init.d-posix/px4-rc.mavlink").read_text()
            starts = [line for line in script.splitlines() if line.startswith("mavlink start")]
            self.assertEqual(len(starts), 1)
            self.assertNotIn(" -f", starts[0])
            self.assertIn("-t 127.0.0.1", starts[0])
            self.assertIn("20000+px4_instance", script)
            self.assertIn("param set MAV_0_BROADCAST 0", script)

    def test_readiness_requires_all_expected_heartbeat_system_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            self.assertEqual(launcher.observed_systems(path), set())
            path.write_text("{partial")
            self.assertEqual(launcher.observed_systems(path), set())
            path.write_text(json.dumps({"heartbeat_system_ids": [1, 2]}))
            self.assertEqual(launcher.observed_systems(path), {1, 2})
            self.assertFalse({1, 2, 3} <= launcher.observed_systems(path))


if __name__ == "__main__":
    unittest.main()
