import os
import unittest

from scaffold import load_blueprint, render_step_script, step_script_filename

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
        self.assertIn('MARKER=".agent-build-state/${IDEMPOTENCY_KEY}.done"', script)
        self.assertIn("mkdir -p .agent-build-state", script)
        self.assertIn("already completed", script)
        self.assertIn("TODO: implement the side-effecting command", script)

    def test_reversible_step_includes_rollback_note(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        script = render_step_script(bp["steps"][2])
        self.assertIn("Rollback: void the refund via the orders API", script)

    def test_step_script_filename_slugifies_id(self):
        self.assertEqual(step_script_filename({"id": "Fetch Order!"}), "fetch-order.sh")


if __name__ == "__main__":
    unittest.main()
