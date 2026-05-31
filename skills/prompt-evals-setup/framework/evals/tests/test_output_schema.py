import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from evals.output_schema import (
    MAX_OUTPUT_SCHEMA_BYTES,
    MAX_OUTPUT_SCHEMA_DEPTH,
    MAX_OUTPUT_SCHEMA_OPTIONAL_PROPERTIES,
    parse_strict_json,
    validate_output_against_schema,
    validate_output_schema,
)


VALID_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "count": {"type": "integer"},
        "score": {"type": "number"},
        "ok": {"type": "boolean"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "meta": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["a", "b"]}},
            "required": ["kind"],
            "additionalProperties": False,
        },
    },
    "required": ["title", "count", "score", "ok", "tags", "meta"],
    "additionalProperties": False,
}


class TestValidateOutputSchema(unittest.TestCase):
    def test_accepts_bounded_root_object_schema(self):
        self.assertEqual(validate_output_schema(VALID_SCHEMA), VALID_SCHEMA)

    def test_rejects_non_object_schema(self):
        with self.assertRaisesRegex(ValueError, "target\\.output_schema.*JSON object"):
            validate_output_schema([])

    def test_rejects_non_root_object_schema(self):
        with self.assertRaisesRegex(ValueError, "target\\.output_schema.*JSON object"):
            validate_output_schema({"type": "array", "items": {"type": "string"}})

    def test_rejects_non_object_properties(self):
        with self.assertRaisesRegex(ValueError, "target\\.output_schema\\.properties.*object"):
            validate_output_schema({"type": "object", "properties": []})

    def test_rejects_non_string_required_entries(self):
        with self.assertRaisesRegex(ValueError, "target\\.output_schema\\.required.*strings"):
            validate_output_schema({"type": "object", "required": ["ok", 2]})

    def test_rejects_unclosed_object_schema(self):
        with self.assertRaisesRegex(ValueError, "additionalProperties.*false"):
            validate_output_schema({"type": "object", "properties": {}, "required": []})

    def test_rejects_unconstrained_child_schema(self):
        with self.assertRaisesRegex(ValueError, "properties\\.payload\\.type.*required"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": {"payload": {}},
                    "required": ["payload"],
                    "additionalProperties": False,
                }
            )

    def test_rejects_array_without_items(self):
        with self.assertRaisesRegex(ValueError, "items.*required"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": {"items": {"type": "array"}},
                    "required": ["items"],
                    "additionalProperties": False,
                }
            )

    def test_rejects_unsupported_validation_keywords(self):
        with self.assertRaisesRegex(ValueError, "does not support.*minItems"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        }
                    },
                    "required": ["items"],
                    "additionalProperties": False,
                }
            )

    def test_rejects_reference_keywords(self):
        with self.assertRaisesRegex(ValueError, "does not support.*\\$ref"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": {"x": {"$ref": "#/$defs/X"}},
                    "required": ["x"],
                    "additionalProperties": False,
                }
            )

    def test_rejects_union_keywords(self):
        with self.assertRaisesRegex(ValueError, "does not support.*anyOf"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": {"x": {"anyOf": []}},
                    "required": ["x"],
                    "additionalProperties": False,
                }
            )
        with self.assertRaisesRegex(ValueError, "does not support.*type arrays"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": {"x": {"type": ["string", "null"]}},
                    "required": ["x"],
                    "additionalProperties": False,
                }
            )

    def test_rejects_too_many_optional_properties(self):
        properties = {f"p{i}": {"type": "string"} for i in range(MAX_OUTPUT_SCHEMA_OPTIONAL_PROPERTIES + 1)}
        with self.assertRaisesRegex(ValueError, "optional properties"):
            validate_output_schema(
                {
                    "type": "object",
                    "properties": properties,
                    "required": [],
                    "additionalProperties": False,
                }
            )

    def test_rejects_oversized_schema(self):
        schema = {
            "type": "object",
            "properties": {"big": {"type": "string", "description": "x" * MAX_OUTPUT_SCHEMA_BYTES}},
            "required": ["big"],
            "additionalProperties": False,
        }
        with self.assertRaisesRegex(ValueError, "maximum"):
            validate_output_schema(schema)

    def test_rejects_too_deep_schema(self):
        child = {"type": "string"}
        for _ in range(MAX_OUTPUT_SCHEMA_DEPTH):
            child = {
                "type": "object",
                "properties": {"child": child},
                "required": ["child"],
                "additionalProperties": False,
            }
        with self.assertRaisesRegex(ValueError, "depth"):
            validate_output_schema(child)


