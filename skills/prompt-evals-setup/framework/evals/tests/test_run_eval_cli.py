import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from evals import run_eval
from evals.artifacts import scaffold_eval_artifacts


def _scaffold_prompt_project(root: Path):
    (root / "prompts").mkdir(parents=True, exist_ok=True)
    (root / "prompts" / "planner.md").write_text("Plan for {goal}", encoding="utf-8")
    scaffold_eval_artifacts(root, "planner", mode="prompt_file", prompt_file="prompts/planner.md")
    (root / "evals" / "planner" / "cases.json").write_text(
        json.dumps(
            {
                "provenance": {"task_description": "plan"},
                "cases": [
                    {
                        "task_description": "plan",
                        "prompt_inputs": {"goal": "retention"},
                        "solution_criteria": ["x"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return root / "evals" / "planner" / "eval.json"


class TestRunEvalCli(unittest.TestCase):
    def run_evaluate_variance(self, group_label: str, k: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with (
            patch.object(run_eval.config, "EXECUTION_MODE", "anthropic_api"),
            patch.object(run_eval, "run_k_variance") as run_k_variance,
            redirect_stdout(stdout),
        ):
            result = run_eval.main(["run_eval.py", "evaluate-variance", group_label, k])
        run_k_variance.assert_not_called()
        return result, stdout.getvalue()

    def test_evaluate_variance_rejects_non_integer_k_without_running(self):
        result, stdout = self.run_evaluate_variance("group", "nope")

        self.assertEqual(result, 2)
        self.assertIn("error: <k> must be an integer >= 2", stdout)

    def test_evaluate_variance_rejects_k_less_than_two_without_running(self):
        result, stdout = self.run_evaluate_variance("group", "1")

        self.assertEqual(result, 2)
        self.assertIn("K-run variance requires k >= 2", stdout)

    def test_evaluate_variance_rejects_path_like_group_label_without_running(self):
        result, stdout = self.run_evaluate_variance("group/path", "2")

        self.assertEqual(result, 2)
        self.assertIn("group_label must be a non-empty run label, not a path", stdout)

    # --- T-018 artifact CLI branches -------------------------------------------

    def _run(self, argv):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = run_eval.main(["run_eval.py", *argv])
        return rc, stdout.getvalue()

    def test_render_artifact_prints_rendered_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())
            rc, out = self._run(["render-artifact", str(eval_json), "0"])
            self.assertEqual(rc, 0)
            self.assertIn("Plan for retention", out)

    def test_render_artifact_rejects_missing_args(self):
        rc, out = self._run(["render-artifact"])
        self.assertEqual(rc, 2)

    def test_render_artifact_rejects_out_of_range_case_index(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())
            rc, out = self._run(["render-artifact", str(eval_json), "9"])
            self.assertEqual(rc, 2)

    def test_render_artifact_rejects_negative_case_index(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())
            rc, out = self._run(["render-artifact", str(eval_json), "-1"])
            self.assertEqual(rc, 2)
            self.assertIn("out of range", out)

    def test_render_artifact_reports_missing_cases_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "prompts").mkdir()
            (root / "prompts" / "planner.md").write_text("Plan for {goal}", encoding="utf-8")
            scaffold_eval_artifacts(root, "planner", mode="prompt_file", prompt_file="prompts/planner.md")
            eval_json = root / "evals" / "planner" / "eval.json"  # no cases.json generated
            rc, out = self._run(["render-artifact", str(eval_json), "0"])
            self.assertEqual(rc, 2)
            self.assertIn("cases file not found", out)

    def test_evaluate_artifact_requires_eval_json_path(self):
        rc, out = self._run(["evaluate-artifact"])
        self.assertEqual(rc, 2)

    def test_evaluate_artifact_mode_gated_in_claude_code(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())
            with patch.object(run_eval.config, "EXECUTION_MODE", "in_claude_code"):
                rc, out = self._run(["evaluate-artifact", str(eval_json)])
            self.assertEqual(rc, 3)
            self.assertIn("prompt-evals-run", out)

    def test_generate_artifact_requires_eval_json_path(self):
        rc, out = self._run(["generate-artifact"])
        self.assertEqual(rc, 2)

    def test_generate_artifact_rejects_unfilled_generation_block(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())  # generation left empty
            rc, out = self._run(["generate-artifact", str(eval_json)])
            self.assertEqual(rc, 2)
            self.assertIn("generation", out)

    def test_generate_artifact_writes_cases_via_evaluator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            eval_json = _scaffold_prompt_project(root)
            data = json.loads(eval_json.read_text(encoding="utf-8"))
            data["generation"] = {
                "task_description": "Write a plan",
                "prompt_inputs_spec": {"goal": "the goal"},
                "num_cases": 2,
            }
            eval_json.write_text(json.dumps(data), encoding="utf-8")

            class FakeEvaluator:
                def generate_dataset(self, *, task_description, prompt_inputs_spec, num_cases, output_file):
                    Path(output_file).write_text(
                        json.dumps({"provenance": {"task_description": task_description}, "cases": []}),
                        encoding="utf-8",
                    )

            with patch.object(run_eval, "build_evaluator", return_value=FakeEvaluator()):
                rc, out = self._run(["generate-artifact", str(eval_json)])
            self.assertEqual(rc, 0)
            cases = root / "evals" / "planner" / "cases.json"
            self.assertTrue(cases.exists())
            self.assertEqual(
                json.loads(cases.read_text(encoding="utf-8"))["provenance"]["task_description"],
                "Write a plan",
            )

    def test_scaffold_artifact_creates_layout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "prompts").mkdir()
            (root / "prompts" / "p.md").write_text("{g}", encoding="utf-8")
            rc, out = self._run(["scaffold-artifact", str(root), "p", "prompt_file", "prompts/p.md"])
            self.assertEqual(rc, 0)
            self.assertTrue((root / "evals" / "p" / "eval.json").exists())
            self.assertIn("eval.json", out)

    def test_scaffold_artifact_rejects_bad_mode(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = self._run(["scaffold-artifact", str(Path(d).resolve()), "p", "bogus", "x"])
            self.assertEqual(rc, 2)

    def test_scaffold_artifact_requires_all_args(self):
        rc, out = self._run(["scaffold-artifact", "/tmp", "p"])
        self.assertEqual(rc, 2)

    def test_evaluate_artifact_variance_requires_args(self):
        rc, out = self._run(["evaluate-artifact-variance", "only-eval.json"])
        self.assertEqual(rc, 2)

    def test_evaluate_artifact_variance_mode_gated_in_claude_code(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())
            with patch.object(run_eval.config, "EXECUTION_MODE", "in_claude_code"):
                rc, out = self._run(["evaluate-artifact-variance", str(eval_json), "grp", "2"])
            self.assertEqual(rc, 3)

    def test_evaluate_artifact_variance_rejects_non_integer_k_without_running(self):
        with tempfile.TemporaryDirectory() as d:
            eval_json = _scaffold_prompt_project(Path(d).resolve())
            with (
                patch.object(run_eval.config, "EXECUTION_MODE", "anthropic_api"),
                patch.object(run_eval, "run_k_variance") as run_k_variance,
            ):
                rc, out = self._run(["evaluate-artifact-variance", str(eval_json), "grp", "nope"])
            run_k_variance.assert_not_called()
            self.assertEqual(rc, 2)

    def test_generate_artifact_overwrites_existing_cases(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            eval_json = _scaffold_prompt_project(root)  # already writes a cases.json
            data = json.loads(eval_json.read_text(encoding="utf-8"))
            data["generation"] = {
                "task_description": "T",
                "prompt_inputs_spec": {"goal": "g"},
                "num_cases": 1,
            }
            eval_json.write_text(json.dumps(data), encoding="utf-8")

            class FakeEvaluator:
                def generate_dataset(self, *, task_description, prompt_inputs_spec, num_cases, output_file):
                    Path(output_file).write_text(
                        json.dumps({"provenance": {"task_description": "REGENERATED"}, "cases": []}),
                        encoding="utf-8",
                    )

            with patch.object(run_eval, "build_evaluator", return_value=FakeEvaluator()):
                rc, out = self._run(["generate-artifact", str(eval_json)])
            self.assertEqual(rc, 0)
            cases = json.loads((root / "evals" / "planner" / "cases.json").read_text(encoding="utf-8"))
            self.assertEqual(cases["provenance"]["task_description"], "REGENERATED")

    def test_unknown_command_returns_2(self):
        rc, out = self._run(["bogus"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
