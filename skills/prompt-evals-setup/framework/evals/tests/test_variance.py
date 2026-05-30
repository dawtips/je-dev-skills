import unittest

from evals.variance import compute_variance


def run(avg, cases):
    return {
        "summary": {"average_score": avg},
        "results": [{"test_case": {"scenario": s}, "score": sc} for s, sc in cases],
    }


class TestComputeVariance(unittest.TestCase):
    def setUp(self):
        # case "a" is stable (8,8,8); case "b" is flaky (10,5,7)
        self.runs = [
            run(9.0, [("a", 8), ("b", 10)]),
            run(6.5, [("a", 8), ("b", 5)]),
            run(7.5, [("a", 8), ("b", 7)]),
        ]

    def test_stable_case_zero_stddev(self):
        rep = compute_variance(self.runs)
        a = next(c for c in rep["per_case"] if c["case"] == "a")
        self.assertEqual(a["stddev"], 0.0)
        self.assertFalse(a["flaky"])
        self.assertEqual(a["mean"], 8.0)

    def test_flaky_case_flagged(self):
        rep = compute_variance(self.runs, flaky_stddev=1.0)
        b = next(c for c in rep["per_case"] if c["case"] == "b")
        self.assertGreater(b["stddev"], 1.0)
        self.assertTrue(b["flaky"])
        self.assertEqual(rep["aggregate"]["flaky_cases"], 1)

    def test_suggested_regression_band_is_worst_case_stddev(self):
        rep = compute_variance(self.runs)
        worst = max(c["stddev"] for c in rep["per_case"])
        self.assertEqual(rep["suggested_regression_band"], round(worst, 2))

    def test_requires_at_least_one_run(self):
        with self.assertRaises(ValueError):
            compute_variance([])


if __name__ == "__main__":
    unittest.main()
