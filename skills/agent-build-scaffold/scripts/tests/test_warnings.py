import os
import unittest

from scaffold import load_blueprint, warn_overpowered_steps

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestWarnings(unittest.TestCase):
    def test_warns_when_agentic_step_is_mechanical(self):
        bp = load_blueprint(os.path.join(FIXTURES, "overpowered.blueprint.md"))
        warnings = warn_overpowered_steps(bp)
        self.assertEqual(len(warnings), 1)
        self.assertIn("extract-fields", warnings[0])
        self.assertIn("script", warnings[0])

    def test_does_not_warn_when_agentic_step_needs_judgment(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.assertEqual(warn_overpowered_steps(bp), [])


if __name__ == "__main__":
    unittest.main()
