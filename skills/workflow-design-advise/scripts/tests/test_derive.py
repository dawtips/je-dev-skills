import unittest

from advise_model import (
    STEP_PATTERN_SIGNALS,
    TaskSignals,
    derive_signals_for_step,
    derive_signals_for_subagent,
)


class TestDeriveStep(unittest.TestCase):
    def test_deterministic_step_yields_no_signals(self):
        signals, needs_review = derive_signals_for_step(
            {"id": "x", "kind": "deterministic", "pattern": "none"})
        self.assertIsNone(signals)
        self.assertFalse(needs_review)

    def test_route_step_is_easy_narrow(self):
        signals, needs_review = derive_signals_for_step(
            {"id": "c", "kind": "agentic", "pattern": "route"})
        self.assertEqual(signals, TaskSignals("easy", "narrow", "step"))
        self.assertFalse(needs_review)

    def test_orchestrate_step_is_orchestrator(self):
        signals, _ = derive_signals_for_step(
            {"id": "p", "kind": "agentic", "pattern": "orchestrate"})
        self.assertEqual(signals.role, "orchestrator")
        self.assertEqual(signals.difficulty, "hard")

    def test_agentic_step_without_known_pattern_flags_review(self):
        signals, needs_review = derive_signals_for_step(
            {"id": "q", "kind": "agentic", "pattern": "none"})
        self.assertEqual(signals, TaskSignals("moderate", "moderate", "step"))
        self.assertTrue(needs_review)

    def test_all_known_patterns_match_the_constant(self):
        # Pins every STEP_PATTERN_SIGNALS row (chain/evaluate/parallelize too).
        for pattern, (difficulty, breadth, role) in STEP_PATTERN_SIGNALS.items():
            signals, needs_review = derive_signals_for_step(
                {"id": pattern, "kind": "agentic", "pattern": pattern})
            self.assertEqual(signals, TaskSignals(difficulty, breadth, role), pattern)
            self.assertFalse(needs_review, pattern)


class TestDeriveSubagent(unittest.TestCase):
    def test_two_tool_worker_is_moderate_breadth_and_flags_review(self):
        signals, needs_review = derive_signals_for_subagent(
            {"id": "w", "tools": ["web_search", "web_fetch"]})
        self.assertEqual(signals, TaskSignals("moderate", "moderate", "worker"))
        self.assertTrue(needs_review)  # difficulty is assumed, not derived

    def test_single_tool_worker_is_narrow(self):
        signals, _ = derive_signals_for_subagent({"id": "w", "tools": ["lookup"]})
        self.assertEqual(signals.breadth, "narrow")

    def test_many_tool_worker_is_broad(self):
        signals, _ = derive_signals_for_subagent(
            {"id": "w", "tools": ["a", "b", "c", "d"]})
        self.assertEqual(signals.breadth, "broad")

    def test_missing_tools_treated_as_narrow(self):
        signals, _ = derive_signals_for_subagent({"id": "w"})
        self.assertEqual(signals.breadth, "narrow")


if __name__ == "__main__":
    unittest.main()
