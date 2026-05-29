import os
import unittest

from validate_blueprint import check_subagents, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestSubagents(unittest.TestCase):
    def test_complete_contract_passes(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_full.blueprint.md"))
        self.assertEqual(check_subagents(bp), [])

    def test_partial_contract_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_partial_contract.blueprint.md"))
        gaps = check_subagents(bp)
        self.assertTrue(any(g.path == "subagents[0].boundaries" for g in gaps))

    def test_empty_tools_is_a_gap(self):
        bp = {"steps": [{"id": "a", "kind": "agentic", "rationale": "r", "termination": "x"}],
              "subagents": [{"objective": "o", "output_format": "f", "tools": [],
                             "boundaries": "b", "model": "sonnet", "effort": "low"}]}
        gaps = check_subagents(bp)
        self.assertTrue(any(g.path == "subagents[0].tools" for g in gaps))

    def test_subagents_without_agentic_step_is_a_gap(self):
        bp = {"steps": [{"id": "a", "kind": "deterministic", "rationale": "r"}],
              "subagents": [{"objective": "o", "output_format": "f", "tools": ["x"],
                             "boundaries": "b", "model": "sonnet", "effort": "low"}]}
        gaps = check_subagents(bp)
        self.assertTrue(any(g.path == "subagents" for g in gaps))
