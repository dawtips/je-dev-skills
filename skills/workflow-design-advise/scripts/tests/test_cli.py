import io
import os
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


if __name__ == "__main__":
    unittest.main()