class TestValidateOutputAgainstSchema(unittest.TestCase):
    def test_accepts_supported_subset(self):
        payload = {
            "title": "Plan",
            "count": 3,
            "score": 4.5,
            "ok": True,
            "tags": ["a", "b"],
            "meta": {"kind": "a"},
        }
        self.assertEqual(validate_output_against_schema(payload, VALID_SCHEMA), payload)

    def test_rejects_missing_required_property(self):
        payload = {
            "count": 3,
            "score": 4.5,
            "ok": True,
            "tags": [],
            "meta": {"kind": "a"},
        }
        with self.assertRaisesRegex(ValueError, "missing required property.*title"):
            validate_output_against_schema(payload, VALID_SCHEMA)

    def test_rejects_additional_property_when_closed(self):
        payload = {
            "title": "Plan",
            "count": 3,
            "score": 4.5,
            "ok": True,
            "tags": [],
            "meta": {"kind": "a"},
            "extra": "nope",
        }
        with self.assertRaisesRegex(ValueError, "unexpected property.*extra"):
            validate_output_against_schema(payload, VALID_SCHEMA)

    def test_rejects_wrong_primitive_type(self):
        payload = {
            "title": "Plan",
            "count": "3",
            "score": 4.5,
            "ok": True,
            "tags": [],
            "meta": {"kind": "a"},
        }
        with self.assertRaisesRegex(ValueError, "count.*integer"):
            validate_output_against_schema(payload, VALID_SCHEMA)

    def test_rejects_enum_violation(self):
        payload = {
            "title": "Plan",
            "count": 3,
            "score": 4.5,
            "ok": True,
            "tags": [],
            "meta": {"kind": "c"},
        }
        with self.assertRaisesRegex(ValueError, "meta\\.kind.*enum"):
            validate_output_against_schema(payload, VALID_SCHEMA)

    def test_rejects_array_item_type_violation(self):
        payload = {
            "title": "Plan",
            "count": 3,
            "score": 4.5,
            "ok": True,
            "tags": ["a", 2],
            "meta": {"kind": "a"},
        }
        with self.assertRaisesRegex(ValueError, "tags\\[1\\].*string"):
            validate_output_against_schema(payload, VALID_SCHEMA)


class TestStrictJsonParsing(unittest.TestCase):
    def test_rejects_nan_constant(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON constant.*NaN"):
            parse_strict_json('{"score": NaN}')

    def test_rejects_infinity_constant(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON constant.*Infinity"):
            parse_strict_json('{"score": Infinity}')


class TestValidateOutputSchemaCli(unittest.TestCase):
    def test_cli_validates_output_file_against_eval_json_schema(self):
        from evals import output_schema

        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            eval_dir = root / "evals" / "planner"
            eval_dir.mkdir(parents=True)
            eval_json = eval_dir / "eval.json"
            output_file = root / "output.json"
            eval_json.write_text(
                json.dumps(
                    {
                        "target": {
                            "mode": "prompt_file",
                            "prompt_file": "p.md",
                            "output_schema": {
                                "type": "object",
                                "properties": {"title": {"type": "string"}},
                                "required": ["title"],
                                "additionalProperties": False,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            output_file.write_text('{"title": "ok"}', encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = output_schema.main(["--eval-json", str(eval_json), "--output-file", str(output_file)])

            self.assertEqual(rc, 0)

    def test_cli_rejects_malformed_json_output(self):
        from evals import output_schema

        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            eval_dir = root / "evals" / "planner"
            eval_dir.mkdir(parents=True)
            eval_json = eval_dir / "eval.json"
            output_file = root / "output.json"
            eval_json.write_text(
                json.dumps(
                    {
                        "target": {
                            "mode": "prompt_file",
                            "prompt_file": "p.md",
                            "output_schema": {
                                "type": "object",
                                "properties": {"title": {"type": "string"}},
                                "required": ["title"],
                                "additionalProperties": False,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            output_file.write_text("not json", encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = output_schema.main(["--eval-json", str(eval_json), "--output-file", str(output_file)])

            self.assertEqual(rc, 1)

    def test_cli_rejects_nan_json_constant(self):
        from evals import output_schema

        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            eval_dir = root / "evals" / "planner"
            eval_dir.mkdir(parents=True)
            eval_json = eval_dir / "eval.json"
            output_file = root / "output.json"
            eval_json.write_text(
                json.dumps(
                    {
                        "target": {
                            "mode": "prompt_file",
                            "prompt_file": "p.md",
                            "output_schema": {
                                "type": "object",
                                "properties": {"score": {"type": "number"}},
                                "required": ["score"],
                                "additionalProperties": False,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            output_file.write_text('{"score": NaN}', encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = output_schema.main(["--eval-json", str(eval_json), "--output-file", str(output_file)])

            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
