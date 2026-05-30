"""Deterministic renderer: a validated workflow blueprint to Claude Code artifacts.

Parses the single fenced ```yaml block from a <name>.blueprint.md file, matching
workflow-design-validate, then renders Claude-Code-native files in later stages.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
AGENTIC = "agentic"
DETERMINISTIC = "deterministic"
SUBAGENT_CONTRACT_FIELDS = ("objective", "output_format", "tools", "boundaries")
MECHANICAL_SIGNALS = {
    "copy", "extract", "format", "lookup", "parse", "read", "transform", "normalize",
    "convert", "sort", "filter",
}
JUDGMENT_SIGNALS = {
    "ambiguous", "categorize", "classify", "decide", "judgment", "open-ended",
    "reason", "synthesize", "tradeoff",
}


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


def render_entry_command(bp: dict, workflow_name: str) -> str:
    inputs = bp.get("inputs") or []
    input_hint = " ".join(f"<{item.get('key', 'input')}>" for item in inputs) or "<inputs>"
    subagents = list(bp.get("subagents") or [])
    agentic_index = 0
    lines = [
        "---",
        f"description: Run the {workflow_name} agent workflow",
        f"argument-hint: {input_hint}",
        "---",
        "",
        f"# {workflow_name}",
        "",
        "## Execution Rules",
        "",
        "- Dispatch agentic steps one level deep only; do not nest subagent calls.",
        "- Run deterministic steps through their generated scripts.",
        "- Stop on failed scripts, failed gates, or violated termination conditions.",
        "",
        "## Steps",
        "",
    ]
    for index, step in enumerate(bp.get("steps") or [], start=1):
        step_id = str(step.get("id", f"step-{index}"))
        if step.get("kind") == AGENTIC:
            if agentic_index >= len(subagents):
                raise ScaffoldError(f"agentic step {step_id!r} has no paired subagent")
            subagent = subagents[agentic_index]
            agentic_index += 1
            lines.append(
                f"{index}. `{step_id}` - dispatch subagent `{subagent.get('id')}`."
            )
            if step.get("termination"):
                lines.append(f"   Termination: {step['termination']}")
        else:
            lines.append(
                f"{index}. `{step_id}` - run script `.claude/scripts/{step_script_filename(step)}`."
            )
        lines.append("")
    return "\n".join(lines)


def warn_overpowered_steps(bp: dict) -> list[str]:
    warnings = []
    for step in bp.get("steps") or []:
        if step.get("kind") != AGENTIC:
            continue
        text = " ".join([
            str(step.get("id", "")),
            str(step.get("rationale", "")),
            str(step.get("pattern", "")),
            str(step.get("termination", "")),
        ]).lower()
        has_mechanical_signal = any(signal in text for signal in MECHANICAL_SIGNALS)
        has_judgment_signal = any(signal in text for signal in JUDGMENT_SIGNALS)
        if has_mechanical_signal and not has_judgment_signal:
            step_id = step.get("id", "<unknown>")
            warnings.append(
                f"agentic step {step_id!r} looks mechanical; a script may be simpler"
            )
    return warnings


def _workflow_name(blueprint_path: str | Path) -> str:
    name = Path(blueprint_path).name
    if name.endswith(".blueprint.md"):
        return name[: -len(".blueprint.md")]
    return Path(blueprint_path).stem


def _plan_outputs(bp: dict, workflow_name: str, out_dir: str | Path) -> list[tuple[Path, str, bool]]:
    base = Path(out_dir)
    outputs: list[tuple[Path, str, bool]] = []
    for step in bp.get("steps") or []:
        if step.get("kind") == DETERMINISTIC:
            outputs.append((
                base / ".claude" / "scripts" / step_script_filename(step),
                render_step_script(step),
                True,
            ))
    for subagent in bp.get("subagents") or []:
        outputs.append((
            base / ".claude" / "agents" / subagent_filename(subagent),
            render_subagent(subagent),
            False,
        ))
    gated_rubrics = [
        rubric for rubric in (bp.get("rubrics") or [])
        if rubric.get("gate") is not None
    ]
    for rubric in gated_rubrics:
        outputs.append((
            base / ".claude" / "hooks" / hook_filename(rubric),
            render_hook(rubric),
            True,
        ))
    if gated_rubrics:
        outputs.append((
            base / ".claude" / "hooks.json",
            render_hooks_json(gated_rubrics),
            False,
        ))
    outputs.append((
        base / ".claude" / "commands" / f"{workflow_name}.md",
        render_entry_command(bp, workflow_name),
        False,
    ))
    return outputs


def scaffold_blueprint(
    blueprint_path: str | Path,
    out_dir: str | Path = ".",
    dry_run: bool = False,
) -> tuple[list[Path], list[str]]:
    bp = load_blueprint(str(blueprint_path))
    workflow_name = _workflow_name(blueprint_path)
    warnings = warn_overpowered_steps(bp)
    planned = _plan_outputs(bp, workflow_name, out_dir)
    written = [path for path, _, _ in planned]
    if dry_run:
        return written, warnings
    for path, text, executable in planned:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if executable:
            path.chmod(path.stat().st_mode | 0o111)
    return written, warnings


def main(argv=None, stdout=None, stderr=None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(
        description="Render a workflow blueprint into Claude Code artifacts."
    )
    parser.add_argument("blueprint", help="path to <name>.blueprint.md")
    parser.add_argument("--out-dir", default=".", help="target project directory")
    parser.add_argument("--dry-run", action="store_true", help="print planned files only")
    args = parser.parse_args(argv)
    try:
        paths, warnings = scaffold_blueprint(
            args.blueprint,
            args.out_dir,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, ScaffoldError) as exc:
        print(f"ERROR: {exc}", file=stderr)
        return 2
    if args.dry_run:
        print("DRY RUN: would write", file=stdout)
    for warning in warnings:
        print(f"WARNING: {warning}", file=stdout)
    for path in paths:
        rel = os.path.relpath(path, args.out_dir)
        prefix = "would write" if args.dry_run else "wrote"
        print(f"{prefix} {rel}", file=stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
