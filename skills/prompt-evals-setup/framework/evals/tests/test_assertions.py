import unittest

from evals.assertions import all_passed, check_assertion, check_assertions


class TestCheckAssertion(unittest.TestCase):
    def test_contains_pass_and_fail(self):
        self.assertTrue(check_assertion("Total: 2400 kcal", {"type": "contains", "value": "kcal"})["passed"])
        self.assertFalse(check_assertion("no macros", {"type": "contains", "value": "kcal"})["passed"])

    def test_regex(self):
        self.assertTrue(check_assertion("2400 kcal", {"type": "regex", "pattern": r"\d+ kcal"})["passed"])

    def test_min_and_max_length(self):
        self.assertTrue(check_assertion("abcdef", {"type": "min_length", "value": 3})["passed"])
        self.assertFalse(check_assertion("abcdef", {"type": "max_length", "value": 3})["passed"])

    def test_json_valid_and_has_key(self):
        self.assertTrue(check_assertion('{"a": 1}', {"type": "json_valid"})["passed"])
        self.assertFalse(check_assertion("nope", {"type": "json_valid"})["passed"])
        self.assertTrue(check_assertion('{"a": 1}', {"type": "json_has_key", "key": "a"})["passed"])
        self.assertFalse(check_assertion('{"a": 1}', {"type": "json_has_key", "key": "b"})["passed"])

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            check_assertion("x", {"type": "bogus"})


class TestCheckAssertions(unittest.TestCase):
    def test_all_passed(self):
        specs = [{"type": "contains", "value": "kcal"}, {"type": "min_length", "value": 2}]
        results = check_assertions("2400 kcal", specs)
        self.assertEqual(len(results), 2)
        self.assertTrue(all_passed(results))

    def test_one_failure_breaks_all_passed(self):
        specs = [{"type": "contains", "value": "kcal"}, {"type": "contains", "value": "ZZZ"}]
        self.assertFalse(all_passed(check_assertions("2400 kcal", specs)))


if __name__ == "__main__":
    unittest.main()
