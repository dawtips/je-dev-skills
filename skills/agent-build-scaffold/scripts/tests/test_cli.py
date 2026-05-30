import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from scaffold import main, scaffold_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestCli(unittest.TestCase):
    def test_scaffold_blueprint_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            written, warnings = scaffold_blueprint(
                os.path.join(FIXTURES, "refund-triage.blueprint.md"),
                tmp,
            )
            rel = sorted(os.path.relpath(path, tmp) for path in written)
            self.assertEqual(warnings, [])
            self.assertIn(".claude/agents/reason-classifier.md", rel)
            self.assertIn(".claude/scripts/fetch-order.sh", rel)
            self.assertIn(".claude/scripts/issue-refund.sh", rel)
            self.assertIn(".claude/hooks/classification-accuracy-gate.sh", rel)
            self.assertIn(".claude/hooks.json", rel)
            self.assertIn(".claude/commands/refund-triage.md", rel)

    def test_main_dry_run_reports_warnings_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            rc = main([
                os.path.join(FIXTURES, "overpowered.blueprint.md"),
                "--out-dir",
                tmp,
                "--dry-run",
            ], stdout=out)
            self.assertEqual(rc, 0)
            self.assertIn("DRY RUN", out.getvalue())
            self.assertIn("WARNING", out.getvalue())
            self.assertFalse(os.path.exists(os.path.join(tmp, ".claude")))

    def test_main_returns_two_for_bad_blueprint(self):
        err = io.StringIO()
        rc = main([
            os.path.join(FIXTURES, "broken_no_yaml.blueprint.md"),
        ], stderr=err)
        self.assertEqual(rc, 2)
        self.assertIn("ERROR:", err.getvalue())

    def test_main_writes_files_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            rc = main([
                os.path.join(FIXTURES, "csv-to-slack.blueprint.md"),
                "--out-dir",
                tmp,
            ], stdout=out)
            self.assertEqual(rc, 0)
            self.assertIn("wrote", out.getvalue())
            self.assertTrue(os.path.exists(os.path.join(tmp, ".claude/scripts/parse-csv.sh")))
            self.assertTrue(os.path.exists(os.path.join(tmp, ".claude/commands/csv-to-slack.md")))

    def test_main_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".claude", "commands")
            os.makedirs(path)
            with open(os.path.join(path, "csv-to-slack.md"), "w", encoding="utf-8") as f:
                f.write("existing")
            err = io.StringIO()
            rc = main([
                os.path.join(FIXTURES, "csv-to-slack.blueprint.md"),
                "--out-dir",
                tmp,
            ], stderr=err)
            self.assertEqual(rc, 2)
            self.assertIn("already exists", err.getvalue())

    def test_main_force_allows_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".claude", "commands")
            os.makedirs(path)
            with open(os.path.join(path, "csv-to-slack.md"), "w", encoding="utf-8") as f:
                f.write("existing")
            rc = main([
                os.path.join(FIXTURES, "csv-to-slack.blueprint.md"),
                "--out-dir",
                tmp,
                "--force",
            ], stdout=io.StringIO())
            self.assertEqual(rc, 0)
            with open(os.path.join(path, "csv-to-slack.md"), encoding="utf-8") as f:
                self.assertIn("# csv-to-slack", f.read())


if __name__ == "__main__":
    unittest.main()
