import os
import unittest

from validate_blueprint import check_rubrics, check_outcomes, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRubricsOutcomes(unittest.TestCase):
    def test_valid_full_rubrics_pass(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_full.blueprint.md"))
        self.assertEqual(check_rubrics(bp), [])

    def test_gateless_rubric_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_gateless_rubric.blueprint.md"))
        gaps = check_rubrics(bp)
        self.assertTrue(any(g.path == "rubrics[0].gate" for g in gaps))

    def test_rubric_without_levels_is_a_gap(self):
        bp = {"rubrics": [{"name": "x", "scale": "1-5", "gate": 3}]}
        gaps = check_rubrics(bp)
        self.assertTrue(any(g.path == "rubrics[0].levels" for g in gaps))

    def test_valid_full_outcomes_pass(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_full.blueprint.md"))
        self.assertEqual(check_outcomes(bp), [])

    def test_outcome_missing_then_is_a_gap(self):
        bp = {"outcomes": [{"given": "g", "when": "w"}]}
        gaps = check_outcomes(bp)
        self.assertTrue(any(g.path == "outcomes[0].then" for g in gaps))
