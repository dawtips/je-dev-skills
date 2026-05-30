"""Offline tests for the plugin-resident artifact scaffold + spec loader (T-018).

No network or API key. Exercises scaffold_eval_artifacts (no framework copy),
idempotent .gitignore insertion, and deterministic path resolution from the
prescribed evals/<name>/eval.json layout.
"""

import json
import tempfile
import unittest
from pathlib import Path

from evals.artifacts import (
    EvalSpec,
    load_eval_spec,
    resolve_project_root,
    scaffold_eval_artifacts,
)


def _make_prompt(root: Path, rel: str = "prompts/planner.md", body: str = "Plan for {goal}") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


class TestScaffold(unittest.TestCase):
    def test_scaffold_creates_artifact_layout_without_framework_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _make_prompt(root)

            spec = scaffold_eval_artifacts(
                root, "planner", mode="prompt_file", prompt_file="prompts/planner.md"
            )

            self.assertIsInstance(spec, EvalSpec)
            self.assertEqual(spec.eval_dir, root / "evals" / "planner")
            self.assertTrue((root / "evals" / "planner" / "eval.json").exists())
            self.assertTrue((root / "evals" / "planner" / "runs" / ".gitkeep").exists())
            # The framework must NOT be copied into the target.
            self.assertFalse((root / "evals" / "evaluator").exists())
            self.assertFalse((root / "evals" / "run_eval.py").exists())
            self.assertFalse((root / "evals" / "planner" / "run_eval.py").exists())
            gi = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("evals/*/runs/*", gi)
            self.assertIn("!evals/*/runs/.gitkeep", gi)

    def test_eval_json_records_mode_and_prompt_ref(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _make_prompt(root)
            scaffold_eval_artifacts(root, "planner", mode="prompt_file", prompt_file="prompts/planner.md")
            data = json.loads((root / "evals" / "planner" / "eval.json").read_text(encoding="utf-8"))
            self.assertEqual(data["target"]["mode"], "prompt_file")
            self.assertEqual(data["target"]["prompt_file"], "prompts/planner.md")
            self.assertEqual(data["assertion_policy"], "gate_mandatory")
            self.assertEqual(data["assertions"], [])
            # Keyed dataset-generation params are scaffolded empty for the developer to fill.
            self.assertEqual(data["generation"]["num_cases"], 20)
            self.assertEqual(data["generation"]["task_description"], "")

    def test_command_adapter_scaffold_records_command(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            scaffold_eval_artifacts(
                root, "agent", mode="command_adapter", command=["python", "run_agent.py"]
            )
            data = json.loads((root / "evals" / "agent" / "eval.json").read_text(encoding="utf-8"))
            self.assertEqual(data["target"]["mode"], "command_adapter")
            self.assertEqual(data["target"]["command"], ["python", "run_agent.py"])

    def test_gitignore_insertion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _make_prompt(root)
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            scaffold_eval_artifacts(root, "p2", mode="prompt_file", prompt_file="prompts/planner.md")
            gi = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(gi.count("evals/*/runs/*"), 1)
            self.assertEqual(gi.count("!evals/*/runs/.gitkeep"), 1)

    def test_gitignore_appends_below_existing_entries(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
            _make_prompt(root)
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            gi = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("__pycache__/", gi)
            self.assertIn("evals/*/runs/*", gi)

    def test_scaffold_does_not_overwrite_existing_eval_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _make_prompt(root)
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            ej = root / "evals" / "p" / "eval.json"
            data = json.loads(ej.read_text(encoding="utf-8"))
            data["extra_criteria"] = "do not clobber me"
            ej.write_text(json.dumps(data), encoding="utf-8")
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            self.assertEqual(
                json.loads(ej.read_text(encoding="utf-8"))["extra_criteria"], "do not clobber me"
            )

    def test_invalid_mode_rejected_by_scaffold(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                scaffold_eval_artifacts(Path(d).resolve(), "x", mode="bogus")


class TestLoadAndPaths(unittest.TestCase):
    def test_load_resolves_paths_from_prescribed_layout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _make_prompt(root)
            scaffold_eval_artifacts(root, "planner", mode="prompt_file", prompt_file="prompts/planner.md")
            spec = load_eval_spec(root / "evals" / "planner" / "eval.json")
            self.assertEqual(spec.project_root, root)
            self.assertEqual(spec.eval_dir, root / "evals" / "planner")
            self.assertEqual(spec.cases_file, root / "evals" / "planner" / "cases.json")
            self.assertEqual(spec.runs_dir, root / "evals" / "planner" / "runs")
            self.assertEqual(spec.prompt_file, root / "prompts" / "planner.md")

    def _prescribed_eval_json(self, root: Path, name: str, target: dict) -> Path:
        """Write an eval.json at the prescribed <root>/evals/<name>/eval.json path."""
        eval_dir = root / "evals" / name
        eval_dir.mkdir(parents=True, exist_ok=True)
        p = eval_dir / "eval.json"
        p.write_text(json.dumps({"name": name, "target": target}), encoding="utf-8")
        return p

    def test_invalid_mode_rejected_by_loader(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._prescribed_eval_json(Path(d).resolve(), "x", {"mode": "bogus"})
            with self.assertRaises(ValueError):
                load_eval_spec(p)

    def test_prompt_file_mode_requires_prompt_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._prescribed_eval_json(Path(d).resolve(), "x", {"mode": "prompt_file"})
            with self.assertRaises(ValueError):
                load_eval_spec(p)

    def test_command_adapter_mode_requires_command(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._prescribed_eval_json(Path(d).resolve(), "x", {"mode": "command_adapter"})
            with self.assertRaises(ValueError):
                load_eval_spec(p)

    def test_loader_rejects_non_prescribed_layout(self):
        # A valid target but the wrong path (not <project>/evals/<name>/eval.json).
        with tempfile.TemporaryDirectory() as d:
            p = Path(d).resolve() / "eval.json"
            p.write_text(
                json.dumps({"name": "x", "target": {"mode": "prompt_file", "prompt_file": "p.md"}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_eval_spec(p)


class TestProjectRootResolution(unittest.TestCase):
    def test_resolve_project_root_ok(self):
        self.assertEqual(
            resolve_project_root(Path("/p/evals/planner/eval.json")), Path("/p")
        )

    def test_resolve_project_root_rejects_shallow_path(self):
        # <project>/evals/<name> is required; a root-level evals/ is too shallow and
        # must raise a clear ValueError rather than an opaque IndexError.
        with self.assertRaises(ValueError):
            resolve_project_root(Path("/evals/eval.json"))


class TestGitignoreEdges(unittest.TestCase):
    def test_gitignore_handles_no_trailing_newline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / ".gitignore").write_text("*.pyc", encoding="utf-8")  # no trailing newline
            _make_prompt(root)
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            gi = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("*.pyc", gi)
            self.assertIn("evals/*/runs/*", gi)
            self.assertTrue(gi.endswith("\n"))
            self.assertNotIn("*.pycevals", gi)  # the original entry was not run together


class TestScaffoldIdempotency(unittest.TestCase):
    def test_re_scaffold_preserves_existing_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _make_prompt(root)
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            run_dir = root / "evals" / "p" / "runs" / "20260530-000000"
            run_dir.mkdir(parents=True)
            (run_dir / "output.json").write_text("{}", encoding="utf-8")
            scaffold_eval_artifacts(root, "p", mode="prompt_file", prompt_file="prompts/planner.md")
            self.assertTrue((run_dir / "output.json").exists())


if __name__ == "__main__":
    unittest.main()
