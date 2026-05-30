import unittest

from advise_model import (
    MODEL_IDS,
    TIERS,
    EFFORTS,
    TaskSignals,
    score,
    _step_down,
    _max_tier,
)


class TestPrimitives(unittest.TestCase):
    def test_tiers_ordered_cheap_to_capable(self):
        self.assertEqual(TIERS, ("haiku", "sonnet", "opus"))

    def test_efforts_ordered_light_to_heavy(self):
        self.assertEqual(EFFORTS, ("low", "medium", "high", "max"))

    def test_model_ids_cover_exactly_the_recommendable_tiers(self):
        self.assertEqual(set(MODEL_IDS), set(TIERS))
        for tier, model_id in MODEL_IDS.items():
            self.assertTrue(model_id.startswith("claude-"), tier)

    def test_step_down_clamps_at_floor(self):
        self.assertEqual(_step_down("opus"), "sonnet")
        self.assertEqual(_step_down("sonnet"), "haiku")
        self.assertEqual(_step_down("haiku"), "haiku")

    def test_max_tier(self):
        self.assertEqual(_max_tier("haiku", "opus"), "opus")
        self.assertEqual(_max_tier("sonnet", "haiku"), "sonnet")

    def test_task_signals_rejects_bad_values(self):
        with self.assertRaises(ValueError):
            TaskSignals(difficulty="epic", breadth="narrow", role="step")
        with self.assertRaises(ValueError):
            TaskSignals(difficulty="easy", breadth="narrow", role="boss")


class TestScore(unittest.TestCase):
    def test_email_triage_route_step_is_haiku_low(self):
        # model-selection.md worked example: classification into fixed buckets.
        s = TaskSignals(difficulty="easy", breadth="narrow", role="step")
        tier, effort, rationale = score(s)
        self.assertEqual((tier, effort), ("haiku", "low"))
        self.assertTrue(rationale.endswith("."))

    def test_competitor_worker_is_sonnet_medium(self):
        # Worker, but NOT narrow (a few sources) -> no step-down; stays sonnet.
        s = TaskSignals(difficulty="moderate", breadth="moderate", role="worker")
        self.assertEqual(score(s)[:2], ("sonnet", "medium"))

    def test_research_orchestrator_is_opus_high(self):
        s = TaskSignals(difficulty="hard", breadth="broad", role="orchestrator")
        self.assertEqual(score(s)[:2], ("opus", "high"))

    def test_narrow_bounded_worker_steps_down_one_tier(self):
        s = TaskSignals(difficulty="moderate", breadth="narrow", role="worker")
        self.assertEqual(score(s)[0], "haiku")

    def test_orchestrator_is_never_below_opus(self):
        s = TaskSignals(difficulty="easy", breadth="narrow", role="orchestrator")
        self.assertEqual(score(s)[0], "opus")

    def test_budget_pressure_caps_effort_at_medium(self):
        # High cost pressure bounds the ~15x effort multiplier; tier is unchanged.
        s = TaskSignals(difficulty="hard", breadth="broad", role="step",
                        budget_pressure="high")
        self.assertEqual(score(s)[:2], ("opus", "medium"))

    def test_budget_pressure_caps_orchestrator_effort_too(self):
        s = TaskSignals(difficulty="hard", breadth="broad", role="orchestrator",
                        budget_pressure="high")
        self.assertEqual(score(s)[:2], ("opus", "medium"))

    def test_budget_pressure_does_not_raise_low_effort(self):
        s = TaskSignals(difficulty="easy", breadth="narrow", role="step",
                        budget_pressure="high")
        self.assertEqual(score(s)[1], "low")


if __name__ == "__main__":
    unittest.main()
