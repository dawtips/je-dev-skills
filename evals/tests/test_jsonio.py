import unittest

from evals.evaluator.jsonio import JSONParseError, parse_json


class TestParseJson(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_array(self):
        self.assertEqual(parse_json('["x", "y"]'), ["x", "y"])

    def test_strips_json_fence(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_strips_bare_fence(self):
        self.assertEqual(parse_json('```\n[1, 2]\n```'), [1, 2])

    def test_bracket_slice_repair(self):
        # Leading/trailing prose around a JSON object is recovered.
        self.assertEqual(parse_json('Sure! {"a": 1} hope that helps'), {"a": 1})

    def test_invalid_raises(self):
        with self.assertRaises(JSONParseError):
            parse_json("not json at all")


if __name__ == "__main__":
    unittest.main()
