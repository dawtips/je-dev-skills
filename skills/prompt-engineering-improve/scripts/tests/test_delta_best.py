import unittest

from improve_step import compute_delta, running_best, RoundRecord


class TestDeltaBest(unittest.TestCase):
    def test_delta_first_round_is_none(self):
        # No prior round -> delta is None (baseline has nothing to compare to).
        self.assertIsNone(compute_delta(current_avg=5.0, prior_avg=None))

    def test_delta_positive(self):
        self.assertEqual(compute_delta(current_avg=6.5, prior_avg=5.0), 1.5)

    def test_delta_negative(self):
        self.assertEqual(compute_delta(current_avg=4.5, prior_avg=5.0), -0.5)

    def test_delta_rounds_to_two_dp(self):
        self.assertEqual(compute_delta(current_avg=5.3333, prior_avg=5.0), 0.33)

    def test_running_best_argmax_returns_highest_avg_version(self):
        rounds = [
            RoundRecord(version="v1", avg=5.0, pass_rate=25.0),
            RoundRecord(version="v2", avg=7.2, pass_rate=75.0),
            RoundRecord(version="v3", avg=6.8, pass_rate=50.0),
        ]
        self.assertEqual(running_best(rounds).version, "v2")

    def test_running_best_tie_keeps_earliest(self):
        rounds = [
            RoundRecord(version="v1", avg=7.0, pass_rate=50.0),
            RoundRecord(version="v2", avg=7.0, pass_rate=75.0),
        ]
        # Ties broken by earliest (the baseline-of-equal-quality is kept; spec 6 tie-break).
        self.assertEqual(running_best(rounds).version, "v1")

    def test_running_best_empty_returns_none(self):
        self.assertIsNone(running_best([]))
