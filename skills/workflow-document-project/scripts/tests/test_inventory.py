import tempfile
import unittest
from pathlib import Path

from document_project import (
    classify_path,
    inventory_project,
    is_excluded_path,
    redact_excerpt,
)


FIXTURES = Path(__file__).parent / "fixtures"
PROJECT = FIXTURES / "inventory_project"


class TestInventory(unittest.TestCase):
    def test_exclusions_skip_generated_caches_and_secret_paths(self):
        excluded = [
            PROJECT / ".git" / "config",
            PROJECT / ".worktrees" / "feature" / "file.py",
            PROJECT / "node_modules" / "pkg" / "index.js",
            PROJECT / ".venv" / "pyvenv.cfg",
            PROJECT / "evals" / "runs" / "run-1" / "output.json",
            # eval-run outputs are excluded at any depth, not just at the root
            PROJECT / "skills" / "x" / "framework" / "evals" / "runs" / "r" / "out.json",
            PROJECT / ".env",
            PROJECT / "deploy.pem",
            PROJECT / ".ssh" / "id_rsa",
            PROJECT / ".npmrc",
            # directory matching is case-insensitive
            PROJECT / ".AWS" / "config",
            PROJECT / "Node_Modules" / "x.js",
            PROJECT / ".Git" / "HEAD",
        ]
        for path in excluded:
            with self.subTest(path=path):
                self.assertTrue(is_excluded_path(path, PROJECT))

    def test_redaction_masks_tokens_before_excerpt_storage(self):
        text = (
            "api_key = 'sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890'\n"
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890\n"
            "normal workflow text"
        )
        redacted = redact_excerpt(text)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("normal workflow text", redacted)
        self.assertNotIn("sk-ant-api03", redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz1234567890", redacted)

    def test_redaction_masks_underscore_joined_and_punctuated_secrets(self):
        text = (
            "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY\n"
            "client_secret = sk_live_0123456789abcdefXYZ\n"
            "password = hunter2plaintextpwd\n"
            "private_key = MIIBOwIBAAJBANcd1234\n"
            "access_token = abc123def456ghi789\n"
            "bare AKIAIOSFODNN7EXAMPLE here\n"
        )
        redacted = redact_excerpt(text)
        for leak in (
            "wJalrXUtnFEMI",
            "sk_live_0123456789abcdefXYZ",
            "hunter2plaintextpwd",
            "MIIBOwIBAAJBANcd1234",
            "abc123def456ghi789",
            "AKIAIOSFODNN7EXAMPLE",
        ):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, redacted)

    def test_redaction_preserves_non_secret_identifiers_and_hashes(self):
        text = (
            "commit a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 fixes the bug\n"
            "uuid 550e8400e29b41d4a716446655440000 here\n"
            "uuid2 550e8400-e29b-41d4-a716-446655440000 here\n"
            "def test_inventory_separates_artifacts_signals_and_questions():\n"
        )
        redacted = redact_excerpt(text)
        for keep in (
            "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
            "550e8400e29b41d4a716446655440000",
            "550e8400-e29b-41d4-a716-446655440000",
            "test_inventory_separates_artifacts_signals_and_questions",
        ):
            with self.subTest(keep=keep):
                self.assertIn(keep, redacted)

    def test_classification_covers_project_artifact_types(self):
        cases = {
            "README.md": "guidance",
            "AGENTS.md": "guidance",
            ".story/tickets/T-001.json": "durable_memory",
            "docs/superpowers/specs/example-spec.md": "spec",
            "docs/superpowers/plans/example-plan.md": "plan",
            "workflows/existing.blueprint.md": "workflow",
            "skills/example/SKILL.md": "skill",
            "scripts/run.py": "script",
            "tests/test_run.py": "test",
            "prompts/planner.md": "prompt",
            "package.json": "config",
            "src/app.py": "source",
        }
        for rel, category in cases.items():
            with self.subTest(rel=rel):
                self.assertEqual(classify_path(Path(rel)), category)

    def test_inventory_separates_artifacts_signals_and_questions(self):
        inventory = inventory_project(PROJECT, workflow_name="existing")

        paths = {artifact.path for artifact in inventory.artifacts}
        self.assertIn("README.md", paths)
        self.assertIn("workflows/existing.blueprint.md", paths)
        self.assertIn(".story/tickets/T-001.json", paths)
        self.assertNotIn(".env", paths)
        self.assertIn("has workflow blueprint", inventory.signals)
        self.assertIn("has tests", inventory.signals)
        self.assertIn("has script entry point", inventory.signals)
        self.assertEqual(inventory.existing_blueprints, ["workflows/existing.blueprint.md"])
        self.assertTrue(inventory.strong_workflow_signal)
        self.assertIn("Infer workflow purpose from observed artifacts.", inventory.inference_requests)
        self.assertIn("guidance: README.md", inventory.observed_facts)

    def test_inventory_without_signal_is_explicit_not_fabricated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "README.md").write_text("# Notes\n\nNo workflow here.\n", encoding="utf-8")
            inventory = inventory_project(root, workflow_name="notes")

        self.assertFalse(inventory.strong_workflow_signal)
        self.assertIn("No strong workflow signal found.", inventory.open_questions)


if __name__ == "__main__":
    unittest.main()
