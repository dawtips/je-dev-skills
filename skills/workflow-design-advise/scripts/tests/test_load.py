import os
import tempfile
import unittest

from advise_model import AdviceInputError, extract_yaml_block, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestLoad(unittest.TestCase):
    def test_extract_single_block(self):
        text = "intro\n```yaml\na: 1\n```\nend"
        self.assertEqual(extract_yaml_block(text), "a: 1")

    def test_extract_rejects_zero_blocks(self):
        with self.assertRaises(AdviceInputError):
            extract_yaml_block("no fenced yaml here")

    def test_extract_rejects_multiple_blocks(self):
        text = "```yaml\na: 1\n```\n```yaml\nb: 2\n```"
        with self.assertRaises(AdviceInputError):
            extract_yaml_block(text)

    def test_load_fixture_returns_mapping(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_sample.blueprint.md"))
        self.assertEqual([s["id"] for s in bp["steps"]],
                         ["plan", "research-each", "classify", "verify"])
        self.assertEqual(bp["subagents"][0]["model"], "opus")

    def test_load_missing_file_raises_input_error(self):
        with self.assertRaises(AdviceInputError):
            load_blueprint(os.path.join(FIXTURES, "does_not_exist.blueprint.md"))

    def test_invalid_yaml_block_raises(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".blueprint.md", delete=False, encoding="utf-8") as f:
            f.write("# x\n\n```yaml\nkey: [unclosed\n```\n")
            name = f.name
        try:
            with self.assertRaises(AdviceInputError) as cm:
                load_blueprint(name)
            self.assertIn("invalid yaml", str(cm.exception))
        finally:
            os.unlink(name)

    def test_non_mapping_block_raises(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".blueprint.md", delete=False, encoding="utf-8") as f:
            f.write("# x\n\n```yaml\n- a\n- b\n```\n")
            name = f.name
        try:
            with self.assertRaises(AdviceInputError) as cm:
                load_blueprint(name)
            self.assertIn("must parse to a mapping", str(cm.exception))
        finally:
            os.unlink(name)


if __name__ == "__main__":
    unittest.main()
