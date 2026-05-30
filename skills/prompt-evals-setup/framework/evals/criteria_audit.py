"""Deterministic audit of a frozen dataset's solution_criteria (spec §7, §13).

Promotes the manual criteria spot-check into a checked report. Flags:
- subjective-style criteria (the §7 low-quality markers — judged unreliably);
- non-discriminating criteria (identical across ALL cases — likely a global
  extra_criteria masquerading as per-case; skill-creator's analyzer pattern);
- duplicate scenarios (low coverage diversity).
No model calls.
"""

import argparse
import re
import sys
from collections import Counter

from evals.runs_util import load_json

# §7 "low quality" style words: subjective, not measurable. Whole-word, case-insensitive.
SUBJECTIVE_MARKERS = frozenset(
    {
        "engaging", "creative", "well-formatted", "insightful", "compelling",
        "elegant", "interesting", "good", "nice", "appropriate", "clear",
        "concise", "high-quality", "professional", "thoughtful", "readable",
    }
)
_SUBJECTIVE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(SUBJECTIVE_MARKERS)) + r")\b",
    re.IGNORECASE,
)


def _cases(dataset: dict) -> list[dict]:
    return dataset.get("cases", [])


def _scenario(case: dict) -> str:
    return case.get("scenario") or case.get("test_case", {}).get("scenario") or ""


def audit_dataset(dataset: dict) -> dict:
    cases = _cases(dataset)
    num_cases = len(cases)

    subjective = []
    criterion_counts: Counter[str] = Counter()
    for i, case in enumerate(cases):
        for crit in case.get("solution_criteria", []):
            criterion_counts[crit] += 1
            m = _SUBJECTIVE_RE.search(crit)
            if m:
                subjective.append({"case_index": i, "criterion": crit, "marker": m.group(1)})

    # Non-discriminating = a criterion present in EVERY case (num_cases > 1).
    non_discriminating = [
        {"criterion": crit, "count": count}
        for crit, count in criterion_counts.items()
        if num_cases > 1 and count == num_cases
    ]

    scenarios = [_scenario(c) for c in cases if _scenario(c)]
    duplicate_scenarios = sorted({s for s, n in Counter(scenarios).items() if n > 1})

    return {
        "num_cases": num_cases,
        "subjective": subjective,
        "non_discriminating": non_discriminating,
        "duplicate_scenarios": duplicate_scenarios,
    }


def has_issues(report: dict) -> bool:
    return bool(
        report["subjective"]
        or report["non_discriminating"]
        or report["duplicate_scenarios"]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit a frozen dataset's solution_criteria.")
    ap.add_argument("dataset", help="path to datasets/<name>.json")
    args = ap.parse_args(argv)
    try:
        report = audit_dataset(load_json(args.dataset))
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"Audited {report['num_cases']} cases.")
    for s in report["subjective"]:
        print(f"  SUBJECTIVE (case {s['case_index']}, '{s['marker']}'): {s['criterion']}")
    for nd in report["non_discriminating"]:
        print(
            f"  NON-DISCRIMINATING (in all {nd['count']} cases — consider extra_criteria): "
            f"{nd['criterion']}"
        )
    for dup in report["duplicate_scenarios"]:
        print(f"  DUPLICATE SCENARIO: {dup}")
    if not has_issues(report):
        print("  clean — no issues found.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
