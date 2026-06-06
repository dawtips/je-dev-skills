import os
import unittest

from visualize_blueprint import extract_yaml_block, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtract(unittest.TestCase):
    def test_extracts_single_yaml_block(self):
        text = "intro\n```yaml\na: 1\n```\noutro"
        self.assertEqual(extract_yaml_block(text).strip(), "a: 1")

    def test_rejects_zero_blocks(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("no fenced yaml here")

    def test_rejects_multiple_blocks(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("```yaml\na: 1\n```\n```yaml\nb: 2\n```")

    def test_load_returns_mapping(self):
        bp = load_blueprint(os.path.join(FIXTURES, "minimal.blueprint.md"))
        self.assertIsInstance(bp, dict)
        self.assertEqual(bp["steps"][0]["id"], "do_thing")

    def test_load_rejects_non_mapping(self):
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_non_mapping.blueprint.md"))

    def test_load_rejects_no_yaml(self):
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_no_yaml.blueprint.md"))

    def test_load_rejects_two_yaml(self):
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_two_yaml.blueprint.md"))


if __name__ == "__main__":
    unittest.main()
