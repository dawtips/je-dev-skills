"""Doc tests for the plugin-resident default of prompt-evals-setup (T-018)."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "skills" / "prompt-evals-setup" / "SKILL.md"
RUN = ROOT / "skills" / "prompt-evals-run" / "SKILL.md"


def _frontmatter_description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("description:"):
            return line
    return ""


class TestPromptEvalsSetupSkill(unittest.TestCase):
    def test_setup_skill_describes_plugin_resident_artifacts(self):
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("evals/<name>/eval.json", text)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", text)
        self.assertIn("command-adapter", text)
        self.assertIn("prompt-file", text)

    def test_setup_default_is_scaffold_not_framework_vendoring(self):
        text = SETUP.read_text(encoding="utf-8")
        desc = _frontmatter_description(SETUP)
        # The headline behavior must no longer be "vendor the framework into ./evals".
        self.assertNotIn("vendors the bundled Python eval framework into ./evals", desc)
        self.assertIn("scaffold", text.lower())
        self.assertIn("scaffold-artifact", text)

    def test_setup_keeps_migration_note_for_vendored_projects(self):
        text = SETUP.read_text(encoding="utf-8").lower()
        self.assertIn("migration", text)

    def test_run_skill_documents_artifact_run_path(self):
        text = RUN.read_text(encoding="utf-8")
        self.assertIn("render-artifact", text)
        self.assertIn("evaluate-artifact", text)
        # The in-CC report assembler is repointed at the project's artifact runs dir.
        self.assertIn("--runs-dir", text)

    def test_run_skill_documents_structured_output_paths(self):
        text = RUN.read_text(encoding="utf-8")
        for token in [
            "target.output_schema",
            "forced structured-output tool",
            "strict: true",
            "tool_choice",
            "output-sink tool",
            "fail closed",
            "zero tool calls",
            "multiple tool calls",
            "malformed JSON",
            "max_tokens",
            "output_config",
            "CANDIDATE_FILE",
        ]:
            self.assertIn(token, text)

    def test_run_skill_validates_structured_candidate_before_persisting_output(self):
        text = RUN.read_text(encoding="utf-8")
        start = text.index("# With target.output_schema:")
        end = text.index("# Without target.output_schema:")
        branch = text[start:end]

        candidate_write = 'printf \'%s\' "$RAW_OUTPUT" > "$CANDIDATE_FILE"'
        validation = 'python3 -m evals.output_schema --eval-json "$EVAL" --output-file "$CANDIDATE_FILE"'
        cleanup = 'rm -f "$CANDIDATE_FILE"'
        publish = 'mv "$CANDIDATE_FILE" "$OUTPUT_FILE"'

        for token in [candidate_write, validation, cleanup, publish]:
            self.assertIn(token, branch)
        self.assertLess(branch.index(candidate_write), branch.index(validation))
        self.assertLess(branch.index(validation), branch.index(cleanup))
        self.assertLess(branch.index(cleanup), branch.index(publish))
        self.assertNotIn('> "$OUTPUT_FILE"', branch)


if __name__ == "__main__":
    unittest.main()
