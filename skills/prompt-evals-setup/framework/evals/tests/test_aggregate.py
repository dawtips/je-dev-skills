"""Offline tests for evals/aggregate.py - the no-model report assembler. No API key."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from evals import aggregate

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
VERDICTS_OK = os.path.join(FIXTURES, "verdicts_ok")
VERDICTS_BAD = os.path.join(FIXTURES, "verdicts_bad")


class TestLoadVerdicts(unittest.TestCase):
    def test_load_sorts_by_filename_and_builds_results(self):
        results = aggregate.load_results(VERDICTS_OK)
        # 3 fixtures, in filename order case-00, case-01, case-02.
        self.assertEqual(len(results), 3)
        self.assertEqual([r["score"] for r in results], [8, 3, 9])
        first = results[0]
        self.assertEqual(set(first.keys()) >= {"output", "test_case", "score", "reasoning", "verdict"}, True)
        self.assertEqual(first["reasoning"], first["verdict"]["reasoning"])

    def test_bad_verdict_raises(self):
        with self.assertRaises(ValueError):
            aggregate.load_results(VERDICTS_BAD)


class TestAggregateWritesReport(unittest.TestCase):
    def test_writes_output_json_and_html_to_run_dir(self):
        with tempfile.TemporaryDirectory() as d:
            runs_dir = Path(d) / "runs"
            run_dir = aggregate.aggregate(
                run_label="improve-meal-round-00",
                verdicts_dir=VERDICTS_OK,
                dataset=None,
                runs_dir=str(runs_dir),
            )
            self.assertEqual(Path(run_dir), runs_dir / "improve-meal-round-00")
            out_json = Path(run_dir) / "output.json"
            out_html = Path(run_dir) / "output.html"
            self.assertTrue(out_json.exists())
            self.assertTrue(out_html.exists())
            data = json.loads(out_json.read_text())
            self.assertEqual(set(data.keys()), {"meta", "summary", "results"})
            # summarize(): scores [8,3,9], PASS_THRESHOLD 7 -> 2 pass of 3.
            self.assertEqual(data["summary"]["total"], 3)
            self.assertEqual(data["summary"]["passed"], 2)
            self.assertEqual(data["meta"]["run_label"], "improve-meal-round-00")
            # HTML is escaped + self-contained.
            html = out_html.read_text()
            self.assertIn("Average score", html)

    def test_dataset_meta_overrides_when_provided(self):
        with tempfile.TemporaryDirectory() as d:
            dataset_path = Path(d) / "ds.json"
            dataset_path.write_text(json.dumps({
                "provenance": {"task_description": "DS TASK", "prompt_inputs_spec": {}},
                "cases": [],
            }))
            run_dir = aggregate.aggregate(
                run_label="r1",
                verdicts_dir=VERDICTS_OK,
                dataset=str(dataset_path),
                runs_dir=str(Path(d) / "runs"),
            )
            data = json.loads((Path(run_dir) / "output.json").read_text())
            self.assertEqual(data["meta"]["task_description"], "DS TASK")
            self.assertEqual(data["meta"]["dataset_file"], str(dataset_path))


class TestCli(unittest.TestCase):
    def test_main_returns_zero_and_prints_run_dir(self):
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = aggregate.main([
                    "--run-label", "cli-run",
                    "--verdicts-dir", VERDICTS_OK,
                    "--runs-dir", str(Path(d) / "runs"),
                ])
            self.assertEqual(rc, 0)
            self.assertIn("cli-run", buf.getvalue())
            self.assertTrue((Path(d) / "runs" / "cli-run" / "output.json").exists())

    def test_main_returns_two_on_empty_verdicts_dir(self):
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty"
            empty.mkdir()
            rc = aggregate.main([
                "--run-label", "x",
                "--verdicts-dir", str(empty),
                "--runs-dir", str(Path(d) / "runs"),
            ])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
