import json
import tempfile
import unittest
from pathlib import Path

from evals.examples.fake_client import FakeLLMClient
from evals.live_run import run_evaluation
from evals.promptprep import MissingPlaceholderError


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


class TestLiveRunResilience(unittest.TestCase):
    def _two_case_dataset(self, path):
        payload = {
            "provenance": {"task_description": "t"},
            "cases": [
                {"task_description": "t", "scenario": "ok",
                 "prompt_inputs": {"goal": "fine"}, "solution_criteria": ["x"]},
                {"task_description": "t", "scenario": "boom",
                 "prompt_inputs": {"goal": "boom"}, "solution_criteria": ["x"]},
            ],
        }
        path.write_text(json.dumps(payload))

    def test_executor_failure_is_isolated_scored_and_reported(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            self._two_case_dataset(dataset)

            def flaky(inputs):
                if inputs.get("goal") == "boom":
                    raise RuntimeError("executor exploded")
                return "an answer"

            result = run_evaluation(
                judge_client=CountingJudge(fixed_score=8),
                run_function=flaky,
                dataset_file=str(dataset),
                assertions=[],
                runs_dir=str(runs_dir),
                run_label="flaky",
            )

            # The good case still ran; the bad case is isolated, not fatal.
            self.assertEqual(len(result["results"]), 2)
            self.assertEqual(len(result["errors"]), 1)
            errored = next(r for r in result["results"] if r.get("error"))
            ok = next(r for r in result["results"] if not r.get("error"))
            self.assertEqual(errored["score"], 1)
            self.assertIn("executor exploded", errored["error"])
            self.assertEqual(ok["score"], 8)
            # The report was still written and records the failure in meta.
            out = json.loads((runs_dir / "flaky" / "output.json").read_text())
            self.assertEqual(len(out["results"]), 2)
            self.assertEqual(len(out["meta"]["errors"]), 1)
            self.assertEqual(out["meta"]["errors"][0]["scenario"], "boom")

    def test_grade_failure_is_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            write_dataset(dataset)

            class BoomJudge(FakeLLMClient):
                def complete_json(self, **kwargs):
                    if kwargs.get("tag") == "grade":
                        raise RuntimeError("judge 500")
                    return super().complete_json(**kwargs)

            result = run_evaluation(
                judge_client=BoomJudge(fixed_score=8),
                run_function=lambda inputs: "kcal 2000",
                dataset_file=str(dataset),
                assertions=[],
                runs_dir=str(Path(d) / "runs"),
                run_label="grade-boom",
            )

            res0 = result["results"][0]
            self.assertEqual(res0["score"], 1)
            self.assertIn("judge 500", res0["error"])
            self.assertEqual(len(result["errors"]), 1)

    def test_malformed_dataset_fails_loudly_not_as_scored_failure(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            payload = {
                "provenance": {"task_description": "t"},
                # case is missing the required 'prompt_inputs' key
                "cases": [{"task_description": "t", "scenario": "bad", "solution_criteria": ["x"]}],
            }
            dataset.write_text(json.dumps(payload))

            with self.assertRaisesRegex(ValueError, "prompt_inputs"):
                run_evaluation(
                    judge_client=CountingJudge(),
                    run_function=lambda inputs: "x",
                    dataset_file=str(dataset),
                    assertions=[],
                    runs_dir=str(runs_dir),
                    run_label="bad",
                )
            # A schema error must not write a partial, normal-looking report.
            self.assertFalse((runs_dir / "bad").exists())

    def test_wrong_typed_prompt_inputs_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            payload = {
                "provenance": {"task_description": "t"},
                # prompt_inputs present but null -> not a mapping; must fail up front,
                # not reach check_placeholders and become a score-1 result.
                "cases": [{"task_description": "t", "scenario": "bad",
                           "prompt_inputs": None, "solution_criteria": ["x"]}],
            }
            dataset.write_text(json.dumps(payload))

            with self.assertRaisesRegex(ValueError, "prompt_inputs"):
                run_evaluation(
                    judge_client=CountingJudge(),
                    run_function=lambda inputs: "x",
                    dataset_file=str(dataset),
                    assertions=[],
                    runs_dir=str(runs_dir),
                    run_label="bad2",
                )
            self.assertFalse((runs_dir / "bad2").exists())

    def test_prompt_render_contract_error_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            write_dataset(dataset)

            def render_boom(inputs):
                # In prompt_file mode the template renders inside the executor call;
                # check_placeholders raises MissingPlaceholderError on a template/cases
                # mismatch. That is a deterministic contract error, not a flaky run.
                raise MissingPlaceholderError("template requires placeholder {missing}")

            with self.assertRaises(MissingPlaceholderError):
                run_evaluation(
                    judge_client=CountingJudge(),
                    run_function=render_boom,
                    dataset_file=str(dataset),
                    assertions=[],
                    runs_dir=str(runs_dir),
                    run_label="cfg",
                )
            self.assertFalse((runs_dir / "cfg").exists())


if __name__ == "__main__":
    unittest.main()
