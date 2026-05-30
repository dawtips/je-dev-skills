import json
import tempfile
import unittest
from pathlib import Path

from evals.examples.fake_client import FakeLLMClient
from evals.live_run import run_evaluation


def write_dataset(path):
    payload = {
        "provenance": {"task_description": "Write a meal plan."},
        "cases": [
            {
                "task_description": "Write a meal plan.",
                "scenario": "missing mandatory output",
                "prompt_inputs": {"goal": "bulk"},
                "solution_criteria": ["Includes calories."],
            }
        ],
    }
    path.write_text(json.dumps(payload))


class CountingJudge(FakeLLMClient):
    def __init__(self, *, fixed_score=8):
        super().__init__(fixed_score=fixed_score)
        self.grade_calls = 0

    def complete_json(self, **kwargs):
        if kwargs.get("tag") == "grade":
            self.grade_calls += 1
        return super().complete_json(**kwargs)


class TestLiveRunAssertions(unittest.TestCase):
    def test_mandatory_assertion_failure_skips_judge_and_persists_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            write_dataset(dataset)
            judge = CountingJudge()

            result = run_evaluation(
                judge_client=judge,
                run_function=lambda inputs: "plain answer",
                dataset_file=str(dataset),
                assertions=[{"type": "contains", "value": "kcal", "severity": "mandatory"}],
                assertion_policy="gate_mandatory",
                runs_dir=str(runs_dir),
                run_label="assertion-gated",
            )

            self.assertEqual(judge.grade_calls, 0)
            self.assertEqual(result["summary"]["passed"], 0)
            case = result["results"][0]
            self.assertEqual(case["score"], 1)
            self.assertTrue(case["assertion_gate"]["judge_skipped"])
            output = json.loads((runs_dir / "assertion-gated" / "output.json").read_text())
            self.assertTrue(output["results"][0]["assertion_gate"]["judge_skipped"])

    def test_advisory_assertion_failure_still_calls_judge(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            write_dataset(dataset)
            judge = CountingJudge(fixed_score=8)

            result = run_evaluation(
                judge_client=judge,
                run_function=lambda inputs: "plain answer",
                dataset_file=str(dataset),
                assertions=[{"type": "contains", "value": "kcal", "severity": "advisory"}],
                assertion_policy="gate_mandatory",
                runs_dir=str(Path(d) / "runs"),
                run_label="assertion-annotated",
            )

            self.assertEqual(judge.grade_calls, 1)
            self.assertEqual(result["results"][0]["score"], 8)
            self.assertFalse(result["results"][0]["assertion_gate"]["judge_skipped"])


if __name__ == "__main__":
    unittest.main()
