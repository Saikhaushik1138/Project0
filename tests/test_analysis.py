import unittest
from swarm_security.analysis import summarize


class AnalysisTests(unittest.TestCase):
    def test_distinct_clock_fields_and_rates(self):
        text = '''sim_time { sec: 1 nsec: 500000000 }
real_time { sec: 2 nsec: 0 }
iterations: 375
sim_time { sec: 2 nsec: 500000000 }
real_time { sec: 4 nsec: 0 }
iterations: 625'''
        result = summarize(text)
        self.assertEqual(result['real_time_factor'], .5)
        self.assertEqual(result['physics_updates_per_real_second'], 125)
        self.assertEqual(result['simulation_step_ms'], 4)

    def test_empty_and_reset_not_silently_summarized(self):
        with self.assertRaises(ValueError):
            summarize('')
        with self.assertRaises(ValueError):
            summarize('sim_time { sec: 5 } real_time { sec: 5 } iterations: 5\n'
                      'sim_time {} real_time {} iterations: 0')

    def test_single_sample_has_no_invented_rate(self):
        result = summarize('sim_time {sec: 5} real_time {sec: 10} iterations: 250')
        self.assertIsNone(result['real_time_factor'])
