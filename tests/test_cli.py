"""Test user-facing command dispatch and key-file handling in fresh processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from swarm_security import __version__


class CliTests(unittest.TestCase):
    def command(self, *arguments):
        return subprocess.run(
            [sys.executable, '-m', 'swarm_security', *arguments],
            capture_output=True, text=True, timeout=15,
        )

    def test_version_and_subcommand_help(self):
        result = self.command('--version')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(__version__, result.stdout)
        for command in ('launch', 'relay', 'doctor', 'benchmark', 'analyze', 'record', 'keygen'):
            with self.subTest(command=command):
                result = self.command(command, '--help')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_keygen_creates_private_distinct_keys_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'keys.json'
            arguments = ('keygen', '--drones', '2', '--output', str(path))
            result = self.command(*arguments)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = path.read_bytes()
            data = json.loads(original)
            self.assertEqual(set(data['drones']), {'1', '2'})
            self.assertNotEqual(data['drones']['1'], data['drones']['2'])
            if os.name == 'posix':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            result = self.command(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Created', result.stdout)
            self.assertEqual(path.read_bytes(), original)

    def test_invalid_drone_count_does_not_create_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'keys.json'
            result = self.command('keygen', '--drones', '65', '--output', str(path))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
