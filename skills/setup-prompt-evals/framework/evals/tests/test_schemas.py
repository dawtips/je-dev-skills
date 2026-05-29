import unittest

from evals.evaluator.schemas import (
    Step,
    Trajectory,
    normalize_trajectory,
    validate_test_case,
    validate_verdict,
)

ALLOWED = ["height", "weight", "goal"]


def good_case():
    return {
        "prompt_inputs": {"height": "180cm", "weight": "80kg", "goal": "cut"},
        "solution_criteria": ["Has a caloric total."],
    }


class TestValidateTestCase(unittest.TestCase):
    def test_valid(self):
        validate_test_case(good_case(), ALLOWED)

    def test_missing_key(self):
        case = good_case()
        del case["prompt_inputs"]["goal"]
        with self.assertRaises(ValueError):
            validate_test_case(case, ALLOWED)

    def test_extra_key(self):
        case = good_case()
        case["prompt_inputs"]["age"] = "30"
        with self.assertRaises(ValueError):
            validate_test_case(case, ALLOWED)

    def test_too_many_criteria(self):
        case = good_case()
        case["solution_criteria"] = ["a", "b", "c", "d", "e"]
        with self.assertRaises(ValueError):
            validate_test_case(case, ALLOWED)

    def test_empty_criteria(self):
        case = good_case()
        case["solution_criteria"] = []
        with self.assertRaises(ValueError):
            validate_test_case(case, ALLOWED)


class TestTrajectory(unittest.TestCase):
    def test_string_normalizes_to_single_shot(self):
        traj = normalize_trajectory("hello")
        self.assertEqual(traj.final_output, "hello")
        self.assertFalse(traj.is_agentic)

    def test_trajectory_passthrough(self):
        traj = Trajectory(final_output="x", steps=[Step(role="assistant", content="hi")])
        self.assertIs(normalize_trajectory(traj), traj)
        self.assertTrue(traj.is_agentic)

    def test_bad_type_raises(self):
        with self.assertRaises(TypeError):
            normalize_trajectory(123)


class TestValidateVerdict(unittest.TestCase):
    def test_clamps_high(self):
        self.assertEqual(validate_verdict({"score": 99})["score"], 10)

    def test_clamps_low(self):
        self.assertEqual(validate_verdict({"score": -4})["score"], 1)

    def test_rounds_float(self):
        self.assertEqual(validate_verdict({"score": 7.6})["score"], 8)

    def test_fills_defaults(self):
        v = validate_verdict({"score": 5})
        self.assertEqual(v["strengths"], [])
        self.assertEqual(v["weaknesses"], [])

    def test_missing_score_raises(self):
        with self.assertRaises(ValueError):
            validate_verdict({"reasoning": "x"})


if __name__ == "__main__":
    unittest.main()
