"""Deterministic Mermaid visualizer for workflow blueprints.

Reads the single fenced ```yaml block from a <name>.blueprint.md file (the schema
in docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md §4.1) and emits a sibling
<name>.diagram.md: a Mermaid flowchart of the steps in list order, colored and
shaped by kind, with approval-gate nodes and a subagents subgraph, plus per-step
and per-subagent drill-down tables. Pure transform — no model call, no network,
no timestamp (byte-stable output).
"""
import argparse
import os
import re
import sys

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)

VALID_KINDS = {"deterministic", "agentic"}
GATE_LABELS = {"notify": "notify gate", "explicit": "explicit gate"}


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
            f"got {type(parsed).__name__}")
    return parsed


if __name__ == "__main__":
    sys.exit(main())
