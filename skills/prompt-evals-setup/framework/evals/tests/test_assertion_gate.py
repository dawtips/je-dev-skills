import unittest

from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict


class TestAssertionGate(unittest.TestCase):
    def test_mandatory_failure_skips_judge_by_default(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory"}],
            policy="gate_mandatory",
        )

        self.assertTrue(gate["mandatory_failed"])
        self.assertTrue(gate["judge_skipped"])
        self.assertEqual(gate["results"][0]["action"], "gate")

    def test_advisory_failure_does_not_skip_judge(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "advisory"}],
            policy="gate_mandatory",
        )

        self.assertFalse(gate["mandatory_failed"])
        self.assertFalse(gate["judge_skipped"])
        self.assertEqual(gate["results"][0]["action"], "annotate")

    def test_per_assertion_annotate_override_keeps_judge(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory", "policy": "annotate"}],
            policy="gate_mandatory",
        )

        self.assertTrue(gate["mandatory_failed"])
        self.assertFalse(gate["judge_skipped"])
        self.assertEqual(gate["results"][0]["action"], "annotate")

    def test_annotate_only_policy_keeps_judge(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory"}],
            policy="annotate_only",
        )

        self.assertTrue(gate["mandatory_failed"])
        self.assertFalse(gate["judge_skipped"])

    def test_synthetic_verdict_is_deterministic_floor(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory"}],
            policy="gate_mandatory",
        )

        verdict = synthetic_gated_verdict(gate)

        self.assertEqual(verdict["score"], 1)
        self.assertEqual(verdict["strengths"], [])
        self.assertIn("Skipped judge", verdict["reasoning"])
        self.assertIn("missing 'kcal'", verdict["weaknesses"][0])


if __name__ == "__main__":
    unittest.main()
