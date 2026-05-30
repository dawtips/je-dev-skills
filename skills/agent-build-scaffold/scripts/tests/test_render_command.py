import os
import unittest

from scaffold import load_blueprint, render_entry_command

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderEntryCommand(unittest.TestCase):
    def test_renders_command_frontmatter_and_ordered_steps(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        text = render_entry_command(bp, "refund-triage")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("description: Run the refund-triage agent workflow", text)
        self.assertIn("argument-hint: <order_id> <reason>", text)
        self.assertIn("## Execution Rules", text)
        self.assertIn("one level deep", text)
        self.assertIn("1. `classify-reason` - dispatch subagent `reason-classifier`", text)
        self.assertIn("Termination: a single category is chosen", text)
        self.assertIn("2. `fetch-order` - run script `.claude/scripts/fetch-order.sh`", text)
        self.assertIn("3. `issue-refund` - run script `.claude/scripts/issue-refund.sh`", text)
        self.assertIn("## Gates", text)
        self.assertIn("classification-accuracy: score file `.agent-build-state/classification-accuracy.score`, gate `4`", text)
        self.assertIn("## Side Effects And Recovery", text)
        self.assertIn("issue-refund: idempotency key `order_id`; retry `exponential`; rollback `void the refund via the orders API`", text)

    def test_renders_no_subagent_path_for_deterministic_only_blueprint(self):
        bp = load_blueprint(os.path.join(FIXTURES, "csv-to-slack.blueprint.md"))
        text = render_entry_command(bp, "csv-to-slack")
        self.assertIn("1. `parse-csv` - run script `.claude/scripts/parse-csv.sh`", text)
        self.assertIn("2. `post-summary` - run script `.claude/scripts/post-summary.sh`", text)
        self.assertNotIn("dispatch subagent", text)


if __name__ == "__main__":
    unittest.main()
