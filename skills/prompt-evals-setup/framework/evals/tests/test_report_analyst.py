import unittest

from evals.report_analyst import build_report_analysis, render_markdown


def run(avg, pass_rate, passed, cases, label="run"):
    return {
        "meta": {"run_label": label, "dataset_file": "evals/datasets/meal_plan.json"},
        "summary": {"average_score": avg, "pass_rate": pass_rate, "passed": passed},
        "results": [{"test_case": {"scenario": scenario}, "score": score} for scenario, score in cases],
    }


class TestReportAnalysis(unittest.TestCase):
    def test_baseline_delta_calls_core_and_names_movers(self):
        baseline = run(7.0, 50.0, 1, [("easy", 8), ("hard", 6)], label="base")
        current = run(8.0, 100.0, 2, [("easy", 8), ("hard", 9)], label="current")

        analysis = build_report_analysis(current, baseline=baseline, variance_runs=[])

        delta = analysis["baseline_delta"]
        self.assertTrue(delta["available"])
        self.assertEqual(delta["aggregate"]["average_score"], 1.0)
        self.assertEqual(delta["aggregate"]["pass_rate"], 50.0)
        self.assertEqual(delta["movers"]["best"]["case"], "hard")
        self.assertEqual(delta["movers"]["best"]["delta"], 3)
        self.assertEqual(delta["movers"]["worst"]["case"], "easy")
        self.assertEqual(delta["movers"]["worst"]["delta"], 0)

    def test_non_negative_deltas_do_not_render_regression_label(self):
        baseline = run(7.0, 50.0, 1, [("easy", 8), ("hard", 6)], label="base")
        current = run(8.0, 100.0, 2, [("easy", 8), ("hard", 9)], label="current")

        analysis = build_report_analysis(current, baseline=baseline, variance_runs=[])
        md = render_markdown(analysis)

        self.assertIn("Biggest improvement: hard (+3).", md)
        self.assertNotIn("Biggest regression", md)

    def test_variance_calls_core_and_surfaces_regression_band(self):
        runs = [
            run(9.0, 100.0, 2, [("stable", 8), ("flaky", 10)], label="k00"),
            run(6.5, 50.0, 1, [("stable", 8), ("flaky", 5)], label="k01"),
            run(7.5, 50.0, 1, [("stable", 8), ("flaky", 7)], label="k02"),
        ]

        analysis = build_report_analysis(runs[-1], baseline=None, variance_runs=runs)

        variance = analysis["variance"]
        self.assertTrue(variance["available"])
        self.assertEqual(variance["aggregate"]["runs"], 3)
        self.assertEqual(variance["aggregate"]["flaky_cases"], 1)
        self.assertGreater(variance["suggested_regression_band"], 0)

    def test_absent_inputs_render_notes_not_errors(self):
        current = run(8.0, 100.0, 1, [("only", 8)], label="current")

        analysis = build_report_analysis(current, baseline=None, variance_runs=[current])
        md = render_markdown(analysis)

        self.assertFalse(analysis["baseline_delta"]["available"])
        self.assertFalse(analysis["variance"]["available"])
        self.assertIn("Baseline delta: not available", md)
        self.assertIn("Variance: not available", md)
        self.assertIn("needs >=2 runs", md)


if __name__ == "__main__":
    unittest.main()
