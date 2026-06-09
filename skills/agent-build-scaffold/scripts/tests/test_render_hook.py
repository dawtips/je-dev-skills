import os
import subprocess
import tempfile
import unittest

from scaffold import ScaffoldError, hook_filename, load_blueprint, render_hook

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderHook(unittest.TestCase):
    def test_renders_rubric_gate_hook(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        hook = render_hook(bp["rubrics"][0])
        self.assertTrue(hook.startswith("#!/usr/bin/env bash\nset -euo pipefail\n"))
        self.assertIn("classification-accuracy", hook)
        self.assertIn("Exit 0 = pass, exit 2 = block", hook)
        self.assertIn('PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"', hook)
        self.assertIn('SCORE_FILE="$PROJECT_DIR/.agent-build-state/classification-accuracy.score"', hook)
        self.assertIn('if [ "$SCORE" -lt "4" ]; then', hook)
        self.assertIn("exit 2", hook)

    def test_hook_blocks_non_numeric_scores(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        hook = render_hook(bp["rubrics"][0])
        with tempfile.TemporaryDirectory() as tmp:
            hook_path = os.path.join(tmp, "gate.sh")
            os.makedirs(os.path.join(tmp, ".agent-build-state"))
            with open(hook_path, "w", encoding="utf-8") as f:
                f.write(hook)
            os.chmod(hook_path, 0o755)
            with open(
                os.path.join(tmp, ".agent-build-state", "classification-accuracy.score"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("abc")
            result = subprocess.run(
                [hook_path],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid numeric score", result.stderr)

    def test_hook_reads_score_from_project_root_env(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        hook = render_hook(bp["rubrics"][0])
        with tempfile.TemporaryDirectory() as tmp:
            hook_path = os.path.join(tmp, "gate.sh")
            nested = os.path.join(tmp, "nested")
            os.makedirs(os.path.join(tmp, ".agent-build-state"))
            os.makedirs(nested)
            with open(hook_path, "w", encoding="utf-8") as f:
                f.write(hook)
            os.chmod(hook_path, 0o755)
            with open(
                os.path.join(tmp, ".agent-build-state", "classification-accuracy.score"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("5")
            result = subprocess.run(
                [hook_path],
                cwd=nested,
                env={**os.environ, "CLAUDE_PROJECT_DIR": tmp},
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_numeric_gate_is_rejected_before_rendering_shell(self):
        with self.assertRaisesRegex(ScaffoldError, "gate"):
            render_hook({"name": "bad", "gate": "high"})

    def test_zero_gate_is_rejected_as_fail_open(self):
        # gate: 0 -> `[ "$SCORE" -lt "0" ]` is always false (never blocks).
        with self.assertRaisesRegex(ScaffoldError, "gate"):
            render_hook({"name": "bad", "gate": 0})

    def test_hook_filename_slugifies_name(self):
        self.assertEqual(
            hook_filename({"name": "Classification Accuracy!"}),
            "classification-accuracy-gate.sh",
        )


if __name__ == "__main__":
    unittest.main()
