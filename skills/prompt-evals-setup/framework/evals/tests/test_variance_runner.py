import json
import tempfile
import unittest
from pathlib import Path

from evals.variance_runner import output_paths_for_labels, run_k_variance, variance_labels


class TestVarianceLabels(unittest.TestCase):
    def test_labels_are_explicit_group_plus_ordinal(self):
        self.assertEqual(
            variance_labels("meal-plan-variance", 3),
            ["meal-plan-variance__k00", "meal-plan-variance__k01", "meal-plan-variance__k02"],
        )

    def test_k_must_be_at_least_two(self):
        with self.assertRaises(ValueError):
            variance_labels("group", 1)


class TestRunKVariance(unittest.TestCase):
    def test_runs_k_times_and_computes_variance(self):
        with tempfile.TemporaryDirectory() as d:
            runs_dir = Path(d) / "runs"
            scores = [8, 6, 10]
            calls = []

            def run_once(label):
                calls.append(label)
                run_dir = runs_dir / label
                run_dir.mkdir(parents=True)
                payload = {
                    "summary": {"average_score": float(scores[len(calls) - 1])},
                    "results": [{"test_case": {"scenario": "case"}, "score": scores[len(calls) - 1]}],
                }
                (run_dir / "output.json").write_text(json.dumps(payload))
                return {"run_dir": str(run_dir)}

            result = run_k_variance(
                group_label="meal-plan-variance",
                k=3,
                runs_dir=str(runs_dir),
                run_once=run_once,
            )

        self.assertEqual(calls, ["meal-plan-variance__k00", "meal-plan-variance__k01", "meal-plan-variance__k02"])
        self.assertEqual(result["aggregate"]["runs"], 3)
        self.assertGreater(result["suggested_regression_band"], 0)

    def test_rejects_run_once_output_from_unexpected_directory(self):
        with tempfile.TemporaryDirectory() as d:
            runs_dir = Path(d) / "runs"
            stale_dir = runs_dir / "g__k00"
            stale_dir.mkdir(parents=True)
            (stale_dir / "output.json").write_text(
                json.dumps({"summary": {"average_score": 10.0}, "results": []})
            )

            def run_once(label):
                actual_dir = runs_dir / f"{label}-wrong"
                actual_dir.mkdir(parents=True)
                (actual_dir / "output.json").write_text(
                    json.dumps({"summary": {"average_score": 1.0}, "results": []})
                )
                return {"run_dir": str(actual_dir)}

            with self.assertRaises(ValueError):
                run_k_variance(group_label="g", k=2, runs_dir=runs_dir, run_once=run_once)

    def test_requires_output_json_in_actual_run_directory(self):
        with tempfile.TemporaryDirectory() as d:
            runs_dir = Path(d) / "runs"

            def run_once(label):
                actual_dir = runs_dir / label
                actual_dir.mkdir(parents=True)
                return {"run_dir": str(actual_dir)}

            with self.assertRaises(FileNotFoundError):
                run_k_variance(group_label="g", k=2, runs_dir=runs_dir, run_once=run_once)

    def test_output_paths_are_enumerated_without_guessing(self):
        paths = output_paths_for_labels("evals/runs", ["g__k00", "g__k01"])
        self.assertEqual(paths, [Path("evals/runs/g__k00/output.json"), Path("evals/runs/g__k01/output.json")])


if __name__ == "__main__":
    unittest.main()
