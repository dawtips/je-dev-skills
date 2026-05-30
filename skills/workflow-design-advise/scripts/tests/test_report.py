import json
import os
import unittest

from advise_model import (
    advise_blueprint,
    load_blueprint,
    recommendations_to_json,
    render_report,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestReport(unittest.TestCase):
    def setUp(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_sample.blueprint.md"))
        self.recs = advise_blueprint(bp)

    def test_markdown_has_header_table_and_disagreement(self):
        out = render_report(self.recs, "advise-sample.blueprint.md", "2026-05-30")
        self.assertIn("# Model advice: advise-sample.blueprint.md", out)
        self.assertIn("Advised: 2026-05-30", out)
        self.assertIn("| Target | Kind | Recommended | Effort | Current | Agree | Review |", out)
        self.assertIn("item-researcher", out)
        self.assertIn("NO", out)            # the over-provisioned subagent disagrees
        self.assertIn("advisory (no model/effort field on steps)", out)

    def test_json_is_valid_and_round_trips_fields(self):
        payload = json.loads(recommendations_to_json(self.recs))
        by_id = {r["target_id"]: r for r in payload}
        self.assertNotIn("verify", by_id)
        self.assertEqual(by_id["item-researcher"]["recommended_model"], "sonnet")
        self.assertFalse(by_id["item-researcher"]["agrees"])
        self.assertFalse(by_id["plan"]["writeable"])


if __name__ == "__main__":
    unittest.main()
