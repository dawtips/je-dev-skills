import os
import unittest

from validate_blueprint import check_steps, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestSteps(unittest.TestCase):
    def test_valid_minimal_has_no_step_gaps(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        self.assertEqual(check_steps(bp), [])

    def test_missing_rationale_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_missing_rationale.blueprint.md"))
        gaps = check_steps(bp)
        self.assertTrue(any("rationale" in g.path for g in gaps))

    def test_invalid_kind_is_a_gap(self):
        bp = {"steps": [{"id": "x", "kind": "magic", "rationale": "r"}]}
        gaps = check_steps(bp)
        self.assertTrue(any(g.path == "steps[0].kind" for g in gaps))

    def test_agentic_step_requires_termination(self):
        bp = {"steps": [{"id": "x", "kind": "agentic", "rationale": "judgment"}]}
        gaps = check_steps(bp)
        self.assertTrue(any(g.path == "steps[0].termination" for g in gaps))

    def test_side_effecting_requires_idempotency_key(self):
        bp = {"steps": [{"id": "x", "kind": "deterministic", "rationale": "r",
                         "side_effecting": True, "retry": {"policy": "x3"}}]}
        gaps = check_steps(bp)
        self.assertTrue(any("idempotency_key" in g.path for g in gaps))

    def test_reversible_requires_rollback(self):
        bp = {"steps": [{"id": "x", "kind": "deterministic", "rationale": "r",
                         "reversible": True}]}
        gaps = check_steps(bp)
        self.assertTrue(any(g.path == "steps[0].rollback" for g in gaps))
