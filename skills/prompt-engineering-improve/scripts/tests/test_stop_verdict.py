import unittest

from improve_step import stop_verdict, RoundRecord, LoopParams

PARAMS = LoopParams(
    pass_threshold=7, pass_rate_target=0.80, max_rounds=3,
    epsilon=0.25, diminishing_return_rounds=2, regression_band=0.5,
)


class TestStopVerdict(unittest.TestCase):
    def _rr(self, version, avg, pr):
        return RoundRecord(version=version, avg=avg, pass_rate=pr)

    def test_continue_when_below_bar_and_rounds_remain(self):
        rounds = [self._rr("v1", 5.0, 25.0)]
        v = stop_verdict(rounds, PARAMS, round_index=0)
        self.assertEqual(v.decision, "continue")
        self.assertIsNone(v.rule)

    def test_stop_threshold_when_avg_meets_pass_threshold(self):
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 7.0, 60.0)]
        v = stop_verdict(rounds, PARAMS, round_index=1)
        self.assertEqual(v.decision, "stop")
        self.assertEqual(v.rule, "threshold")

    def test_stop_pass_rate_when_target_reached(self):
        # avg below 7 but pass_rate >= 80% -> stop on pass_rate.
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 6.9, 80.0)]
        v = stop_verdict(rounds, PARAMS, round_index=1)
        self.assertEqual(v.decision, "stop")
        self.assertEqual(v.rule, "pass_rate")

    def test_stop_max_rounds_when_cap_reached(self):
        # round_index counts the baseline as round 0; max_rounds=3 improvement
        # rounds means baseline=0, r1=1, r2=2, r3=3 -> the cap fires at index 3
        # (round_index >= max_rounds). Four rounds total: baseline + 3 improvements.
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 5.5, 30.0),
                  self._rr("v3", 5.8, 35.0), self._rr("v4", 6.0, 40.0)]
        v = stop_verdict(rounds, PARAMS, round_index=3)
        self.assertEqual(v.decision, "stop")
        self.assertEqual(v.rule, "max_rounds")

    def test_threshold_takes_priority_over_max_rounds(self):
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 6.0, 40.0),
                  self._rr("v3", 6.5, 50.0), self._rr("v4", 8.0, 90.0)]
        v = stop_verdict(rounds, PARAMS, round_index=3)
        self.assertEqual(v.rule, "threshold")  # report the success rule, not the budget cap

    def test_stop_regression_when_more_than_band_below_best(self):
        # best v2=7.2; v3=6.5 is 0.7 below best > band 0.5 -> stop:regression_band.
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 7.2, 75.0),
                  self._rr("v3", 6.5, 50.0)]
        v = stop_verdict(rounds, PARAMS, round_index=2)
        self.assertEqual(v.decision, "stop")
        self.assertEqual(v.rule, "regression_band")

    def test_no_regression_within_band(self):
        # best v2=7.2 already meets threshold 7 -> threshold fires first, not regression.
        # Use a sub-threshold best to isolate the band: best v2=6.9; v3=6.5 is 0.4 below -> within band.
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 6.9, 60.0),
                  self._rr("v3", 6.5, 55.0)]
        v = stop_verdict(rounds, PARAMS, round_index=2)
        # 0.4 <= band 0.5 -> not a regression; rounds remain (index 2, cap 3) -> continue.
        self.assertEqual(v.decision, "continue")

    def test_stop_diminishing_returns_after_K_subepsilon_rounds(self):
        # epsilon 0.25, K=2: two consecutive deltas below 0.25 (0.1 then 0.1) -> stop.
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 5.1, 26.0),
                  self._rr("v3", 5.2, 27.0)]
        v = stop_verdict(rounds, PARAMS, round_index=2)
        self.assertEqual(v.decision, "stop")
        self.assertEqual(v.rule, "diminishing-returns-2")

    def test_one_subepsilon_round_is_not_diminishing(self):
        rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 5.1, 26.0)]
        v = stop_verdict(rounds, PARAMS, round_index=1)
        self.assertEqual(v.decision, "continue")
