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


def step_script_filename(step: dict) -> str:
    return f"{slugify(str(step.get('id', 'step')))}.sh"


def _shell_var_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def render_step_script(step: dict) -> str:
    step_id = str(step.get("id", "step"))
    rationale = str(step.get("rationale", "")).strip()
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# AUTO-GENERATED placeholder by agent-build-scaffold. Fill in the real command below.",
        f"# Step: {step_id}",
        f"# Rationale: {rationale}",
    ]
    if step.get("reversible") and step.get("rollback"):
        lines.append(f"# Rollback: {step['rollback']}")
    lines.append("")

    if step.get("side_effecting"):
        retry = step.get("retry") or {}
        key = str(retry.get("idempotency_key", "IDEMPOTENCY_KEY"))
        var_name = _shell_var_name(key)
        lines.extend([
            f'IDEMPOTENCY_KEY="${{{var_name}:?set {var_name}}}"',
            'MARKER=".agent-build-state/${IDEMPOTENCY_KEY}.done"',
            "mkdir -p .agent-build-state",
            'if [ -f "$MARKER" ]; then',
            f'  echo "Step {step_id} already completed for $IDEMPOTENCY_KEY"',
            "  exit 0",
            "fi",
            "",
            "echo 'TODO: implement the side-effecting command'",
            "",
            'touch "$MARKER"',
        ])
    else:
        lines.append("echo 'TODO: implement this deterministic step'")

    return "\n".join(lines) + "\n"
