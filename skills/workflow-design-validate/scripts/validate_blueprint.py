"""Deterministic completeness validator for workflow blueprints.

Parses the single fenced ```yaml block from a <name>.blueprint.md file and
checks it against the schema in docs/WORKFLOW_DESIGN_SPEC.md §4.1.
"""
import argparse
import re
import sys
from dataclasses import dataclass

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)

REQUIRED_DIMENSIONS = [
    "observability", "cost_latency_budgets", "guardrails_permissions",
    "context_management", "human_in_the_loop", "state_artifact_passing",
    "failure_handling", "retry_idempotency", "rollback_compensation",
    "termination_conditions", "tool_selection", "evaluation_success",
]
VALID_KINDS = {"deterministic", "agentic"}
CONTRACT_FIELDS = ["objective", "output_format", "tools", "boundaries", "model", "effort"]


@dataclass
class Gap:
    path: str
    message: str

    def __str__(self):
        return f"{self.path}: {self.message}"


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


def _nonempty(value) -> bool:
    return value is not None and str(value).strip() != ""


def check_dimensions(bp: dict):
    gaps = []
    dims = bp.get("dimensions") or {}
    accounted = 0
    for name in REQUIRED_DIMENSIONS:
        if name not in dims:
            gaps.append(Gap(f"dimensions.{name}",
                            "missing — must be 'specified' or {n/a: <rationale>}"))
            continue
        val = dims[name]
        if val == "specified":
            accounted += 1
        elif isinstance(val, dict) and _nonempty(val.get("n/a")):
            accounted += 1
        else:
            gaps.append(Gap(f"dimensions.{name}",
                            "must be 'specified' or {n/a: <non-empty rationale>}"))
    return gaps, (accounted, len(REQUIRED_DIMENSIONS))


def check_steps(bp: dict):
    gaps = []
    for i, step in enumerate(bp.get("steps") or []):
        p = f"steps[{i}]"
        if step.get("kind") not in VALID_KINDS:
            gaps.append(Gap(f"{p}.kind", f"must be one of {sorted(VALID_KINDS)}"))
        if not _nonempty(step.get("rationale")):
            gaps.append(Gap(f"{p}.rationale", "missing — required for every step"))
        if step.get("kind") == "agentic" and not _nonempty(step.get("termination")):
            gaps.append(Gap(f"{p}.termination", "required for agentic steps"))
        if step.get("side_effecting"):
            retry = step.get("retry") or {}
            if not _nonempty(retry.get("idempotency_key")):
                gaps.append(Gap(f"{p}.retry.idempotency_key",
                                "required for side_effecting steps"))
        if step.get("reversible") and not _nonempty(step.get("rollback")):
            gaps.append(Gap(f"{p}.rollback", "required for reversible steps"))
    return gaps


def check_subagents(bp: dict):
    gaps = []
    subs = bp.get("subagents") or []
    steps = bp.get("steps") or []
    if subs and not any(s.get("kind") == "agentic" for s in steps):
        gaps.append(Gap("subagents", "present but no agentic step justifies them"))
    for i, sa in enumerate(subs):
        p = f"subagents[{i}]"
        for field in CONTRACT_FIELDS:
            val = sa.get(field)
            if field == "tools":
                if not (isinstance(val, list) and len(val) > 0):
                    gaps.append(Gap(f"{p}.tools",
                                    "must be a non-empty list (least-privilege allowlist)"))
            elif not _nonempty(val):
                gaps.append(Gap(f"{p}.{field}", "missing — part of the required contract"))
    return gaps


def check_rubrics(bp: dict):
    gaps = []
    for i, r in enumerate(bp.get("rubrics") or []):
        p = f"rubrics[{i}]"
        if not _nonempty(r.get("scale")):
            gaps.append(Gap(f"{p}.scale", "missing categorical scale"))
        levels = r.get("levels")
        if not (isinstance(levels, dict) and len(levels) > 0):
            gaps.append(Gap(f"{p}.levels", "must define at least one level"))
        if r.get("gate") is None:
            gaps.append(Gap(f"{p}.gate", "missing pass/fail threshold"))
    return gaps


def check_outcomes(bp: dict):
    gaps = []
    for i, o in enumerate(bp.get("outcomes") or []):
        p = f"outcomes[{i}]"
        for field in ("given", "when", "then"):
            if not _nonempty(o.get(field)):
                gaps.append(Gap(f"{p}.{field}", "missing — outcomes must be Given-When-Then"))
    return gaps


def validate(bp: dict):
    gaps = []
    dim_gaps, coverage = check_dimensions(bp)
    gaps += dim_gaps
    gaps += check_steps(bp)
    gaps += check_subagents(bp)
    gaps += check_rubrics(bp)
    gaps += check_outcomes(bp)
    return gaps, coverage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a workflow blueprint for completeness.")
    parser.add_argument("path", help="path to <name>.blueprint.md")
    args = parser.parse_args(argv)
    try:
        bp = load_blueprint(args.path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    gaps, (accounted, total) = validate(bp)
    print(f"Coverage: {accounted}/{total} dimensions accounted for")
    if gaps:
        print(f"\n{len(gaps)} gap(s):")
        for gap in gaps:
            print(f"  - {gap}")
        print("\nFAIL")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
