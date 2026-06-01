import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "workflow-design-visualize" / "SKILL.md"
SCRIPT = ROOT / "skills" / "workflow-design-visualize" / "scripts" / "visualize_blueprint.py"
REQS = ROOT / "skills" / "workflow-design-visualize" / "scripts" / "requirements.txt"


class TestWorkflowDesignVisualizeSkill(unittest.TestCase):
    def test_skill_frontmatter_and_procedure(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: workflow-design-visualize", text)
        self.assertIn("allowed-tools: Bash, Read, Glob", text)
        self.assertIn("<name>.diagram.md", text)
        self.assertIn("mermaid", text)
        self.assertIn("list order", text)
        self.assertIn("workflow-design-validate", text)
        self.assertIn(
            "${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-visualize/scripts/visualize_blueprint.py",
            text,
        )

    def test_requirements_pins_pyyaml(self):
        self.assertIn("PyYAML", REQS.read_text(encoding="utf-8"))

    def test_script_exists(self):
        self.assertTrue(SCRIPT.is_file())

    def test_readme_and_plugin_metadata_include_visualize(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        plugin = (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        self.assertIn("visualize", readme)
        self.assertIn("mermaid", plugin)
        self.assertIn("diagram", plugin)


if __name__ == "__main__":
    unittest.main()
