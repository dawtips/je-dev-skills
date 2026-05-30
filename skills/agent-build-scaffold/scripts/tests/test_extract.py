import os
import unittest

from scaffold import extract_yaml_block, load_blueprint, slugify

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtract(unittest.TestCase):
    def test_loads_full_blueprint_as_mapping(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.assertIsInstance(bp, dict)
        self.assertEqual(len(bp["steps"]), 3)
        self.assertEqual(bp["subagents"][0]["id"], "reason-classifier")

    def test_extract_requires_exactly_one_block(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("no fenced block here")

    def test_slugify_normalizes(self):
        self.assertEqual(slugify("Reason Classifier!"), "reason-classifier")
        self.assertEqual(slugify("fetch_order"), "fetch-order")
        self.assertEqual(slugify("  A  B  "), "a-b")


if __name__ == "__main__":
    unittest.main()
