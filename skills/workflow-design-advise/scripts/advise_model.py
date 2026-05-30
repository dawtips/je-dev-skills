"""Deterministic Claude model + effort advisor for workflow blueprints.

Reads the single fenced ```yaml block of a <name>.blueprint.md, scores each
agentic step (advisory) and each subagent (writeable) against the routing and
effort-scaling rules in
skills/workflow-design-interview/references/model-selection.md, and reports a
recommended Claude tier + effort with a rationale. Deterministic and offline:
no API key, no model call. Genuine judgment is surfaced as needs_review, never
guessed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import yaml

# --- Volatile: Claude model IDs. SINGLE SOURCE in this module. --------------
# Blueprints store a TIER (the schema's `model` field is haiku|sonnet|opus|
# inherit, never a pinned ID), so the advisor recommends tiers and these IDs are
# only used for optional display/resolution. Re-verify against
# skills/workflow-design-interview/references/citations.md (the volatile-values
# table) and the Anthropic models-overview before relying on them. UPDATE HERE
# when the lineup changes -- never scatter model IDs elsewhere.
MODEL_IDS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-5",
    "opus": "claude-opus-4-1",
}

TIERS = ("haiku", "sonnet", "opus")          # cheap -> capable
EFFORTS = ("low", "medium", "high", "max")   # light -> heavy
ROLES = ("step", "worker", "orchestrator")
DIFFICULTIES = ("easy", "moderate", "hard")
BREADTHS = ("narrow", "moderate", "broad")

BASE_TIER = {"easy": "haiku", "moderate": "sonnet", "hard": "opus"}
EFFORT_BY_BREADTH = {"narrow": "low", "moderate": "medium", "broad": "high"}
DIFFICULTY_REASON = {
    "easy": "an easy, bounded task (classification/extraction/lookup) suits the cheapest tier",
    "moderate": "moderate multi-step reasoning or synthesis suits the mid tier",
    "hard": "hard, open-ended, high-stakes work suits the strongest tier",
}

# Pattern -> (difficulty, breadth, role) for an agentic STEP.
STEP_PATTERN_SIGNALS = {
    "route": ("easy", "narrow", "step"),
    "chain": ("moderate", "moderate", "step"),
    "evaluate": ("moderate", "moderate", "step"),
    "parallelize": ("moderate", "broad", "step"),
    "orchestrate": ("hard", "broad", "orchestrator"),
}

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


class AdviceInputError(Exception):
    """Blueprint path or content is invalid."""


@dataclass(frozen=True)
class TaskSignals:
    difficulty: str            # easy | moderate | hard
    breadth: str               # narrow | moderate | broad
    role: str                  # step | worker | orchestrator
    budget_pressure: str = "low"   # low | high

    def __post_init__(self) -> None:
        for field, allowed in (
            ("difficulty", DIFFICULTIES),
            ("breadth", BREADTHS),
            ("role", ROLES),
            ("budget_pressure", ("low", "high")),
        ):
            value = getattr(self, field)
            if value not in allowed:
                raise ValueError(f"{field} must be one of {allowed}, got {value!r}")


@dataclass(frozen=True)
class Recommendation:
    target_kind: str           # step | subagent
    target_id: str
    recommended_model: str
    recommended_effort: str
    rationale: str
    writeable: bool
    needs_review: bool
    current_model: str | None = None
    current_effort: str | None = None
    agrees: bool | None = None


def _step_down(tier: str) -> str:
    i = TIERS.index(tier)
    return TIERS[max(0, i - 1)]


def _max_tier(a: str, b: str) -> str:
    return a if TIERS.index(a) >= TIERS.index(b) else b


def score(signals: TaskSignals) -> tuple[str, str, str]:
    """Map task signals to a (tier, effort, rationale). Pure and deterministic.

    Rules from references/model-selection.md:
      - difficulty -> base tier (easy=haiku, moderate=sonnet, hard=opus), i.e.
        the cheapest tier that clears the difficulty bar (cost-minimization on
        the tier axis);
      - an orchestrator warrants at least the strongest tier;
      - a narrow, bounded worker runs one tier below its difficulty;
      - breadth -> effort (narrow=low, moderate=medium, broad=high). 'max' is
        never auto-recommended -- it is a human choice given the ~15x cost;
      - a human-supplied high cost/token budget caps effort at 'medium' to bound
        the ~15x effort multiplier (the guideline's cost-minimization input).

    Note: this deterministic form ties effort to breadth and tier to
    difficulty/role, so the guideline's "independent dials" cases (a Haiku
    worker at medium effort, an Opus orchestrator at low effort) are not
    auto-produced -- they remain a human override.
    """
    tier = BASE_TIER[signals.difficulty]
    reasons = [DIFFICULTY_REASON[signals.difficulty]]

    if signals.role == "orchestrator":
        bumped = _max_tier(tier, "opus")
        if bumped != tier:
            reasons.append("an orchestrator plans and synthesizes, so the strongest tier earns its cost")
        tier = bumped
    elif signals.role == "worker" and signals.breadth == "narrow" and signals.difficulty != "hard":
        stepped = _step_down(tier)
        if stepped != tier:
            reasons.append("a narrow, bounded worker subtask runs a tier below the orchestrator")
        tier = stepped

    effort = EFFORT_BY_BREADTH[signals.breadth]
    if signals.budget_pressure == "high" and EFFORTS.index(effort) > EFFORTS.index("medium"):
        effort = "medium"
        reasons.append("cost pressure caps effort at medium to bound the ~15x effort multiplier")

    return tier, effort, "; ".join(reasons) + "."


def extract_yaml_block(text: str) -> str:
    blocks = YAML_FENCE.findall(text)
    if len(blocks) != 1:
        raise AdviceInputError(f"expected exactly one ```yaml block, found {len(blocks)}")
    return blocks[0]


def load_blueprint(path: str | Path) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise AdviceInputError(str(exc)) from exc
    try:
        parsed = yaml.safe_load(extract_yaml_block(text))
    except yaml.YAMLError as exc:
        raise AdviceInputError(f"invalid yaml: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AdviceInputError(
            "the ```yaml block must parse to a mapping of blueprint fields, "
            f"got {type(parsed).__name__}")
    return parsed


def derive_signals_for_step(step: dict) -> tuple[TaskSignals | None, bool]:
    """Derive (signals, needs_review) for one step.

    Returns (None, False) for deterministic steps (no model). For an agentic
    step whose `pattern` is not in STEP_PATTERN_SIGNALS (e.g. 'none'), returns a
    conservative moderate/moderate/step default with needs_review=True.
    """
    if step.get("kind") != "agentic":
        return None, False
    pattern = step.get("pattern")
    if pattern in STEP_PATTERN_SIGNALS:
        difficulty, breadth, role = STEP_PATTERN_SIGNALS[pattern]
        return TaskSignals(difficulty=difficulty, breadth=breadth, role=role), False
    return TaskSignals(difficulty="moderate", breadth="moderate", role="step"), True


def _breadth_from_tools(tools: Any) -> str:
    n = len(tools) if isinstance(tools, list) else 0
    if n <= 1:
        return "narrow"
    if n <= 3:
        return "moderate"
    return "broad"


def derive_signals_for_subagent(subagent: dict) -> tuple[TaskSignals, bool]:
    """Derive (signals, needs_review) for one subagent.

    Breadth comes from the tool count (a structural signal). Difficulty is a
    judgment the structure cannot decide, so it is assumed 'moderate' and
    needs_review is always True -- the human confirms the difficulty before the
    recommendation is applied.
    """
    signals = TaskSignals(
        difficulty="moderate",
        breadth=_breadth_from_tools(subagent.get("tools")),
        role="worker",
    )
    return signals, True


def _agreement(cur_model: Any, cur_effort: Any, rec_model: str, rec_effort: str) -> bool | None:
    # Undecided (None, not a disagreement) only when 'inherit' or NOTHING is
    # chosen yet. A half-specified entry (one field set) is still compared, so a
    # wrong-but-partial choice (e.g. model=haiku, no effort) trips --strict.
    if cur_model == "inherit":
        return None
    if cur_model is None and cur_effort is None:
        return None
    return cur_model == rec_model and cur_effort == rec_effort


def advise_blueprint(bp: dict, budget_pressure: str = "low") -> list[Recommendation]:
    """Score every agentic step (advisory) and subagent (writeable).

    budget_pressure is a workflow-level, human-supplied signal (the guideline's
    third input, cost/token minimization). It is threaded into every TaskSignals
    so the cost cap in score() can fire; it is never guessed from blueprint prose.
    """
    recs: list[Recommendation] = []

    steps = bp.get("steps")
    if steps is None:
        steps = []
    if not isinstance(steps, list):
        raise AdviceInputError(f"steps must be a list, got {type(steps).__name__}")
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise AdviceInputError(
                f"steps[{i}] must be a mapping, got {type(step).__name__}")
        signals, needs_review = derive_signals_for_step(step)
        if signals is None:
            continue
        model, effort, rationale = score(replace(signals, budget_pressure=budget_pressure))
        recs.append(Recommendation(
            target_kind="step",
            target_id=str(step.get("id", f"steps[{i}]")),
            recommended_model=model,
            recommended_effort=effort,
            rationale=rationale,
            writeable=False,  # the schema stores model/effort on subagents only
            needs_review=needs_review,
        ))

    subagents = bp.get("subagents")
    if subagents is None:
        subagents = []
    if not isinstance(subagents, list):
        raise AdviceInputError(
            f"subagents must be a list, got {type(subagents).__name__}")
    for i, sub in enumerate(subagents):
        if not isinstance(sub, dict):
            raise AdviceInputError(
                f"subagents[{i}] must be a mapping, got {type(sub).__name__}")
        signals, needs_review = derive_signals_for_subagent(sub)
        model, effort, rationale = score(replace(signals, budget_pressure=budget_pressure))
        cur_model = sub.get("model")
        cur_effort = sub.get("effort")
        recs.append(Recommendation(
            target_kind="subagent",
            target_id=str(sub.get("id", f"subagents[{i}]")),
            recommended_model=model,
            recommended_effort=effort,
            rationale=rationale,
            writeable=True,
            needs_review=needs_review,
            current_model=str(cur_model) if cur_model is not None else None,
            current_effort=str(cur_effort) if cur_effort is not None else None,
            agrees=_agreement(cur_model, cur_effort, model, effort),
        ))

    return recs


def render_report(recs: list[Recommendation], blueprint_name: str, date: str) -> str:
    lines = [
        f"# Model advice: {blueprint_name}",
        "",
        f"Advised: {date} | deterministic | Claude tiers only",
        "",
        "| Target | Kind | Recommended | Effort | Current | Agree | Review |",
        "|---|---|---|---|---|:---:|:---:|",
    ]
    for r in recs:
        if r.target_kind != "subagent" or (r.current_model is None and r.current_effort is None):
            current = "—"
        else:
            current = f"{r.current_model or '—'}/{r.current_effort or '—'}"
        if r.agrees is True:
            agree = "yes"
        elif r.agrees is False:
            agree = "NO"
        elif r.current_model == "inherit":
            agree = "inherit?"
        elif r.target_kind == "subagent":
            agree = "unset?"
        else:
            agree = "—"
        review = "!" if r.needs_review else ""
        lines.append(
            f"| {r.target_id} | {r.target_kind} | {r.recommended_model} | "
            f"{r.recommended_effort} | {current} | {agree} | {review} |"
        )

    lines.extend(["", "## Rationale", ""])
    for r in recs:
        scope = "writeable" if r.writeable else "advisory (no model/effort field on steps)"
        lines.append(f"- **{r.target_id}** ({scope}): {r.rationale}")
        if r.needs_review:
            lines.append(
                f"  - review: confirm the assumed task difficulty for "
                f"`{r.target_id}` before applying."
            )
    lines.append("")
    return "\n".join(lines)


def recommendations_to_json(recs: list[Recommendation]) -> str:
    return json.dumps([asdict(r) for r in recs], indent=2)


def resolve_blueprint_path(explicit_path: str | None, cwd: str | Path | None = None) -> Path:
    root = Path(cwd) if cwd is not None else Path.cwd()
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            raise AdviceInputError(f"blueprint not found: {path}")
        if not path.is_file():
            raise AdviceInputError(f"blueprint path is not a file: {path}")
        if not path.name.endswith(".blueprint.md"):
            raise AdviceInputError(f"blueprint path must end with .blueprint.md: {path}")
        return path
    matches = sorted((root / "workflows").glob("*.blueprint.md"))
    if not matches:
        raise AdviceInputError("no ./workflows/*.blueprint.md file found")
    if len(matches) > 1:
        rendered = ", ".join(str(p) for p in matches)
        raise AdviceInputError(f"multiple blueprint files found; pass one path explicitly: {rendered}")
    return matches[0]


def has_disagreement(recs: list[Recommendation]) -> bool:
    return any(r.writeable and r.agrees is False for r in recs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Advise Claude model + effort for a workflow blueprint.")
    parser.add_argument("path", nargs="?", help="path to <name>.blueprint.md")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--date", help="advice date for the report header, e.g. 2026-05-30")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any subagent's model/effort disagrees with the advice")
    parser.add_argument("--budget", choices=("low", "high"), default="low",
                        help="workflow cost/token pressure; 'high' caps effort at medium")
    args = parser.parse_args(argv)

    if not args.json and not args.date:
        print("ERROR: --date is required for the report (or pass --json)", file=sys.stderr)
        return 2
    try:
        path = resolve_blueprint_path(args.path)
        bp = load_blueprint(path)
        recs = advise_blueprint(bp, budget_pressure=args.budget)
    except AdviceInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(recommendations_to_json(recs))
    else:
        print(render_report(recs, path.name, args.date))

    if args.strict and has_disagreement(recs):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
