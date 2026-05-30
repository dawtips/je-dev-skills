import json
import os
import unittest

from scaffold import hook_filename, load_blueprint, render_hook, render_hooks_json

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderHook(unittest.TestCase):
    def test_renders_rubric_gate_hook(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        hook = render_hook(bp["rubrics"][0])
        self.assertTrue(hook.startswith("#!/usr/bin/env bash\nset -euo pipefail\n"))
        self.assertIn("classification-accuracy", hook)
        self.assertIn("Exit 0 = pass, exit 1 = block", hook)
        self.assertIn('SCORE_FILE=".agent-build-state/classification-accuracy.score"', hook)
        self.assertIn('if [ "$SCORE" -lt "4" ]; then', hook)

    def test_render_hooks_json_wires_default_subagent_stop_event(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        payload = json.loads(render_hooks_json(bp["rubrics"]))
        self.assertIn("hooks", payload)
        self.assertIn("SubagentStop", payload["hooks"])
        self.assertEqual(
            payload["hooks"]["SubagentStop"][0]["command"],
            ".claude/hooks/classification-accuracy-gate.sh",
        )

    def test_hook_filename_slugifies_name(self):
        self.assertEqual(
            hook_filename({"name": "Classification Accuracy!"}),
            "classification-accuracy-gate.sh",
        )


if __name__ == "__main__":
    unittest.main()
