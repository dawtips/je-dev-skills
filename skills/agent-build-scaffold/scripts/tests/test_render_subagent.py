import os
import unittest

from scaffold import load_blueprint, render_subagent, subagent_filename

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderSubagent(unittest.TestCase):
    def test_renders_subagent_frontmatter_and_body_contract(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        text = render_subagent(bp["subagents"][0])
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: reason-classifier", text)
        self.assertIn("model: haiku", text)
        self.assertIn("tools: Read", text)
        frontmatter = text.split("---", 2)[1]
        self.assertNotIn("output_format", frontmatter)
        self.assertIn("## Objective", text)
        self.assertIn("classify the customer's refund reason", text)
        self.assertIn("## Output Format", text)
        self.assertIn("JSON {category: string, confidence: number}", text)
        self.assertIn("## Boundaries", text)
        self.assertIn("never issue a refund", text)
        self.assertIn("Recommended effort: low", text)

    def test_subagent_filename_slugifies_id(self):
        self.assertEqual(
            subagent_filename({"id": "Reason Classifier!"}),
            "reason-classifier.md",
        )


if __name__ == "__main__":
    unittest.main()
