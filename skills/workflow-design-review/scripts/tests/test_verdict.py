import unittest

from review_blueprint import (
    compute_exit_code,
    compute_flags,
    compute_verdict,
    parse_review_payload,
)
from tests.fake_client import valid_payload


class TestVerdictLogic(unittest.TestCase):
    def test_flags_dimensions_below_threshold(self):
        result = parse_review_payload(valid_payload())
        flags = compute_flags(result, threshold=3)
        self.assertEqual([f.name for f in flags], ["determinism_classification"])

    def test_weakest_link_verdict_ignores_judge_verdict(self):
        result = parse_review_payload(valid_payload())
        self.assertEqual(result.judge_verdict, "solid")
        self.assertEqual(compute_verdict(result, threshold=3), "needs-revision")

    def test_solid_when_no_scores_below_threshold(self):
        result = parse_review_payload(valid_payload({"determinism_classification": 3}))
        self.assertEqual(compute_flags(result, threshold=3), [])
        self.assertEqual(compute_verdict(result, threshold=3), "solid")

    def test_default_exit_is_zero_even_with_flags(self):
        result = parse_review_payload(valid_payload())
        self.assertEqual(compute_exit_code(result, strict=False, threshold=3), 0)

    def test_strict_exit_is_one_with_flags(self):
        result = parse_review_payload(valid_payload())
        self.assertEqual(compute_exit_code(result, strict=True, threshold=3), 1)

    def test_strict_exit_is_zero_without_flags(self):
        result = parse_review_payload(valid_payload({"determinism_classification": 3}))
        self.assertEqual(compute_exit_code(result, strict=True, threshold=3), 0)


if __name__ == "__main__":
    unittest.main()
