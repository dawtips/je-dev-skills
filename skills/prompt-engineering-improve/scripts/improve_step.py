"""Deterministic loop logic for prompt-engineering-improve.

Reads a round's evals/runs/<label>/output.json + a loop-state JSON and emits the
per-round delta, the running best version id (argmax), a continue|stop verdict, a
diagnosis tally, and an EXTRA_CRITERIA freeze-guard. NO model calls; NO float math,
argmax, tally, freeze-check, or serialization is done by the SKILL prose - only here.

CLI:
    python3 improve_step.py --output-json <path> --loop-state <path> \
        [--delta-out <path>] [--check-freeze]

Exit codes: 0 = continue; 1 = stop (a stopping rule fired); 2 = bad input /
freeze violation. Mirrors workflow-design-validate/scripts/validate_blueprint.py.
"""
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict


PASS_THRESHOLD = 7  # mirrors config.PASS_THRESHOLD; mandatory-fail per grading.md is score <= 3.
MANDATORY_FAIL_MAX = 3


def load_output_json(path: str) -> dict:
    """Load an evals/runs/<label>/output.json.

    Raises FileNotFoundError if absent, ValueError if it lacks the {summary,
    results} shape report.py writes.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "summary" not in data or "results" not in data:
        raise ValueError(
            f"{path}: not a report (expected top-level 'summary' and 'results')")
    if not isinstance(data["summary"], dict) or "average_score" not in data["summary"]:
        raise ValueError(f"{path}: 'summary' missing 'average_score'")
    return data


def load_loop_state(path: str) -> dict:
    """Load the small loop-state JSON.

    Raises FileNotFoundError if absent, ValueError if it lacks 'params' or
    'rounds'.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key in ("params", "rounds"):
        if key not in data:
            raise ValueError(f"{path}: loop-state missing '{key}'")
    return data


@dataclass
class RoundRecord:
    """One completed round's headline numbers (read from its output.json summary)."""
    version: str
    avg: float
    pass_rate: float


def compute_delta(*, current_avg: float, prior_avg: float | None) -> float | None:
    """Avg-score change vs. the prior round, rounded to 2 dp. None on the baseline."""
    if prior_avg is None:
        return None
    return round(current_avg - prior_avg, 2)


def running_best(rounds: list[RoundRecord]) -> RoundRecord | None:
    """The highest-avg round so far (argmax). Ties -> earliest (stable max by index)."""
    if not rounds:
        return None
    best = rounds[0]
    for r in rounds[1:]:
        if r.avg > best.avg:  # strict > keeps the earliest on a tie
            best = r
    return best
