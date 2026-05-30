import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_blueprint import (
    ReviewInputError,
    parse_review_payload,
    render_report,
    report_path_for,
    write_report,
)
from tests.fake_client import valid_payload


class TestReportRendering(unittest.TestCase):
    def test_report_path_replaces_blueprint_suffix(self):
        path = report_path_for(Path("workflows/example.blueprint.md"))
        self.assertEqual(path, Path("workflows/example.review.md"))

    def test_render_report_contains_all_dimensions_and_metadata(self):
        result = parse_review_payload(valid_payload())
        text = render_report(
            blueprint_name="valid_full.blueprint.md",
            result=result,
            reviewed_date="2026-05-30",
            model="model-x",
            threshold=3,
        )
        self.assertIn("# Review: valid_full.blueprint.md", text)
        self.assertIn("Reviewed: 2026-05-30", text)
        self.assertIn("judge: model-x", text)
        self.assertIn("verdict: NEEDS-REVISION", text)
        self.assertIn("| Determinism classification soundness | 2 | flag |", text)
        self.assertIn("## Findings", text)
        self.assertIn("Improve determinism_classification.", text)
        self.assertIn("## Summary", text)

    def test_write_report_creates_file(self):
        result = parse_review_payload(valid_payload())
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "example.review.md"
            write_report(report, "example.blueprint.md", result, "2026-05-30", "model-x", 3)
            self.assertTrue(report.exists())
            self.assertIn("example.blueprint.md", report.read_text(encoding="utf-8"))

    def test_write_report_wraps_write_failure(self):
        result = parse_review_payload(valid_payload())
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ReviewInputError, "failed to write report"):
                write_report(Path("example.review.md"), "example.blueprint.md", result, "2026-05-30", "model-x", 3)


if __name__ == "__main__":
    unittest.main()
