"""Deterministic, no-model diff between two evaluation runs (baseline vs current).

Promotes the manual "diff output.json across versions" note (spec §13) into a
checked comparison. Consumed by prompt-engineering-improve's improve_step.py.
"""

import argparse
import json
import sys

from evals.runs_util import case_key, load_json


def compute_delta(baseline: dict, current: dict) -> dict:
    """Return aggregate + per-case score deltas (current - baseline)."""
    b_sum, c_sum = baseline.get("summary", {}), current.get("summary", {})
    aggregate = {
        "average_score": round(
            c_sum.get("average_score", 0.0) - b_sum.get("average_score", 0.0), 2
        ),
        "pass_rate": round(c_sum.get("pass_rate", 0.0) - b_sum.get("pass_rate", 0.0), 1),
        "passed": c_sum.get("passed", 0) - b_sum.get("passed", 0),
    }
    b_by_key = {case_key(r, i): r for i, r in enumerate(baseline.get("results", []))}
    per_case = []
    for i, r in enumerate(current.get("results", [])):
        key = case_key(r, i)
        before = b_by_key.get(key)
        per_case.append(
            {
                "case": key,
                "score_before": before["score"] if before else None,
                "score_after": r["score"],
                "delta": (r["score"] - before["score"]) if before else None,
                "matched": before is not None,
            }
        )
    return {"aggregate": aggregate, "per_case": per_case}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Diff two evaluation runs (current - baseline).")
    ap.add_argument("--baseline", required=True, help="path to the baseline run's output.json")
    ap.add_argument("--current", required=True, help="path to the current run's output.json")
    ap.add_argument("--json", action="store_true", help="print the full delta as JSON")
    args = ap.parse_args(argv)
    try:
        delta = compute_delta(load_json(args.baseline), load_json(args.current))
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(delta, indent=2))
    else:
        agg = delta["aggregate"]
        print(
            f"avg {agg['average_score']:+} | pass_rate {agg['pass_rate']:+}% | "
            f"passed {agg['passed']:+}"
        )
        for c in delta["per_case"]:
            d = "n/a (unmatched)" if c["delta"] is None else f"{c['delta']:+}"
            print(f"  {c['case']}: {c['score_before']} -> {c['score_after']} ({d})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
