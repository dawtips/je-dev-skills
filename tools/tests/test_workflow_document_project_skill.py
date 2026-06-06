import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "workflow-document-project" / "SKILL.md"
EXCLUSIONS = ROOT / "skills" / "workflow-document-project" / "references" / "exclusions.md"
PROMPT = ROOT / "skills" / "workflow-document-project" / "references" / "synthesis-prompt.md"


class TestWorkflowDocumentProjectSkill(unittest.TestCase):
    def test_skill_documents_path_a_path_b_and_outputs(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("workflow-document-project", text)
        self.assertIn("Path A", text)
        self.assertIn("in_claude_code", text)
        self.assertIn("Path B", text)
        self.assertIn("anthropic_api", text)
        self.assertIn("<name>.blueprint.md", text)
        self.assertIn("<name>.project-doc.md", text)
        self.assertIn("strong_workflow_signal", text)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/workflow-document-project/scripts/document_project.py", text)

    def test_reference_docs_pin_redaction_and_synthesis_contracts(self):
        exclusions = EXCLUSIONS.read_text(encoding="utf-8")
        prompt = PROMPT.read_text(encoding="utf-8")

        self.assertIn(".env", exclusions)
        self.assertIn("*.pem", exclusions)
        self.assertIn("high-entropy", exclusions)
        self.assertIn("case-insensitive", exclusions)
        self.assertIn("single fenced JSON object", prompt)
        self.assertIn("Cite paths", prompt)
        self.assertIn("status: draft", prompt)
        # the prompt must convey the required payload substructure, not just the top-level keys
        self.assertIn("blueprint_prose", prompt)
        self.assertIn("report_sections", prompt)
        self.assertIn("Given-When-Then", prompt)


    def test_readme_and_plugin_metadata_include_new_skill(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        plugin = (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")

        self.assertIn("workflow-document-project", readme)
        self.assertIn("/je-dev-skills:workflow-document-project", readme)
        self.assertIn("project inventory", readme)
        self.assertIn("project-documentation", plugin)
        self.assertIn("inventory", plugin)


if __name__ == "__main__":
    unittest.main()
