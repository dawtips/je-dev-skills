import unittest

from evals.run_delta import compute_delta


def run(avg, pass_rate, passed, cases):
    # cases: list of (scenario, score)
    return {
        "summary": {"average_score": avg, "pass_rate": pass_rate, "passed": passed},
        "results": [{"test_case": {"scenario": s}, "score": sc} for s, sc in cases],
    }


class TestComputeDelta(unittest.TestCase):
    def test_aggregate_delta(self):
        base = run(7.0, 50.0, 2, [("a", 6), ("b", 8)])
        cur = run(8.0, 100.0, 2, [("a", 8), ("b", 8)])
        d = compute_delta(base, cur)
        self.assertEqual(d["aggregate"]["average_score"], 1.0)
        self.assertEqual(d["aggregate"]["pass_rate"], 50.0)
        self.assertEqual(d["aggregate"]["passed"], 0)

    def test_per_case_matched_by_scenario(self):
        base = run(7.0, 50.0, 1, [("a", 6), ("b", 8)])
        cur = run(7.5, 50.0, 1, [("b", 8), ("a", 9)])  # reordered
        d = compute_delta(base, cur)
        by_case = {c["case"]: c for c in d["per_case"]}
        self.assertEqual(by_case["a"]["delta"], 3)  # 9 - 6, matched despite reorder
        self.assertTrue(by_case["a"]["matched"])

    def test_unmatched_case_reports_none(self):
        base = run(7.0, 0.0, 0, [("a", 6)])
        cur = run(8.0, 0.0, 0, [("new", 8)])
        d = compute_delta(base, cur)
        c = d["per_case"][0]
        self.assertEqual(c["case"], "new")
        self.assertIsNone(c["delta"])
        self.assertFalse(c["matched"])


if __name__ == "__main__":
    unittest.main()
