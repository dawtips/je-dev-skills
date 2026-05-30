"""Deterministic renderer: a validated workflow blueprint to Claude Code artifacts.

Parses the single fenced ```yaml block from a <name>.blueprint.md file, matching
workflow-design-validate, then renders Claude-Code-native files in later stages.
"""

from __future__ import annotations

import re

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
AGENTIC = "agentic"
DETERMINISTIC = "deterministic"


def extract_yaml_block(text: str) -> str:
    blocks = YAML_FENCE.findall(text)
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```yaml block, found {len(blocks)}")
    return blocks[0]


def load_blueprint(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parsed = yaml.safe_load(extract_yaml_block(text))
    if not isinstance(parsed, dict):
        raise ValueError(
            "the ```yaml block must parse to a mapping of blueprint fields, "
            f"got {type(parsed).__name__}"
        )
    return parsed


def slugify(value: str) -> str:
    """Lowercase, replace non-alphanumeric runs with single hyphens, trim hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
