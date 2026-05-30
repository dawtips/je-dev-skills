"""Offline tests for evals/aggregate.py - the no-model report assembler. No API key."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from evals import aggregate, run_eval

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
VERDICTS_OK = os.path.join(FIXTURES, "verdicts_ok")
VERDICTS_BAD = os.path.join(FIXTURES, "verdicts_bad")


def _fixture_records() -> list[dict]:
    records = []
    for name in sorted(os.listdir(VERDICTS_OK)):
        with open(os.path.join(VERDICTS_OK, name), encoding="utf-8") as f:
            records.append(json.load(f))
    return records


def _write_dataset(path: Path, cases: list[dict], task: str = "DS TASK") -> None:
    path.write_text(json.dumps({
        "provenance": {"task_description": task, "prompt_inputs_spec": {}},
        "cases": cases,
    }), encoding="utf-8")


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
            self.assertEqual(set(data.keys()), {"meta", "summary", "results", "analysis"})
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
            _write_dataset(dataset_path, [r["test_case"] for r in _fixture_records()])
            run_dir = aggregate.aggregate(
                run_label="r1",
                verdicts_dir=VERDICTS_OK,
                dataset=str(dataset_path),
                runs_dir=str(Path(d) / "runs"),
            )
            data = json.loads((Path(run_dir) / "output.json").read_text())
            self.assertEqual(data["meta"]["task_description"], "DS TASK")
            self.assertEqual(data["meta"]["dataset_file"], str(dataset_path))
            self.assertEqual(data["meta"]["extra_criteria"], run_eval.EXTRA_CRITERIA)

    def test_dataset_case_count_must_match_verdicts(self):
        with tempfile.TemporaryDirectory() as d:
            dataset_path = Path(d) / "ds.json"
            _write_dataset(dataset_path, [r["test_case"] for r in _fixture_records()[:2]])
            with self.assertRaises(ValueError) as ctx:
                aggregate.aggregate(
                    run_label="bad-count",
                    verdicts_dir=VERDICTS_OK,
                    dataset=str(dataset_path),
                    runs_dir=str(Path(d) / "runs"),
                )
            self.assertIn("case count", str(ctx.exception))

    def test_dataset_cases_must_match_verdict_test_cases(self):
        with tempfile.TemporaryDirectory() as d:
            dataset_path = Path(d) / "ds.json"
            records = _fixture_records()
            wrong_cases = [r["test_case"] for r in records]
            wrong_cases[1] = dict(wrong_cases[1], scenario="wrong dataset")
            _write_dataset(dataset_path, wrong_cases)
            with self.assertRaises(ValueError) as ctx:
                aggregate.aggregate(
                    run_label="wrong-dataset",
                    verdicts_dir=VERDICTS_OK,
                    dataset=str(dataset_path),
                    runs_dir=str(Path(d) / "runs"),
                )
            self.assertIn("does not match", str(ctx.exception))


class TestAggregateReportAnalysis(unittest.TestCase):
    def test_aggregate_writes_absent_input_analysis_notes(self):
        with tempfile.TemporaryDirectory() as d:
            verdicts = Path(d) / "verdicts"
            verdicts.mkdir()
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            case = {
                "task_description": "task",
                "scenario": "case",
                "prompt_inputs": {},
                "solution_criteria": ["criterion"],
            }
            dataset.write_text(json.dumps({
                "provenance": {"task_description": "task"},
                "cases": [case],
            }))
            (verdicts / "case-00.json").write_text(json.dumps({
                "test_case": case,
                "output": "answer",
                "verdict": {
                    "strengths": [],
                    "weaknesses": [],
                    "reasoning": "ok",
                    "score": 8,
                },
            }))

            out_dir = aggregate.aggregate(
                run_label="current",
                verdicts_dir=verdicts,
                dataset=dataset,
                runs_dir=str(runs_dir),
                extra_criteria=None,
                include_analysis=True,
            )
            payload = json.loads((Path(out_dir) / "output.json").read_text())

        self.assertIn("analysis", payload)
        self.assertFalse(payload["analysis"]["baseline_delta"]["available"])
        self.assertFalse(payload["analysis"]["variance"]["available"])

    def test_aggregate_accepts_baseline_and_variance_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "base.json"
            k1 = Path(d) / "k1.json"
            k2 = Path(d) / "k2.json"
            current = {
                "summary": {"average_score": 8.0, "pass_rate": 100.0, "passed": 1},
                "results": [{"test_case": {"scenario": "case"}, "score": 8}],
            }
            baseline = {
                "summary": {"average_score": 6.0, "pass_rate": 0.0, "passed": 0},
                "results": [{"test_case": {"scenario": "case"}, "score": 6}],
            }
            for path, payload in ((base, baseline), (k1, baseline), (k2, current)):
                path.write_text(json.dumps(payload))

            analysis = aggregate.build_report_analysis_for_output(
                current,
                baseline_output=base,
                variance_outputs=[k1, k2],
            )

        self.assertTrue(analysis["baseline_delta"]["available"])
        self.assertTrue(analysis["variance"]["available"])


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
