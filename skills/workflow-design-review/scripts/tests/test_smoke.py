import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_blueprint import API_KEY_ENV, ReviewInputError, main, make_anthropic_client, run_review
from tests.fake_client import FakeClient, RaisingClient, valid_payload

FIXTURES = Path(__file__).parent / "fixtures"


class TestSmoke(unittest.TestCase):
    def test_run_review_writes_report_with_fake_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            blueprint = Path(tmp) / "example.blueprint.md"
            blueprint.write_text((FIXTURES / "valid_full.blueprint.md").read_text(encoding="utf-8"), encoding="utf-8")
            rc, report_path, result = run_review(
                blueprint_path=blueprint,
                reviewed_date="2026-05-30",
                client_factory=lambda: FakeClient(valid_payload()),
                strict=False,
                model="model-x",
                threshold=3,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(report_path, Path(tmp) / "example.review.md")
            self.assertTrue(report_path.exists())
            self.assertEqual(result.dimensions[0].name, "determinism_classification")

    def test_main_returns_two_for_missing_blueprint(self):
        rc = main(["does-not-exist.blueprint.md", "--date", "2026-05-30"])
        self.assertEqual(rc, 2)

    def test_main_requires_date_to_keep_reports_reproducible(self):
        rc = main([str(FIXTURES / "valid_full.blueprint.md")])
        self.assertEqual(rc, 2)

    def test_main_rejects_threshold_out_of_range(self):
        self.assertEqual(main([str(FIXTURES / "valid_full.blueprint.md"), "--date", "2026-05-30", "--threshold", "0"]), 2)
        self.assertEqual(main([str(FIXTURES / "valid_full.blueprint.md"), "--date", "2026-05-30", "--threshold", "6"]), 2)

    def test_cli_reports_malformed_numeric_env_without_traceback(self):
        script = Path(__file__).parents[1] / "review_blueprint.py"
        for env_name in (
            "WORKFLOW_REVIEW_PASS_THRESHOLD",
            "WORKFLOW_REVIEW_MAX_TOKENS",
            "WORKFLOW_REVIEW_MAX_INPUT_CHARS",
        ):
            with self.subTest(env_name=env_name):
                env = os.environ.copy()
                env[env_name] = "not-an-int"
                env.pop(API_KEY_ENV, None)
                proc = subprocess.run(
                    [sys.executable, str(script), "--date", "2026-05-30", "--", str(FIXTURES / "valid_full.blueprint.md")],
                    cwd=script.parent,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 2)
                self.assertIn(f"{env_name} must be an integer", proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)

    def test_main_reports_malformed_blueprint_before_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            rc = main([str(FIXTURES / "broken_invalid_yaml.blueprint.md"), "--date", "2026-05-30"])
        self.assertEqual(rc, 2)

    def test_main_uses_fake_client_factory_and_strict_returns_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            blueprint = Path(tmp) / "example.blueprint.md"
            blueprint.write_text((FIXTURES / "valid_full.blueprint.md").read_text(encoding="utf-8"), encoding="utf-8")
            with patch("review_blueprint.make_anthropic_client", return_value=FakeClient(valid_payload())):
                rc = main([str(blueprint), "--date", "2026-05-30", "--strict"])
            self.assertEqual(rc, 1)
            self.assertTrue((Path(tmp) / "example.review.md").exists())

    def test_main_returns_two_when_judge_call_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            blueprint = Path(tmp) / "example.blueprint.md"
            blueprint.write_text((FIXTURES / "valid_full.blueprint.md").read_text(encoding="utf-8"), encoding="utf-8")
            with patch("review_blueprint.make_anthropic_client", return_value=RaisingClient()):
                rc = main([str(blueprint), "--date", "2026-05-30"])
        self.assertEqual(rc, 2)

    def test_make_anthropic_client_reports_missing_package(self):
        with patch.dict(os.environ, {API_KEY_ENV: "test"}), patch.dict(sys.modules, {"anthropic": None}):
            with self.assertRaisesRegex(ReviewInputError, "anthropic package is not installed"):
                make_anthropic_client()

    def test_main_returns_two_when_report_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            blueprint = Path(tmp) / "example.blueprint.md"
            blueprint.write_text((FIXTURES / "valid_full.blueprint.md").read_text(encoding="utf-8"), encoding="utf-8")
            with patch("review_blueprint.make_anthropic_client", return_value=FakeClient(valid_payload())):
                with patch.object(Path, "write_text", side_effect=OSError("disk full")):
                    rc = main([str(blueprint), "--date", "2026-05-30"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
