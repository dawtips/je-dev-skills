"""Report-analyst rendering for baseline deltas and multi-run variance.

This module is display/orchestration only. Score deltas come from run_delta.py and
variance numbers come from variance.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from evals.run_delta import compute_delta
from evals.runs_util import load_json
from evals.variance import compute_variance


def _delta_movers(delta: dict) -> dict:
    matched = [
        row
        for row in delta.get("per_case", [])
        if row.get("matched") and row.get("delta") is not None
    ]
    if not matched:
        return {"best": None, "worst": None}
    return {
        "best": max(matched, key=lambda row: row["delta"]),
        "worst": min(matched, key=lambda row: row["delta"]),
    }


def _format_baseline_case(row: dict) -> str:
    if row.get("matched"):
        before = row["score_before"]
        delta = f"{row['delta']:+}"
    else:
        before = "unmatched"
        delta = "n/a"
    return f"{row['case']}: {before} -> {row['score_after']} ({delta})"


def _format_variance_case(row: dict) -> str:
    flag = " FLAKY" if row.get("flaky") else ""
    return (
        f"{row['case']}: mean {row['mean']} +/- {row['stddev']} "
        f"{row['scores']} ({row['runs']} runs){flag}"
    )


def build_report_analysis(
    current: dict,
    *,
    baseline: dict | None = None,
    variance_runs: list[dict] | None = None,
) -> dict:
    """Build advisory analysis from explicit run artifacts."""
    analysis = {
        "baseline_delta": {
            "available": False,
            "note": "Baseline delta: not available -- pass --baseline-output with a prior run output.json.",
        },
        "variance": {
            "available": False,
            "note": "Variance: not available -- needs >=2 runs of the same frozen dataset.",
        },
    }

    if baseline is not None:
        delta = compute_delta(baseline, current)
        analysis["baseline_delta"] = {
            "available": True,
            "aggregate": delta["aggregate"],
            "per_case": delta["per_case"],
            "movers": _delta_movers(delta),
        }

    runs = variance_runs or []
    if len(runs) >= 2:
        variance = compute_variance(runs)
        analysis["variance"] = {
            "available": True,
            "aggregate": variance["aggregate"],
            "per_case": variance["per_case"],
            "suggested_regression_band": variance["suggested_regression_band"],
        }

    return analysis


def analysis_from_paths(
    current_output: str | Path,
    *,
    baseline_output: str | Path | None = None,
    variance_outputs: list[str | Path] | None = None,
) -> dict:
    current = load_json(current_output)
    baseline = load_json(baseline_output) if baseline_output else None
    variance_runs = [load_json(path) for path in (variance_outputs or [])]
    return build_report_analysis(current, baseline=baseline, variance_runs=variance_runs)


def render_markdown(analysis: dict) -> str:
    lines = ["## Report Analyst", ""]
    delta = analysis["baseline_delta"]
    if delta["available"]:
        agg = delta["aggregate"]
        lines.append(
            f"- Baseline delta: average {agg['average_score']:+}, "
            f"pass rate {agg['pass_rate']:+}%, passed {agg['passed']:+}."
        )
        best = delta["movers"]["best"]
        worst = delta["movers"]["worst"]
        if best is not None and best["delta"] > 0:
            lines.append(f"- Biggest improvement: {best['case']} ({best['delta']:+}).")
        if worst is not None and worst["delta"] < 0:
            lines.append(f"- Biggest regression: {worst['case']} ({worst['delta']:+}).")
        for row in delta["per_case"]:
            lines.append(f"- Baseline case: {_format_baseline_case(row)}")
    else:
        lines.append(f"- {delta['note']}")

    variance = analysis["variance"]
    if variance["available"]:
        agg = variance["aggregate"]
        lines.append(
            f"- Variance: {agg['runs']} runs, mean average score "
            f"{agg['mean_average_score']} (+/- {agg['stddev_average_score']}), "
            f"flaky cases {agg['flaky_cases']}."
        )
        lines.append(f"- Suggested regression band: {variance['suggested_regression_band']}.")
        for row in variance["per_case"]:
            lines.append(f"- Variance case: {_format_variance_case(row)}")
    else:
        lines.append(f"- {variance['note']}")
    return "\n".join(lines) + "\n"


def render_html(analysis: dict, esc: Callable[[object], str]) -> str:
    markdown = render_markdown(analysis)
    items = []
    for line in markdown.splitlines():
        if line.startswith("- "):
            items.append(f"<li>{esc(line[2:])}</li>")
    return f"""
  <section class="analysis">
    <h2>Report Analyst</h2>
    <ul>{''.join(items)}</ul>
  </section>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render report-analyst data for explicit eval runs.")
    parser.add_argument("--current-output", required=True, help="current run output.json")
    parser.add_argument("--baseline-output", default=None, help="baseline run output.json")
    parser.add_argument(
        "--variance-output",
        action="append",
        default=[],
        help="run output.json to include in variance; pass once per run",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable analysis")
    args = parser.parse_args(argv)
    try:
        analysis = analysis_from_paths(
            args.current_output,
            baseline_output=args.baseline_output,
            variance_outputs=args.variance_output,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        print(render_markdown(analysis), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
