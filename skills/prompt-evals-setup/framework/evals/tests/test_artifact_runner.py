"""Offline tests for the plugin-resident artifact runner (T-018).

No network or API key. Exercises:
  - prompt-file rendering that REUSES promptprep + templates (no duplicated logic),
  - command-adapter subprocess execution (case JSON on stdin -> stdout),
  - build_run_function dispatch on target mode,
  - evaluate_artifact routing through live_run.run_evaluation so assertions/report
    are inherited and outputs land under the project's evals/<name>/runs/<label>/.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from evals.artifacts import load_eval_spec, scaffold_eval_artifacts
from evals.artifact_runner import (
    build_run_function,
    evaluate_artifact,
    render_prompt_file,
    run_command_adapter,
)
from evals.promptprep import MissingPlaceholderError

_ADAPTER = Path(__file__).parent / "fixtures" / "adapters" / "echo_adapter.py"


def _prompt_eval(root: Path):
    (root / "prompts").mkdir(parents=True, exist_ok=True)
    (root / "prompts" / "planner.md").write_text("Plan for {goal}", encoding="utf-8")
    scaffold_eval_artifacts(root, "planner", mode="prompt_file", prompt_file="prompts/planner.md")
    (root / "evals" / "planner" / "cases.json").write_text(
        json.dumps(
            {
                "provenance": {"task_description": "Produce a plan"},
                "cases": [
                    {
                        "task_description": "Produce a plan",
                        "prompt_inputs": {"goal": "retention"},
                        "solution_criteria": ["Mentions the goal"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_eval_spec(root / "evals" / "planner" / "eval.json")


def _adapter_eval(root: Path):
    scaffold_eval_artifacts(
        root, "agent", mode="command_adapter", command=[sys.executable, str(_ADAPTER)]
    )
    return load_eval_spec(root / "evals" / "agent" / "eval.json")


class FakeJudge:
    """Offline judge double: returns a fixed valid verdict for tag='grade'."""

    model = "fake-judge"

    def complete_json(self, *, system, user, temperature, tag="", schema=None):
        if tag != "grade":
            raise ValueError(f"FakeJudge received unknown tag: {tag!r}")
        return {
            "strengths": ["Mentions the goal."],
            "weaknesses": [],
            "reasoning": "Meets the criterion.",
            "score": 9,
        }


class TestPromptFileMode(unittest.TestCase):
    def test_render_reuses_promptprep_and_templates(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _prompt_eval(Path(d).resolve())
            self.assertEqual(render_prompt_file(spec, {"goal": "retention"}), "Plan for retention")

    def test_missing_placeholder_raises_structured_error(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _prompt_eval(Path(d).resolve())
            with self.assertRaises(MissingPlaceholderError):
                render_prompt_file(spec, {})

    def test_render_warns_on_unused_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _prompt_eval(Path(d).resolve())
            with self.assertLogs("evals.promptprep", level="WARNING") as cm:
                out = render_prompt_file(spec, {"goal": "retention", "stale": "x"})
            self.assertEqual(out, "Plan for retention")
            self.assertTrue(any("never references" in m for m in cm.output))


class TestCommandAdapterMode(unittest.TestCase):
    def test_adapter_receives_case_on_stdin_and_returns_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _adapter_eval(Path(d).resolve())
            out = run_command_adapter(spec, {"prompt_inputs": {"goal": "retention"}})
            self.assertEqual(out, "adapter saw retention")

    def test_adapter_raises_on_subprocess_failure(self):
        import subprocess

        fail = Path(__file__).parent / "fixtures" / "adapters" / "fail_adapter.py"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            scaffold_eval_artifacts(
                root, "agent", mode="command_adapter", command=[sys.executable, str(fail)]
            )
            spec = load_eval_spec(root / "evals" / "agent" / "eval.json")
            with self.assertRaises(subprocess.CalledProcessError):
                run_command_adapter(spec, {"prompt_inputs": {"goal": "x"}})


class TestBuildRunFunction(unittest.TestCase):
    def test_prompt_file_run_function_renders_then_calls_executor(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _prompt_eval(Path(d).resolve())
            run_fn = build_run_function(spec, executor=lambda prompt: prompt.upper())
            self.assertEqual(run_fn({"goal": "retention"}), "PLAN FOR RETENTION")

    def test_prompt_file_mode_requires_executor(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _prompt_eval(Path(d).resolve())
            with self.assertRaises(ValueError):
                build_run_function(spec)

    def test_command_adapter_run_function_needs_no_executor(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _adapter_eval(Path(d).resolve())
            run_fn = build_run_function(spec)
            self.assertEqual(run_fn({"goal": "retention"}), "adapter saw retention")


class TestRoutesThroughRunEvaluation(unittest.TestCase):
    def test_evaluate_artifact_writes_report_into_project_runs_dir(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            spec = _prompt_eval(root)
            result = evaluate_artifact(
                spec,
                judge_client=FakeJudge(),
                run_function=lambda inputs: "Plan for " + inputs["goal"],
                run_label="t1",
            )
            run_dir = root / "evals" / "planner" / "runs" / "t1"
            self.assertTrue((run_dir / "output.json").exists())
            self.assertTrue((run_dir / "output.html").exists())
            self.assertEqual(result["summary"]["total"], 1)
            self.assertEqual(result["run_dir"], str(run_dir))
            # The judge ran (no assertions configured) and produced the fixed score.
            self.assertEqual(result["results"][0]["score"], 9)

    def test_evaluate_artifact_default_run_function_uses_executor(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            spec = _prompt_eval(root)
            result = evaluate_artifact(
                spec,
                judge_client=FakeJudge(),
                executor=lambda prompt: prompt + " :: done",
                run_label="t2",
            )
            self.assertEqual(result["results"][0]["output"], "Plan for retention :: done")

    def test_evaluate_artifact_inherits_assertions_and_extra_criteria(self):
        """Non-empty assertions + extra_criteria configured in eval.json reach the run path."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _prompt_eval(root)
            ej = root / "evals" / "planner" / "eval.json"
            data = json.loads(ej.read_text(encoding="utf-8"))
            data["assertions"] = [{"type": "contains", "value": "retention", "severity": "advisory"}]
            data["extra_criteria"] = "Must mention the goal."
            ej.write_text(json.dumps(data), encoding="utf-8")
            spec = load_eval_spec(ej)

            seen = {}

            class RecordingJudge(FakeJudge):
                def complete_json(self, *, system, user, temperature, tag="", schema=None):
                    seen["user"] = user
                    return super().complete_json(
                        system=system, user=user, temperature=temperature, tag=tag, schema=schema
                    )

            result = evaluate_artifact(
                spec,
                judge_client=RecordingJudge(),
                run_function=lambda inputs: "Plan for " + inputs["goal"],
                run_label="a",
            )
            res0 = result["results"][0]
            # The assertion gate ran and its advisory check passed (output contains "retention").
            self.assertIn("assertion_gate", res0)
            self.assertTrue(any(r["passed"] for r in res0["assertion_gate"]["results"]))
            # extra_criteria reached the judge's grading prompt.
            self.assertIn("Must mention the goal.", seen["user"])

    def test_evaluate_artifact_command_adapter_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _adapter_eval(root)
            (root / "evals" / "agent" / "cases.json").write_text(
                json.dumps(
                    {
                        "provenance": {"task_description": "agent"},
                        "cases": [
                            {
                                "task_description": "agent",
                                "prompt_inputs": {"goal": "retention"},
                                "solution_criteria": ["x"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            spec = load_eval_spec(root / "evals" / "agent" / "eval.json")
            result = evaluate_artifact(spec, judge_client=FakeJudge(), run_label="a")
            self.assertEqual(result["results"][0]["output"], "adapter saw retention")
            self.assertTrue((root / "evals" / "agent" / "runs" / "a" / "output.json").exists())


if __name__ == "__main__":
    unittest.main()
