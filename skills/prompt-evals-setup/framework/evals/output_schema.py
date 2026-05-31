"""Structured-output schema guards for prompt targets.

This module intentionally implements a small, dependency-free JSON Schema subset:
enough to validate the project-owned ``target.output_schema`` contract before it reaches
Claude structured outputs / strict tool use, and enough to validate captured no-key tool
arguments before the eval pipeline persists them as raw output.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

MAX_OUTPUT_SCHEMA_BYTES = 16_384
MAX_OUTPUT_SCHEMA_DEPTH = 12
MAX_OUTPUT_SCHEMA_OPTIONAL_PROPERTIES = 24

_REFERENCE_KEYS = {"$ref", "$defs", "definitions", "$recursiveRef", "$dynamicRef"}
_UNION_KEYS = {"anyOf", "oneOf", "allOf"}
_SUPPORTED_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
_METADATA_KEYS = {"description", "title"}
_STRUCTURAL_KEYS = {"type", "properties", "required", "additionalProperties", "items", "enum"}
_SUPPORTED_KEYS = _STRUCTURAL_KEYS | _METADATA_KEYS


def validate_output_schema(schema: object, *, field: str = "target.output_schema") -> dict:
    """Validate the bounded schema subset this framework forwards to Claude."""
    if not isinstance(schema, dict):
        raise ValueError(f"{field} must be a JSON object")
    if schema.get("type") != "object":
        raise ValueError(f"{field} must be a JSON object schema with root type 'object'")
    _check_json_size(schema, field)
    _check_depth(schema, field)
    optional = _validate_schema_node(schema, field)
    if optional > MAX_OUTPUT_SCHEMA_OPTIONAL_PROPERTIES:
        raise ValueError(
            f"{field} has {optional} optional properties; "
            f"maximum is {MAX_OUTPUT_SCHEMA_OPTIONAL_PROPERTIES}"
        )
    return schema


def validate_output_against_schema(value: object, schema: dict) -> object:
    """Validate a captured structured output against the supported schema subset."""
    validate_output_schema(schema)
    _validate_value(value, schema, "output")
    return value


def parse_strict_json(text: str) -> object:
    """Parse strict JSON, rejecting Python's default NaN/Infinity extensions."""
    return json.loads(text, parse_constant=_reject_json_constant)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def _check_json_size(schema: dict, field: str) -> None:
    try:
        encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON-serializable") from exc
    if len(encoded) > MAX_OUTPUT_SCHEMA_BYTES:
        raise ValueError(
            f"{field} is {len(encoded)} bytes; maximum is {MAX_OUTPUT_SCHEMA_BYTES}"
        )


def _check_depth(value: object, field: str) -> None:
    depth = _depth(value)
    if depth > MAX_OUTPUT_SCHEMA_DEPTH:
        raise ValueError(f"{field} depth is {depth}; maximum is {MAX_OUTPUT_SCHEMA_DEPTH}")


def _depth(value: object) -> int:
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(_depth(v) for v in value.values())
    if isinstance(value, list):
        if not value:
            return 1
        return 1 + max(_depth(v) for v in value)
    return 0


def _validate_schema_node(schema: object, path: str) -> int:
    if not isinstance(schema, dict):
        raise ValueError(f"{path} must be a JSON object schema")

    for key in _REFERENCE_KEYS:
        if key in schema:
            raise ValueError(f"{path} does not support {key}")
    for key in _UNION_KEYS:
        if key in schema:
            raise ValueError(f"{path} does not support {key}")
    for key in sorted(set(schema) - _SUPPORTED_KEYS):
        raise ValueError(f"{path} does not support {key}")

    schema_type = schema.get("type")
    if schema_type is None:
        raise ValueError(f"{path}.type is required")
    if isinstance(schema_type, list):
        raise ValueError(f"{path} does not support type arrays")
    if schema_type not in _SUPPORTED_TYPES:
        raise ValueError(f"{path}.type must be one of {sorted(_SUPPORTED_TYPES)}")

    properties = schema.get("properties")
    if properties is not None and not isinstance(properties, dict):
        raise ValueError(f"{path}.properties must be a JSON object")

    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError(f"{path}.required must be an array of strings")
    required_set = set(required)

    optional = 0
    if schema_type == "object":
        if schema.get("additionalProperties") is not False:
            raise ValueError(f"{path}.additionalProperties must be false")
        unknown_required = required_set - set((properties or {}).keys())
        if unknown_required:
            raise ValueError(
                f"{path}.required references unknown properties: {sorted(unknown_required)}"
            )

    if properties:
        optional += len(set(properties) - required_set)
        for name, child in properties.items():
            if not isinstance(name, str):
                raise ValueError(f"{path}.properties keys must be strings")
            optional += _validate_schema_node(child, f"{path}.properties.{name}")

    items = schema.get("items")
    if schema_type == "array" and items is None:
        raise ValueError(f"{path}.items is required for array schemas")
    if items is not None:
        optional += _validate_schema_node(items, f"{path}.items")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"{path}.enum must be an array")

    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        raise ValueError(f"{path}.additionalProperties must be a boolean")

    return optional


def _validate_value(value: object, schema: dict, path: str) -> None:
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must match enum {schema['enum']!r}")

    schema_type = schema.get("type")
    if schema_type == "object":
        _validate_object(value, schema, path)
    elif schema_type == "array":
        _validate_array(value, schema, path)
    elif schema_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{path} must be an integer")
    elif schema_type == "number":
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(f"{path} must be a number")
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{path} must be a boolean")
    elif schema_type == "null":
        if value is not None:
            raise ValueError(f"{path} must be null")


def _validate_object(value: object, schema: dict, path: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object")

    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    for name in required:
        if name not in value:
            raise ValueError(f"{path} missing required property {name!r}")

    if schema.get("additionalProperties") is False:
        extras = sorted(set(value) - set(properties))
        if extras:
            raise ValueError(f"{path} has unexpected property {extras[0]!r}")

    for name, child_schema in properties.items():
        if name in value:
            child_path = name if path == "output" else f"{path}.{name}"
            _validate_value(value[name], child_schema, child_path)


def _validate_array(value: object, schema: dict, path: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    item_schema = schema.get("items")
    if item_schema is None:
        return
    for index, item in enumerate(value):
        _validate_value(item, item_schema, f"{path}[{index}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate structured output against eval.json")
    parser.add_argument("--eval-json", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args(argv)

    try:
        from evals.artifacts import load_eval_spec

        spec = load_eval_spec(args.eval_json)
        schema = spec.target.output_schema
        if schema is None:
            print("no target.output_schema configured")
            return 0
        output = parse_strict_json(Path(args.output_file).read_text(encoding="utf-8"))
        validate_output_against_schema(output, schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("structured output valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
