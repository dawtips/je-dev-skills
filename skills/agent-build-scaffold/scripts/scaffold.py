"""Deterministic renderer: a validated workflow blueprint to Claude Code artifacts.

Parses the single fenced ```yaml block from a <name>.blueprint.md file, matching
workflow-design-validate, then renders Claude-Code-native files in later stages.
"""

from __future__ import annotations

import json
import re

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
AGENTIC = "agentic"
DETERMINISTIC = "deterministic"
SUBAGENT_CONTRACT_FIELDS = ("objective", "output_format", "tools", "boundaries")


class ScaffoldError(ValueError):
    """Raised when a valid-looking blueprint cannot be rendered safely."""


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


def subagent_filename(subagent: dict) -> str:
    return f"{slugify(str(subagent.get('id', 'agent')))}.md"


def _frontmatter_list(values) -> str:
    if isinstance(values, list):
        return ", ".join(str(v) for v in values)
    return str(values)


def _validate_subagent_contract(subagent: dict) -> None:
    missing = []
    for field in SUBAGENT_CONTRACT_FIELDS:
        value = subagent.get(field)
        if field == "tools":
            if not (isinstance(value, list) and value):
                missing.append(field)
        elif value is None or str(value).strip() == "":
            missing.append(field)
    if missing:
        agent_id = subagent.get("id", "<unknown>")
        raise ScaffoldError(
            f"subagent {agent_id!r} has incomplete contract: {', '.join(missing)}"
        )


def render_subagent(subagent: dict) -> str:
    _validate_subagent_contract(subagent)
    agent_id = str(subagent.get("id", "agent"))
    model = str(subagent.get("model", "inherit"))
    tools = _frontmatter_list(subagent.get("tools", []))
    effort = str(subagent.get("effort", "inherit"))
    return "\n".join([
        "---",
        f"name: {slugify(agent_id)}",
        f"model: {model}",
        f"tools: {tools}",
        "---",
        "",
        f"# {agent_id}",
        "",
        "## Objective",
        str(subagent.get("objective", "")).strip(),
        "",
        "## Output Format",
        str(subagent.get("output_format", "")).strip(),
        "",
        "## Boundaries",
        str(subagent.get("boundaries", "")).strip(),
        "",
        "## Notes",
        f"- Recommended effort: {effort} (non-contract; tune per the live runtime).",
        "- Keep this subagent one level deep; do not dispatch nested subagents.",
        "",
    ])


def hook_filename(rubric: dict) -> str:
    return f"{slugify(str(rubric.get('name', 'rubric')))}-gate.sh"


def render_hook(rubric: dict) -> str:
    name = slugify(str(rubric.get("name", "rubric")))
    gate = rubric.get("gate")
    return "\n".join([
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# AUTO-GENERATED by agent-build-scaffold for rubric: {name}. Exit 0 = pass, exit 1 = block.",
        f'SCORE_FILE=".agent-build-state/{name}.score"',
        'if [ ! -f "$SCORE_FILE" ]; then',
        f'  echo "Missing score for rubric {name}: $SCORE_FILE" >&2',
        "  exit 1",
        "fi",
        'SCORE="$(cat "$SCORE_FILE")"',
        f'if [ "$SCORE" -lt "{gate}" ]; then',
        f'  echo "Rubric {name} failed: $SCORE < {gate}" >&2',
        "  exit 1",
        "fi",
        "exit 0",
        "",
    ])


def render_hooks_json(rubrics: list[dict]) -> str:
    commands = [
        {"command": f".claude/hooks/{hook_filename(rubric)}"}
        for rubric in rubrics
        if rubric.get("gate") is not None
    ]
    return json.dumps({"hooks": {"SubagentStop": commands}}, indent=2) + "\n"
