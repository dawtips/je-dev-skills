import os
import tempfile
import unittest

from scaffold import load_blueprint, render_step_script, step_script_filename
from tests._shell import run_bash_script

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderStepScript(unittest.TestCase):
    def test_renders_plain_deterministic_step_script(self):
        bp = load_blueprint(os.path.join(FIXTURES, "csv-to-slack.blueprint.md"))
        script = render_step_script(bp["steps"][0])
        self.assertTrue(script.startswith("#!/usr/bin/env bash\nset -euo pipefail\n"))
        self.assertIn("AUTO-GENERATED placeholder by agent-build-scaffold", script)
        self.assertIn("Step: parse-csv", script)
        self.assertIn("Rationale: parse rows from a known CSV format", script)
        self.assertIn("TODO: implement this deterministic step", script)
        self.assertNotIn("IDEMPOTENCY_KEY", script)

    def test_side_effecting_step_gets_idempotency_guard(self):
        bp = load_blueprint(os.path.join(FIXTURES, "csv-to-slack.blueprint.md"))
        script = render_step_script(bp["steps"][1])
        self.assertIn('IDEMPOTENCY_KEY="${CSV_PATH:?set CSV_PATH}"', script)
        self.assertIn('SAFE_IDEMPOTENCY_KEY="$(printf', script)
        self.assertIn('MARKER=".agent-build-state/post-summary-${SAFE_IDEMPOTENCY_KEY}.done"', script)
        self.assertIn("mkdir -p .agent-build-state", script)
        self.assertIn("already completed", script)
        self.assertIn("TODO: implement the side-effecting command", script)

    def test_reversible_step_includes_rollback_note(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        script = render_step_script(bp["steps"][2])
        self.assertIn("Rollback: void the refund via the orders API", script)

    def test_multiline_comments_cannot_escape_into_shell_body(self):
        script = render_step_script({
            "id": "unsafe",
            "kind": "deterministic",
            "rationale": "first line\nrm -rf /tmp/should-not-run",
            "side_effecting": False,
            "reversible": True,
            "rollback": "rollback line\nrm -rf /tmp/also-not-run",
        })
        self.assertIn("# Rationale: first line", script)
        self.assertIn("#   rm -rf /tmp/should-not-run", script)
        self.assertIn("# Rollback: rollback line", script)
        self.assertIn("#   rm -rf /tmp/also-not-run", script)
        self.assertNotIn("\nrm -rf /tmp/should-not-run", script)
        self.assertNotIn("\nrm -rf /tmp/also-not-run", script)

    def test_side_effecting_marker_stays_in_state_dir(self):
        bp = load_blueprint(os.path.join(FIXTURES, "csv-to-slack.blueprint.md"))
        script = render_step_script(bp["steps"][1])
        with tempfile.TemporaryDirectory() as tmp:
            script_path = os.path.join(tmp, "post-summary.sh")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)
            os.chmod(script_path, 0o755)
            result = run_bash_script(
                script_path,
                cwd=tmp,
                env={**os.environ, "CSV_PATH": "../escape/path"},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.exists(
                os.path.join(tmp, ".agent-build-state", "post-summary-.._escape_path.done")
            ))
            self.assertFalse(os.path.exists(os.path.join(tmp, "..", "escape", "path.done")))

    def test_step_script_filename_slugifies_id(self):
        self.assertEqual(step_script_filename({"id": "Fetch Order!"}), "fetch-order.sh")


if __name__ == "__main__":
    unittest.main()
