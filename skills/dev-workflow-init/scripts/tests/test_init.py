import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from init_project import InitError, init_project, main, slugify

PINNED_DATE = "2026-05-30"


def _run(root, **kw):
    os.environ["DEV_WORKFLOW_INIT_DATE"] = PINNED_DATE
    return init_project("My App", root, **kw)


class TestSlugify(unittest.TestCase):
    def test_collapses_and_trims(self):
        self.assertEqual(slugify("  Order Refund!! "), "order-refund")
        self.assertEqual(slugify("A__B  C"), "a-b-c")


class TestScaffold(unittest.TestCase):
    def test_writes_full_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            written, warnings = _run(tmp)
            self.assertEqual(warnings, [])
            for expected in (
                ".story/config.json",
                ".story/roadmap.json",
                ".story/.gitignore",
                ".story/tickets/T-001.json",
                ".story/handovers/.gitkeep",
                ".story/lessons/.gitkeep",
                "docs/superpowers/specs/.gitkeep",
                "docs/superpowers/plans/.gitkeep",
                "AGENTS.md",
                "CLAUDE.md",
                ".gitignore",
            ):
                self.assertIn(expected, written, expected)
                self.assertTrue((Path(tmp) / expected).exists(), expected)

    def test_config_and_roadmap_are_valid_json_with_project_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(tmp)
            config = json.loads((Path(tmp) / ".story/config.json").read_text())
            roadmap = json.loads((Path(tmp) / ".story/roadmap.json").read_text())
            ticket = json.loads((Path(tmp) / ".story/tickets/T-001.json").read_text())
            self.assertEqual(config["project"], "My App")
            self.assertEqual(roadmap["title"], "My App")
            self.assertEqual(roadmap["date"], PINNED_DATE)
            self.assertEqual(ticket["status"], "open")
            self.assertEqual(ticket["phase"], roadmap["phases"][0]["id"])

    def test_claude_md_imports_agents_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(tmp)
            self.assertIn("@AGENTS.md", (Path(tmp) / "CLAUDE.md").read_text())

    def test_agents_md_names_the_delete_plan_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(tmp)
            agents = (Path(tmp) / "AGENTS.md").read_text()
            self.assertIn("Deleting plans once implemented", agents)
            self.assertIn("delete before merge", agents)

    def test_agents_md_names_automatic_local_merge_cleanup_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(tmp)
            agents = (Path(tmp) / "AGENTS.md").read_text()
            self.assertIn("Integrate and clean up automatically", agents)
            self.assertIn("Always merge completed work back to the default branch locally", agents)
            self.assertIn("remove the worktree", agents)
            self.assertIn("delete the local branch", agents)
            self.assertNotIn("Open a PR", agents)
            self.assertNotIn("Keep branch and worktree", agents)

    def test_empty_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InitError):
                init_project("   ", tmp)


class TestGitignore(unittest.TestCase):
    def test_appends_block_preserving_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            _run(tmp)
            text = (Path(tmp) / ".gitignore").read_text()
            self.assertIn("node_modules/", text)
            self.assertIn(".story/snapshots/", text)

    def test_idempotent_when_block_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(tmp)
            first = (Path(tmp) / ".gitignore").read_text()
            written2, _ = _run(tmp, force=True)
            second = (Path(tmp) / ".gitignore").read_text()
            self.assertEqual(first, second)  # no duplicate block
            self.assertNotIn(".gitignore", written2)  # reported as no-op the 2nd time


class TestCollisionAndForce(unittest.TestCase):
    def test_refuses_to_clobber_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "AGENTS.md").write_text("keep me", encoding="utf-8")
            with self.assertRaises(InitError):
                _run(tmp)
            # untouched
            self.assertEqual((Path(tmp) / "AGENTS.md").read_text(), "keep me")

    def test_force_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "AGENTS.md").write_text("old", encoding="utf-8")
            _run(tmp, force=True)
            self.assertIn("Working agreement", (Path(tmp) / "AGENTS.md").read_text())

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            written, _ = _run(tmp, dry_run=True)
            self.assertTrue(written)
            self.assertFalse((Path(tmp) / "AGENTS.md").exists())
            self.assertFalse((Path(tmp) / ".story").exists())


class TestCli(unittest.TestCase):
    def test_main_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DEV_WORKFLOW_INIT_DATE"] = PINNED_DATE
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main(["--name", "Widgets", "--root", tmp])
            self.assertEqual(rc, 0)
            self.assertIn("files wrote", out.getvalue())
            self.assertTrue((Path(tmp) / ".story/config.json").exists())

    def test_main_collision_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CLAUDE.md").write_text("x", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                rc = main(["--name", "Widgets", "--root", tmp])
            self.assertEqual(rc, 1)
            self.assertIn("refusing to overwrite", err.getvalue())

    def test_main_dry_run_reports_would_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main(["--name", "Widgets", "--root", tmp, "--dry-run"])
            self.assertEqual(rc, 0)
            self.assertIn("would write", out.getvalue())
            self.assertFalse((Path(tmp) / "CLAUDE.md").exists())


if __name__ == "__main__":
    unittest.main()
