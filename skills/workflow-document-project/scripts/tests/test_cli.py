import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fake_client import valid_synthesis_payload


SCRIPT = Path(__file__).parents[1] / "document_project.py"
FIXTURE = Path(__file__).parent / "fixtures" / "inventory_project"


class TestCli(unittest.TestCase):
    def test_inventory_cli_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "inventory.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "inventory",
                    "--root",
                    str(FIXTURE),
                    "--name",
                    "fixture-review",
                    "--date",
                    "2026-05-31",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["strong_workflow_signal"])
            self.assertIn("Inventory:", proc.stdout)

    def test_write_cli_writes_artifacts_without_partial_on_bad_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inventory = root / "inventory.json"
            synthesis = root / "synthesis.json"
            inventory.write_text(
                json.dumps(
                    {
                        "root": str(root),
                        "workflow_name": "fixture-review",
                        "artifacts": [],
                        "observed_facts": [],
                        "signals": ["has tests"],
                        "existing_blueprints": [],
                        "inference_requests": [],
                        "open_questions": [],
                        "strong_workflow_signal": True,
                    }
                ),
                encoding="utf-8",
            )
            synthesis.write_text(json.dumps(valid_synthesis_payload()), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "write",
                    "--root",
                    str(root),
                    "--name",
                    "fixture-review",
                    "--date",
                    "2026-05-31",
                    "--inventory",
                    str(inventory),
                    "--synthesis",
                    str(synthesis),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((root / "workflows" / "fixture-review.blueprint.md").exists())
            self.assertTrue((root / "workflows" / "fixture-review.project-doc.md").exists())

            bad = root / "bad.json"
            bad.write_text("{\"blueprint_yaml\": {\"status\": \"validated\"}}", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "write",
                    "--root",
                    str(root),
                    "--name",
                    "bad-review",
                    "--date",
                    "2026-05-31",
                    "--inventory",
                    str(inventory),
                    "--synthesis",
                    str(bad),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertFalse((root / "workflows" / "bad-review.blueprint.md").exists())

    def test_cli_rejects_unreadable_root(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "inventory",
                "--root",
                "/path/that/does/not/exist",
                "--name",
                "missing",
                "--date",
                "2026-05-31",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ERROR:", proc.stderr)

    def test_write_cli_accepts_fenced_synthesis_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inventory = root / "inventory.json"
            synthesis = root / "synthesis.json"
            inventory.write_text(
                json.dumps(
                    {
                        "root": str(root),
                        "workflow_name": "fenced-review",
                        "artifacts": [],
                        "observed_facts": [],
                        "signals": ["has tests"],
                        "existing_blueprints": [],
                        "inference_requests": [],
                        "open_questions": [],
                        "strong_workflow_signal": True,
                    }
                ),
                encoding="utf-8",
            )
            # the session model is told to emit a fenced ```json block; the writer must strip it
            synthesis.write_text(
                "```json\n" + json.dumps(valid_synthesis_payload()) + "\n```\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "write",
                    "--root", str(root), "--name", "fenced-review", "--date", "2026-05-31",
                    "--inventory", str(inventory), "--synthesis", str(synthesis),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((root / "workflows" / "fenced-review.blueprint.md").exists())


if __name__ == "__main__":
    unittest.main()
