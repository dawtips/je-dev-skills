import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from advise_model import main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE = os.path.join(FIXTURES, "valid_sample.blueprint.md")


class TestCli(unittest.TestCase):
    def test_report_run_exits_zero_and_prints_table(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main([SAMPLE, "--date", "2026-05-30"])
        self.assertEqual(rc, 0)
        self.assertIn("# Model advice:", out.getvalue())

    def test_missing_date_without_json_is_usage_error(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main([SAMPLE])
        self.assertEqual(rc, 2)
        self.assertIn("--date is required", err.getvalue())

    def test_json_run_needs_no_date(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main([SAMPLE, "--json"])
        self.assertEqual(rc, 0)
        self.assertIn('"recommended_model"', out.getvalue())

    def test_strict_exits_one_on_disagreement(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main([SAMPLE, "--json", "--strict"])
        self.assertEqual(rc, 1)  # item-researcher is over-provisioned

    def test_unknown_path_is_input_error(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main([os.path.join(FIXTURES, "nope.blueprint.md"), "--json"])
        self.assertEqual(rc, 2)
        self.assertIn("ERROR:", err.getvalue())

    def test_strict_exits_zero_on_clean_blueprint(self):
        content = (
            "---\nname: clean\n---\n# c\n\n```yaml\n"
            "subagents:\n  - id: w\n    tools: [a, b]\n"
            "    model: sonnet\n    effort: medium\n```\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "clean.blueprint.md")
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main([p, "--json", "--strict"])
        self.assertEqual(rc, 0)

    def test_budget_high_caps_effort(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main([SAMPLE, "--json", "--budget", "high"])
        self.assertEqual(rc, 0)
        recs = {r["target_id"]: r for r in json.loads(out.getvalue())}
        self.assertEqual(recs["plan"]["recommended_effort"], "medium")


if __name__ == "__main__":
    unittest.main()
