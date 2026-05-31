import unittest

from document_project import parse_synthesis_payload, render_project_doc
from tests.fake_client import valid_synthesis_payload


class TestProjectDocReport(unittest.TestCase):
    def test_report_contains_required_sections_and_feedback_severity(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        inventory = {
            "workflow_name": "fixture-review",
            "artifacts": [
                {"path": "README.md", "category": "guidance", "title": "Inventory Fixture"},
                {"path": "tests/test_run.py", "category": "test", "title": ""},
            ],
            "signals": ["has tests"],
            "existing_blueprints": [],
            "open_questions": ["Confirm fixture boundaries."],
            "strong_workflow_signal": True,
        }
        report = render_project_doc("fixture-review", inventory, payload, "2026-05-31", validation_status="not run")

        for heading in (
            "## Summary",
            "## Inventory",
            "## Evidence Map",
            "## Inferences",
            "## Open Questions",
            "## Feedback",
            "## Generated Artifacts",
        ):
            self.assertIn(heading, report)
        self.assertIn("important", report)
        self.assertIn("README.md", report)
        self.assertIn("steps.inventory", report)
        self.assertIn("validation: not run", report)


if __name__ == "__main__":
    unittest.main()
