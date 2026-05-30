"""Deterministic multi-run variance over K runs of the SAME frozen dataset.

Per-case mean/stddev across the K runs, flagging high-variance (flaky) cases, plus
a suggested regression band (worst-case grading noise) that prompt-engineering-improve
can use to calibrate its regression_band instead of the hardcoded 0.5 (spec §13).

This module AGGREGATES K run files; producing them (re-running evaluate K times, or
re-grading) is the caller's job — kept separate so this stays a pure, offline function.
"""

import argparse
import json
import statistics
import sys

from evals.runs_util import case_key, load_json

DEFAULT_FLAKY_STDDEV = 1.0  # on the 1-10 score scale


def compute_variance(runs: list[dict], flaky_stddev: float = DEFAULT_FLAKY_STDDEV) -> dict:
    """Aggregate per-case score variance across K run dicts of one dataset."""
    if not runs:
        raise ValueError("compute_variance requires at least one run")

    keys = [case_key(r, i) for i, r in enumerate(runs[0].get("results", []))]
    score_maps = [
        {case_key(r, i): r["score"] for i, r in enumerate(run.get("results", []))}
        for run in runs
    ]

    per_case = []
    for key in keys:
        scores = [m[key] for m in score_maps if key in m]
        stddev = round(statistics.pstdev(scores), 3)
        per_case.append(
            {
                "case": key,
                "scores": scores,
                "runs": len(scores),
                "mean": round(statistics.fmean(scores), 2),
                "stddev": stddev,
                "min": min(scores),
                "max": max(scores),
                "flaky": stddev > flaky_stddev,
            }
        )

    avgs = [run.get("summary", {}).get("average_score", 0.0) for run in runs]
    aggregate = {
        "runs": len(runs),
        "mean_average_score": round(statistics.fmean(avgs), 2),
        "stddev_average_score": round(statistics.pstdev(avgs), 3),
        "flaky_cases": sum(1 for c in per_case if c["flaky"]),
    }
    suggested = round(max((c["stddev"] for c in per_case), default=0.0), 2)
    return {"aggregate": aggregate, "per_case": per_case, "suggested_regression_band": suggested}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Per-case score variance across K runs of one frozen dataset."
    )
    ap.add_argument("runs", nargs="+", help="two or more output.json paths (same dataset)")
    ap.add_argument(
        "--flaky-stddev",
        type=float,
        default=DEFAULT_FLAKY_STDDEV,
        help=f"stddev above which a case is flaky (default {DEFAULT_FLAKY_STDDEV})",
    )
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = ap.parse_args(argv)
    try:
        report = compute_variance([load_json(p) for p in args.runs], args.flaky_stddev)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        agg = report["aggregate"]
        print(
            f"{agg['runs']} runs | mean avg {agg['mean_average_score']} "
            f"(±{agg['stddev_average_score']}) | flaky cases {agg['flaky_cases']} | "
            f"suggested regression_band {report['suggested_regression_band']}"
        )
        for c in report["per_case"]:
            flag = "  FLAKY" if c["flaky"] else ""
            print(f"  {c['case']}: mean {c['mean']} ±{c['stddev']} {c['scores']}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
