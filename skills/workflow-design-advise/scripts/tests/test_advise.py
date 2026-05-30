import os
import unittest

from advise_model import AdviceInputError, advise_blueprint, load_blueprint

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

    def test_unset_model_effort_is_undecided_not_disagreement(self):
        # A subagent with no tier chosen yet is 'undecided', not 'wrong'.
        rec = advise_blueprint({"subagents": [{"id": "w", "tools": ["a", "b"]}]})[0]
        self.assertIsNone(rec.agrees)
        self.assertIsNone(rec.current_model)

    def test_model_matches_but_effort_differs_disagrees(self):
        # Isolates the effort half of the `and` so an and->or regression fails.
        bp = {"subagents": [{"id": "w", "tools": ["a", "b"],
                             "model": "sonnet", "effort": "low"}]}
        rec = advise_blueprint(bp)[0]   # recommends sonnet/medium
        self.assertEqual(rec.recommended_model, "sonnet")
        self.assertFalse(rec.agrees)    # effort low != medium

    def test_half_specified_wrong_model_still_disagrees(self):
        # One field set WRONG + the other absent must NOT be excused as undecided.
        bp = {"subagents": [{"id": "w", "tools": ["a", "b"], "model": "haiku"}]}
        rec = advise_blueprint(bp)[0]   # recommends sonnet/medium
        self.assertFalse(rec.agrees)    # haiku != sonnet, so it disagrees


class TestMalformedBlueprint(unittest.TestCase):
    def test_non_dict_step_raises_input_error(self):
        with self.assertRaises(AdviceInputError):
            advise_blueprint({"steps": ["oops"]})

    def test_non_dict_subagent_raises_input_error(self):
        with self.assertRaises(AdviceInputError):
            advise_blueprint({"subagents": ["oops"]})

    def test_non_list_steps_container_raises_input_error(self):
        # A string/scalar container must not crash via enumerate(); exit cleanly.
        with self.assertRaises(AdviceInputError):
            advise_blueprint({"steps": "notalist"})

    def test_scalar_subagents_container_raises_input_error(self):
        with self.assertRaises(AdviceInputError):
            advise_blueprint({"subagents": 5})


class TestBudgetWiring(unittest.TestCase):
    def setUp(self):
        self.bp = load_blueprint(os.path.join(FIXTURES, "valid_sample.blueprint.md"))

    def test_high_budget_caps_a_broad_step_effort_to_medium(self):
        low = {r.target_id: r for r in advise_blueprint(self.bp, budget_pressure="low")}
        high = {r.target_id: r for r in advise_blueprint(self.bp, budget_pressure="high")}
        self.assertEqual(low["plan"].recommended_effort, "high")
        self.assertEqual(high["plan"].recommended_effort, "medium")
        # The tier is unchanged by budget; only effort is bounded.
        self.assertEqual(high["plan"].recommended_model, "opus")


if __name__ == "__main__":
    unittest.main()
