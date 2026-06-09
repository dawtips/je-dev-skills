import os
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from document_project import (
    DocumentProjectError,
    extract_yaml_block,
    parse_synthesis_payload,
    render_blueprint,
    write_artifacts,
)
from tests.fake_client import valid_synthesis_payload


def _minimal_inventory(**overrides):
    base = {
        "root": "",
        "workflow_name": "fixture-review",
        "artifacts": [],
        "observed_facts": [],
        "signals": ["has tests"],
        "existing_blueprints": [],
        "inference_requests": [],
        "open_questions": [],
        "strong_workflow_signal": True,
    }
    base.update(overrides)
    return base


import importlib.util


def _load_validator_module():
    # test_blueprint.py lives at skills/workflow-document-project/scripts/tests/,
    # so the repo root (containing skills/) is parents[4], not parents[5].
    root = Path(__file__).resolve().parents[4]
    path = root / "skills" / "workflow-design-validate" / "scripts" / "validate_blueprint.py"
    spec = importlib.util.spec_from_file_location("wdp_validate_blueprint", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_VALIDATOR = _load_validator_module()


def validate_blueprint_text(text):
    parsed = yaml.safe_load(_VALIDATOR.extract_yaml_block(text))
    return _VALIDATOR.validate(parsed)


class TestBlueprintRendering(unittest.TestCase):
    def test_render_blueprint_has_one_yaml_block_and_stays_draft(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        text = render_blueprint(payload)
        yaml_text = extract_yaml_block(text)
        parsed = yaml.safe_load(yaml_text)

        self.assertEqual(text.count("```yaml"), 1)
        self.assertEqual(parsed["status"], "draft")
        self.assertIn("# Fixture Review Workflow", text)
        self.assertIn("## Purpose", text)
        self.assertIn("## Rationale", text)

    def test_write_artifacts_writes_sibling_blueprint_and_project_doc(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        inventory = {
            "root": "",
            "workflow_name": "fixture-review",
            "artifacts": [],
            "observed_facts": [],
            "signals": ["has tests"],
            "existing_blueprints": [],
            "inference_requests": [],
            "open_questions": [],
            "strong_workflow_signal": True,
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = write_artifacts(root, "fixture-review", inventory, payload, "2026-05-31")

            self.assertEqual(paths["blueprint"], root / "workflows" / "fixture-review.blueprint.md")
            self.assertEqual(paths["project_doc"], root / "workflows" / "fixture-review.project-doc.md")
            self.assertTrue(paths["blueprint"].exists())
            self.assertTrue(paths["project_doc"].exists())
            self.assertIn("status: draft", paths["blueprint"].read_text(encoding="utf-8"))

    def test_write_records_real_validation_status(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        with tempfile.TemporaryDirectory() as d:
            paths = write_artifacts(Path(d), "fixture-review", _minimal_inventory(), payload, "2026-05-31")
            doc = paths["project_doc"].read_text(encoding="utf-8")
            # write_artifacts runs workflow-design-validate in-process: the report is no
            # longer a permanent "not run", it carries the actual validator outcome.
            self.assertIn("validation: pass (12/12 dimensions)", doc)

    def test_write_refuses_to_clobber_validated_blueprint_without_force(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = write_artifacts(root, "fixture-review", _minimal_inventory(), payload, "2026-05-31")
            bp = paths["blueprint"]
            bp.write_text(bp.read_text(encoding="utf-8").replace("status: draft", "status: validated", 1), encoding="utf-8")
            with self.assertRaises(DocumentProjectError):
                write_artifacts(root, "fixture-review", _minimal_inventory(), payload, "2026-05-31")
            forced = write_artifacts(root, "fixture-review", _minimal_inventory(), payload, "2026-05-31", force=True)
            self.assertTrue(forced["blueprint"].exists())

    def test_write_records_superseded_existing_blueprint(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        inventory = _minimal_inventory(existing_blueprints=["workflows/fixture-review.blueprint.md"])
        with tempfile.TemporaryDirectory() as d:
            paths = write_artifacts(Path(d), "fixture-review", inventory, payload, "2026-05-31")
            self.assertIn("### Superseded", paths["project_doc"].read_text(encoding="utf-8"))

    def test_fixed_synthesis_fixture_passes_workflow_design_validate_and_stays_draft(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        text = render_blueprint(payload)
        # call the module-level adapter directly; it is NOT an importable module
        gaps, coverage = validate_blueprint_text(text)
        parsed = yaml.safe_load(extract_yaml_block(text))

        self.assertEqual(coverage, (12, 12))
        self.assertEqual(gaps, [])
        self.assertEqual(parsed["status"], "draft")


class TestBlueprintSafety(unittest.TestCase):
    def test_frontmatter_with_special_chars_stays_valid_yaml(self):
        # A model-supplied frontmatter value with a newline and YAML-special chars
        # must not break the --- block (WR-009).
        raw = valid_synthesis_payload()
        raw["blueprint_frontmatter"]["created"] = "line1\nline2: trap # not a comment"
        payload = parse_synthesis_payload(raw)
        text = render_blueprint(payload)

        block = re.search(r"(?s)\A---\n(.*?)\n---", text).group(1)
        parsed_fm = yaml.safe_load(block)
        self.assertEqual(parsed_fm["status"], "draft")
        self.assertEqual(parsed_fm["name"], "fixture-review")
        self.assertEqual(parsed_fm["created"], "line1\nline2: trap # not a comment")
        # The status line stays regex-readable for _existing_blueprint_status.
        self.assertRegex(block, r"(?m)^status:\s*draft\s*$")

    def test_write_failure_raises_document_error_and_leaves_no_partial(self):
        from unittest import mock

        payload = parse_synthesis_payload(valid_synthesis_payload())
        real_replace = os.replace
        calls = {"n": 0}

        def flaky_replace(src, dst):
            calls["n"] += 1
            if calls["n"] == 1:  # fail on the first rename (the blueprint)
                raise OSError("simulated disk full")
            return real_replace(src, dst)

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with mock.patch("document_project.os.replace", side_effect=flaky_replace):
                with self.assertRaises(DocumentProjectError):
                    write_artifacts(root, "fixture-review", _minimal_inventory(), payload, "2026-05-31")

            wf = root / "workflows"
            self.assertFalse((wf / "fixture-review.blueprint.md").exists())
            self.assertFalse((wf / "fixture-review.project-doc.md").exists())
            self.assertEqual(sorted(wf.glob("*.tmp")), [])  # no leftover temp files
            self.assertEqual(sorted(wf.glob("*.bak")), [])

    def test_second_rename_failure_rolls_back_to_original_blueprint(self):
        from unittest import mock

        payload = parse_synthesis_payload(valid_synthesis_payload())
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            wf = root / "workflows"
            wf.mkdir(parents=True)
            bp = wf / "fixture-review.blueprint.md"
            pd = wf / "fixture-review.project-doc.md"
            bp.write_text("ORIGINAL BLUEPRINT\nstatus: draft\n", encoding="utf-8")
            pd.write_text("ORIGINAL PROJECT DOC\n", encoding="utf-8")

            real_replace = os.replace
            calls = {"n": 0}

            def flaky(src, dst):
                # sequence: 1) bp->bak  2) bp_tmp->bp  3) pd_tmp->pd (fail)  4) bak->bp (rollback)
                calls["n"] += 1
                if calls["n"] == 3:
                    raise OSError("project-doc not replaceable")
                return real_replace(src, dst)

            with mock.patch("document_project.os.replace", side_effect=flaky):
                with self.assertRaises(DocumentProjectError):
                    write_artifacts(root, "fixture-review", _minimal_inventory(), payload, "2026-05-31")

            # The original pair is intact — no new blueprint published without its doc.
            self.assertEqual(bp.read_text(encoding="utf-8"), "ORIGINAL BLUEPRINT\nstatus: draft\n")
            self.assertEqual(pd.read_text(encoding="utf-8"), "ORIGINAL PROJECT DOC\n")
            self.assertEqual(sorted(wf.glob("*.tmp")), [])
            self.assertEqual(sorted(wf.glob("*.bak")), [])

    def test_successful_write_leaves_no_temp_or_backup_files(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # Pre-existing draft blueprint so the backup path is exercised.
            wf = root / "workflows"
            wf.mkdir(parents=True)
            (wf / "fixture-review.blueprint.md").write_text("status: draft\n", encoding="utf-8")
            write_artifacts(root, "fixture-review", _minimal_inventory(), payload, "2026-05-31")
            self.assertEqual(sorted(wf.glob("*.tmp")), [])
            self.assertEqual(sorted(wf.glob("*.bak")), [])

    def test_validation_degrade_warns_on_stderr(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest import mock

        import document_project as dp

        def boom_validate(_parsed):
            raise RuntimeError("validator API drift")

        fake = SimpleNamespace(
            extract_yaml_block=lambda _text: "status: draft",
            validate=boom_validate,
        )
        err = io.StringIO()
        with mock.patch.object(dp, "_validator_module", return_value=fake), \
                contextlib.redirect_stderr(err):
            status = dp.blueprint_validation_status("anything")

        self.assertEqual(status, "not run")
        self.assertIn("validation could not run", err.getvalue())


if __name__ == "__main__":
    unittest.main()
