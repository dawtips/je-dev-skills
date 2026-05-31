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
