import tempfile
import unittest
from pathlib import Path

from evals.evaluator.report import summarize, write_html, write_json


def results(scores):
    return [
        {
            "output": "out",
            "test_case": {"scenario": "s", "prompt_inputs": {}, "solution_criteria": ["c"]},
            "score": s,
            "reasoning": "r",
        }
        for s in scores
    ]


class TestSummarize(unittest.TestCase):
    def test_empty(self):
        s = summarize([])
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["pass_rate"], 0.0)

    def test_average_and_pass_rate(self):
        s = summarize(results([10, 8, 6, 4]))  # pass threshold 7 -> 2/4
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["average_score"], 7.0)
        self.assertEqual(s["passed"], 2)
        self.assertEqual(s["pass_rate"], 50.0)


class TestHtmlEscaping(unittest.TestCase):
    def test_output_is_escaped(self):
        payload = results([8])
        payload[0]["output"] = "<script>alert(1)</script>"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.html"
            write_html(path, payload, summarize(payload), {"task_description": "t"})
            html = path.read_text()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestWriteJson(unittest.TestCase):
    def test_roundtrip_shape(self):
        import json

        payload = results([9])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.json"
            write_json(path, payload, summarize(payload), {"run_label": "x"})
            data = json.loads(path.read_text())
        self.assertEqual(set(data.keys()), {"meta", "summary", "results"})
        self.assertEqual(data["summary"]["total"], 1)


class TestReportAnalysisRendering(unittest.TestCase):
    def test_write_json_includes_analysis_when_supplied(self):
        import json

        payload = results([9])
        analysis = {
            "baseline_delta": {"available": False, "note": "Baseline delta: not available -- pass --baseline-output with a prior run output.json."},
            "variance": {"available": False, "note": "Variance: not available -- needs >=2 runs of the same frozen dataset."},
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.json"
            write_json(path, payload, summarize(payload), {"run_label": "x"}, analysis=analysis)
            data = json.loads(path.read_text())

        self.assertEqual(set(data.keys()), {"meta", "summary", "results", "analysis"})
        self.assertEqual(data["analysis"], analysis)

    def test_write_html_renders_analysis_section_escaped(self):
        payload = results([8])
        analysis = {
            "baseline_delta": {"available": False, "note": "Baseline delta: not available -- <script>bad()</script>"},
            "variance": {"available": False, "note": "Variance: not available -- needs >=2 runs of the same frozen dataset."},
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.html"
            write_html(path, payload, summarize(payload), {"task_description": "t"}, analysis=analysis)
            html = path.read_text()

        self.assertIn("Report Analyst", html)
        self.assertIn("&lt;script&gt;bad()&lt;/script&gt;", html)
        self.assertNotIn("<script>bad()</script>", html)


if __name__ == "__main__":
    unittest.main()
