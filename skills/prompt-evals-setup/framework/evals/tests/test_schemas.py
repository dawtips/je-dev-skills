import unittest

from evals.evaluator.schemas import (
    Step,
    Trajectory,
    normalize_trajectory,
    test_case_schema,
    validate_test_case,
    validate_verdict,
    verdict_schema,
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


class TestStructuredOutputSchemas(unittest.TestCase):
    """The structured-output schemas must stay within the subset the provider
    supports (object root, every property required, additionalProperties:false)
    and match the shapes the validators expect."""

    def test_test_case_schema_locks_closed_key_set(self):
        schema = test_case_schema(ALLOWED)
        inputs = schema["properties"]["prompt_inputs"]
        self.assertEqual(set(inputs["properties"]), set(ALLOWED))
        self.assertEqual(sorted(inputs["required"]), sorted(ALLOWED))
        self.assertFalse(inputs["additionalProperties"])

    def test_test_case_schema_root_is_strict_object(self):
        schema = test_case_schema(ALLOWED)
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            sorted(schema["required"]), ["prompt_inputs", "solution_criteria"]
        )
        # every declared property is required (structured-output requirement)
        self.assertEqual(set(schema["properties"]), set(schema["required"]))

    def test_test_case_schema_output_passes_validator(self):
        # A payload conforming to the schema must satisfy validate_test_case.
        case = {
            "prompt_inputs": {k: "x" for k in ALLOWED},
            "solution_criteria": ["Has a caloric total."],
        }
        validate_test_case(case, ALLOWED)

    def test_verdict_schema_shape(self):
        schema = verdict_schema()
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(schema["required"]))
        self.assertEqual(
            sorted(schema["required"]),
            ["reasoning", "score", "strengths", "weaknesses"],
        )
        self.assertEqual(schema["properties"]["score"]["type"], "integer")


if __name__ == "__main__":
    unittest.main()
