"""Exercise the demo through the same process boundary as the documented CLI."""
import os
import subprocess
import sys
import unittest


class CliTests(unittest.TestCase):
    def test_demo_with_and_without_optimization(self):
        environment = dict(os.environ, DRONE_CHACHA_KEY=bytes(range(32)).hex())
        for flags in ([], ["-O"]):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, *flags, "-m", "project0", "demo"],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.count("PASS:"), 3)

    def test_demo_rejects_missing_key(self):
        environment = dict(os.environ)
        environment.pop("DRONE_CHACHA_KEY", None)
        result = subprocess.run(
            [sys.executable, "-m", "project0", "demo"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("DRONE_CHACHA_KEY", result.stderr)
        self.assertNotIn("PASS:", result.stdout)
