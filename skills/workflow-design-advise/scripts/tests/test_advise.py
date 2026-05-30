import os
import unittest

from advise_model import advise_blueprint, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestAdviseBlueprint(unittest.TestCase):
    def setUp(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_sample.blueprint.md"))
        self.recs = {r.target_id: r for r in advise_blueprint(bp)}

    def test_deterministic_step_is_skipped(self):
        self.assertNotIn("verify", self.recs)

    def test_orchestrate_step_advisory_opus_high(self):
        r = self.recs["plan"]
        self.assertEqual((r.recommended_model, r.recommended_effort), ("opus", "high"))
        self.assertFalse(r.writeable)        # steps have no model/effort field
        self.assertIsNone(r.agrees)

    def test_route_step_advisory_haiku_low(self):
        r = self.recs["classify"]
        self.assertEqual((r.recommended_model, r.recommended_effort), ("haiku", "low"))
        self.assertFalse(r.writeable)

    def test_parallelize_step_advisory_sonnet_high(self):
        r = self.recs["research-each"]
        self.assertEqual((r.recommended_model, r.recommended_effort), ("sonnet", "high"))

    def test_over_provisioned_subagent_flagged_as_disagreement(self):
        r = self.recs["item-researcher"]
        self.assertTrue(r.writeable)
        self.assertEqual((r.recommended_model, r.recommended_effort), ("sonnet", "medium"))
        self.assertEqual((r.current_model, r.current_effort), ("opus", "low"))
        self.assertFalse(r.agrees)           # opus/low != sonnet/medium
        self.assertTrue(r.needs_review)


class TestAgreement(unittest.TestCase):
    def test_inherit_is_undecided(self):
        bp = {"subagents": [{"id": "w", "tools": ["a", "b"],
                             "model": "inherit", "effort": "medium"}]}
        rec = advise_blueprint(bp)[0]
        self.assertIsNone(rec.agrees)

    def test_matching_choice_agrees(self):
        bp = {"subagents": [{"id": "w", "tools": ["a", "b"],
                             "model": "sonnet", "effort": "medium"}]}
        rec = advise_blueprint(bp)[0]
        self.assertTrue(rec.agrees)


if __name__ == "__main__":
    unittest.main()
