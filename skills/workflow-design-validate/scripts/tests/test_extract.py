import os
import unittest

from validate_blueprint import extract_yaml_block, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtract(unittest.TestCase):
    def test_extracts_single_yaml_block(self):
        text = "intro\n```yaml\na: 1\n```\noutro"
        self.assertEqual(extract_yaml_block(text).strip(), "a: 1")

    def test_rejects_zero_blocks(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("no fenced yaml here")

    def test_rejects_multiple_blocks(self):
        text = "```yaml\na: 1\n```\n```yaml\nb: 2\n```"
        with self.assertRaises(ValueError):
            extract_yaml_block(text)

    def test_load_blueprint_returns_dict(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        self.assertEqual(bp["name"] if "name" in bp else bp["steps"][0]["id"], "transform")
        self.assertEqual(bp["steps"][0]["kind"], "deterministic")

    def test_load_blueprint_rejects_non_mapping(self):
        # A comment-only block parses to None; a top-level list parses to a list.
        # Neither is a valid blueprint — raise ValueError so the CLI maps it to exit 2.
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_nondict.blueprint.md"))
