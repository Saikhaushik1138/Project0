"""Protocol acceptance checks against the actual parser and envelope codecs."""

import json
from pathlib import Path
import tempfile
import unittest

from swarm_security.benchmark import heartbeat, main, run_benchmark, validate_heartbeat
from swarm_security.crypto import PacketRejected


class BenchmarkTests(unittest.TestCase):
    def test_baseline_requires_crc_valid_complete_heartbeat(self):
        packet = heartbeat(1, 7)
        self.assertEqual(validate_heartbeat(packet), packet)
        malformed = [packet[:-1], packet + b"extra", packet + packet,
                     packet[:-1] + bytes([packet[-1] ^ 1]), b"arbitrary data"]
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(PacketRejected):
                validate_heartbeat(data)

    def test_profiles_exercise_real_packet_acceptance_for_one_and_64_nodes(self):
        result = run_benchmark([1, 64], steps=20, seed=7)
        self.assertEqual(len(result["results"]), 6)
        for record in result["results"]:
            with self.subTest(mode=record["mode"], nodes=record["nodes"]):
                self.assertEqual(record["benign"]["accepted"], 20)
                self.assertEqual(record["attacks"]["tamper"]["rejected"], 20)
                self.assertEqual(record["timing"]["encode"]["samples"], 20)
                self.assertGreater(record["timing"]["decode_and_mavlink_validation"]["mean_us"], 0)
                if record["mode"] == "baseline":
                    self.assertEqual(record["attacks"]["replay"]["accepted"], 20)
                    self.assertEqual(record["attacks"]["raw_injection"]["accepted"], 20)
                    self.assertIsNone(record["attacks"]["wrong_key"]["acceptance_percent"])
                    self.assertEqual(record["wire"]["overhead_bytes"], 0)
                else:
                    for attack in record["attacks"].values():
                        self.assertEqual(attack["accepted"], 0)
                        self.assertEqual(attack["rejected"], 20)
                    self.assertGreater(record["wire"]["overhead_bytes"], 0)
        for start in (0, 3):
            records = result["results"][start:start + 3]
            self.assertEqual(records[0]["node_trials"], records[1]["node_trials"])
            self.assertEqual(records[1]["node_trials"], records[2]["node_trials"])

    def test_empty_trials_have_null_rates_and_timings(self):
        result = run_benchmark([1], steps=0)
        for record in result["results"]:
            self.assertIsNone(record["benign"]["acceptance_percent"])
            self.assertIsNone(record["timing"]["encode"]["mean_us"])
            for attack in record["attacks"].values():
                self.assertEqual(attack["attempts"], 0)
                self.assertIsNone(attack["acceptance_percent"])
        json.dumps(result, allow_nan=False)

    def test_cli_writes_self_describing_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            self.assertEqual(main(["--sizes", "1", "2", "--steps", "2",
                                   "--output", str(output)]), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result["experiment"], "in_memory_protocol_microbenchmark")
            self.assertEqual(len(result["results"]), 6)

    def test_invalid_inputs_fail_before_running(self):
        for sizes, steps in [([], 1), ([0], 1), ([65], 1), ([1], -1)]:
            with self.subTest(sizes=sizes, steps=steps), self.assertRaises(ValueError):
                run_benchmark(sizes, steps)


if __name__ == "__main__":
    unittest.main()
