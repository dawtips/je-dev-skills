# Eval Framework Hardening (v0.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the four `PROMPT_EVAL_FRAMEWORK_SPEC.md` §13 "v0.2 hardening" capabilities — multi-run variance/CI, baseline/previous-run delta, criteria audit (non-discriminating detection), and a deterministic structural-assertion layer — as standalone, offline, unit-tested modules at the vendored `evals/` top level.

**Architecture:** Four small, single-responsibility Python modules added beside `run_eval.py` in the vendored framework (`skills/prompt-evals-setup/framework/evals/`), each a pure function over the framework's existing file shapes (`datasets/<name>.json` and `runs/<label>/output.json`) plus a thin `argparse` CLI (`python -m evals.<module>`). **No model calls, no network, no API key.** A tiny shared helper (`runs_util.py`) holds the run-file loader + cross-run case-matching key. The framework **core is untouched** (`evals/evaluator/*.py`, `evals/prompts/`) — these compose around it, honoring the composition invariant named in the architecture spec §5 and prompt-engineering spec §9. `prompt-evals-setup` already vendors the whole `evals/` tree (`cp -R`), so new top-level files ship automatically with no setup change.

**Scope (v1 of this workstream):** the deterministic *cores* + CLIs that operate on existing artifacts. Live-path integration — pre-judge assertion **gating** inside the run loop, and orchestrating K live runs for variance — is deferred: it touches `run_evaluation`/`run_eval.py`, which the in-cc-execution-substrate plan rewrites, so wiring there would collide. Downstream consumers (`improve_step.py`, the `prompt-evals-run` skill) call these CLIs. This is called out in Task 6.

**Tech Stack:** Python 3.10+ stdlib only (`json`, `re`, `statistics`, `argparse`, `pathlib`), `unittest` offline fixtures. `python` is NOT on PATH in this environment — always use `python3`.

---

## Verified source facts (cite these; do not re-derive)

- **Run file** `runs/<label>/output.json` = `{meta, summary, results}`. `summary` = `{total, average_score, passed, pass_rate}`. Each `results[i]` = `{output, trajectory, test_case, score, reasoning, verdict}`; `test_case` = `{prompt_inputs, solution_criteria, task_description, scenario?}`. (`runs/smoke-single-shot/output.json`.)
- **Dataset file** `datasets/<name>.json` = `{provenance:{task_description, prompt_inputs_spec, num_cases, generator_model, created_at}, cases:[{prompt_inputs, solution_criteria, task_description, scenario?}]}`. (`datasets/smoke.json`.)
- `evals/config.py`: `PASS_THRESHOLD = 7`. Mandatory-fail (per `evals/prompts/grading.md`) = `score <= 3`. The §7 low-quality-criteria markers are subjective style words ("engaging, creative, well-formatted, insightful").
- **Test idiom** (`evals/tests/test_report.py`): `from evals.<module> import ...`; `unittest.TestCase`; run from the framework root `skills/prompt-evals-setup/framework` via `python3 -m unittest discover -s evals/tests -t .`. Single module: `python3 -m unittest evals.tests.test_<name> -v`.
- **Composition invariant:** do NOT edit `evals/evaluator/*.py` or `evals/prompts/`. New code only at the `evals/` top level + its `tests/`.

---

## File Structure

```
skills/prompt-evals-setup/framework/evals/
  runs_util.py        # Task 1 — load_json(path); case_key(result, index)   [shared by delta + variance]
  run_delta.py        # Task 2 — compute_delta(baseline, current) + CLI      [baseline/previous-run delta]
  variance.py         # Task 3 — compute_variance(runs, flaky_stddev) + CLI  [multi-run variance/CI + suggested_regression_band]
  criteria_audit.py   # Task 4 — audit_dataset(dataset) + has_issues + CLI   [non-discriminating + subjective + dup-scenario]
  assertions.py       # Task 5 — check_assertion/check_assertions/all_passed + CLI  [deterministic structural checks]
  README.md           # Task 6 — append "Hardening utilities (v0.2)" usage section
  tests/
    test_runs_util.py      # Task 1
    test_run_delta.py      # Task 2
    test_variance.py       # Task 3
    test_criteria_audit.py # Task 4
    test_assertions.py     # Task 5
```

Each module has one responsibility and is unit-testable in isolation — mirroring `workflow-design-validate/scripts/validate_blueprint.py`'s one-concern-per-function structure.

## Conventions for every task

- Work from the framework root: `cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework`.
- CLIs follow the repo idiom `python3 -m evals.<module> ...` (like `python3 -m evals.run_eval`).
- CLI exit codes follow `validate_blueprint.py`: `0` = clean/OK, `1` = issues found (advisory), `2` = unreadable input.
- Commit after each green task with the repo trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## Task 1: `runs_util.py` — shared run-file helpers

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/runs_util.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_runs_util.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_runs_util.py`:
```python
import json
import tempfile
import unittest
from pathlib import Path

from evals.runs_util import case_key, load_json


class TestLoadJson(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            p.write_text(json.dumps({"a": 1}), encoding="utf-8")
            self.assertEqual(load_json(p), {"a": 1})


class TestCaseKey(unittest.TestCase):
    def test_prefers_scenario(self):
        r = {"test_case": {"scenario": "wrestler cutting weight"}}
        self.assertEqual(case_key(r, 0), "wrestler cutting weight")

    def test_falls_back_to_index(self):
        self.assertEqual(case_key({"test_case": {}}, 4), "#4")
        self.assertEqual(case_key({}, 2), "#2")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest evals.tests.test_runs_util -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals.runs_util'`.

- [ ] **Step 3: Write minimal implementation**

`evals/runs_util.py`:
```python
"""Shared helpers for reading evaluation run files (evals/runs/<label>/output.json)."""

import json
from pathlib import Path


def load_json(path: str | Path) -> dict:
    """Read and parse a JSON file (a run's output.json or a dataset)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def case_key(result: dict, index: int) -> str:
    """A stable key for matching a result across runs of the same dataset.

    Prefer the human-readable ``scenario`` (stable across runs); fall back to the
    positional ``#<index>`` when a case has no scenario.
    """
    scenario = result.get("test_case", {}).get("scenario")
    return scenario if scenario else f"#{index}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest evals.tests.test_runs_util -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/runs_util.py skills/prompt-evals-setup/framework/evals/tests/test_runs_util.py
git commit -m "evals: add runs_util (load_json + cross-run case_key)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `run_delta.py` — baseline / previous-run delta

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/run_delta.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_run_delta.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_run_delta.py`:
```python
import unittest

from evals.run_delta import compute_delta


def run(avg, pass_rate, passed, cases):
    # cases: list of (scenario, score)
    return {
        "summary": {"average_score": avg, "pass_rate": pass_rate, "passed": passed},
        "results": [{"test_case": {"scenario": s}, "score": sc} for s, sc in cases],
    }


class TestComputeDelta(unittest.TestCase):
    def test_aggregate_delta(self):
        base = run(7.0, 50.0, 2, [("a", 6), ("b", 8)])
        cur = run(8.0, 100.0, 2, [("a", 8), ("b", 8)])
        d = compute_delta(base, cur)
        self.assertEqual(d["aggregate"]["average_score"], 1.0)
        self.assertEqual(d["aggregate"]["pass_rate"], 50.0)
        self.assertEqual(d["aggregate"]["passed"], 0)

    def test_per_case_matched_by_scenario(self):
        base = run(7.0, 50.0, 1, [("a", 6), ("b", 8)])
        cur = run(7.5, 50.0, 1, [("b", 8), ("a", 9)])  # reordered
        d = compute_delta(base, cur)
        by_case = {c["case"]: c for c in d["per_case"]}
        self.assertEqual(by_case["a"]["delta"], 3)  # 9 - 6, matched despite reorder
        self.assertTrue(by_case["a"]["matched"])

    def test_unmatched_case_reports_none(self):
        base = run(7.0, 0.0, 0, [("a", 6)])
        cur = run(8.0, 0.0, 0, [("new", 8)])
        d = compute_delta(base, cur)
        c = d["per_case"][0]
        self.assertEqual(c["case"], "new")
        self.assertIsNone(c["delta"])
        self.assertFalse(c["matched"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest evals.tests.test_run_delta -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals.run_delta'`.

- [ ] **Step 3: Write minimal implementation**

`evals/run_delta.py`:
```python
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
    b_by_key = {
        case_key(r, i): r for i, r in enumerate(baseline.get("results", []))
    }
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest evals.tests.test_run_delta -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/run_delta.py skills/prompt-evals-setup/framework/evals/tests/test_run_delta.py
git commit -m "evals: add run_delta (baseline/previous-run diff)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `variance.py` — multi-run variance / CI

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/variance.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_variance.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_variance.py`:
```python
import unittest

from evals.variance import compute_variance


def run(avg, cases):
    return {
        "summary": {"average_score": avg},
        "results": [{"test_case": {"scenario": s}, "score": sc} for s, sc in cases],
    }


class TestComputeVariance(unittest.TestCase):
    def setUp(self):
        # case "a" is stable (8,8,8); case "b" is flaky (10,5,7)
        self.runs = [
            run(9.0, [("a", 8), ("b", 10)]),
            run(6.5, [("a", 8), ("b", 5)]),
            run(7.5, [("a", 8), ("b", 7)]),
        ]

    def test_stable_case_zero_stddev(self):
        rep = compute_variance(self.runs)
        a = next(c for c in rep["per_case"] if c["case"] == "a")
        self.assertEqual(a["stddev"], 0.0)
        self.assertFalse(a["flaky"])
        self.assertEqual(a["mean"], 8.0)

    def test_flaky_case_flagged(self):
        rep = compute_variance(self.runs, flaky_stddev=1.0)
        b = next(c for c in rep["per_case"] if c["case"] == "b")
        self.assertGreater(b["stddev"], 1.0)
        self.assertTrue(b["flaky"])
        self.assertEqual(rep["aggregate"]["flaky_cases"], 1)

    def test_suggested_regression_band_is_worst_case_stddev(self):
        rep = compute_variance(self.runs)
        worst = max(c["stddev"] for c in rep["per_case"])
        self.assertEqual(rep["suggested_regression_band"], round(worst, 2))

    def test_requires_at_least_one_run(self):
        with self.assertRaises(ValueError):
            compute_variance([])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest evals.tests.test_variance -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals.variance'`.

- [ ] **Step 3: Write minimal implementation**

`evals/variance.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest evals.tests.test_variance -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/variance.py skills/prompt-evals-setup/framework/evals/tests/test_variance.py
git commit -m "evals: add variance (multi-run mean/stddev + flaky + suggested band)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `criteria_audit.py` — non-discriminating / subjective criteria detection

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/criteria_audit.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_criteria_audit.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_criteria_audit.py`:
```python
import unittest

from evals.criteria_audit import audit_dataset, has_issues


def dataset(cases):
    # cases: list of (scenario, [criteria...])
    return {
        "cases": [
            {"test_case": {}, "scenario": s, "solution_criteria": cr} for s, cr in cases
        ]
    }


class TestAuditDataset(unittest.TestCase):
    def test_subjective_criterion_flagged(self):
        ds = dataset([("a", ["Is engaging and creative"]), ("b", ["Lists three steps"])])
        rep = audit_dataset(ds)
        self.assertEqual(len(rep["subjective"]), 1)
        self.assertIn("engaging", rep["subjective"][0]["criterion"].lower())
        self.assertTrue(has_issues(rep))

    def test_non_discriminating_criterion_flagged(self):
        shared = "Includes a caloric total and macro breakdown"
        ds = dataset([("a", [shared]), ("b", [shared]), ("c", [shared])])
        rep = audit_dataset(ds)
        self.assertEqual(len(rep["non_discriminating"]), 1)
        self.assertEqual(rep["non_discriminating"][0]["count"], 3)

    def test_duplicate_scenarios_flagged(self):
        ds = dataset([("same", ["Lists steps"]), ("same", ["Names a tool"])])
        rep = audit_dataset(ds)
        self.assertIn("same", rep["duplicate_scenarios"])

    def test_clean_dataset_has_no_issues(self):
        ds = dataset([("a", ["Lists three steps"]), ("b", ["Names the API endpoint"])])
        rep = audit_dataset(ds)
        self.assertFalse(has_issues(rep))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest evals.tests.test_criteria_audit -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals.criteria_audit'`.

- [ ] **Step 3: Write minimal implementation**

`evals/criteria_audit.py`:
```python
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
    duplicate_scenarios = sorted(
        {s for s, n in Counter(scenarios).items() if n > 1}
    )

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest evals.tests.test_criteria_audit -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/criteria_audit.py skills/prompt-evals-setup/framework/evals/tests/test_criteria_audit.py
git commit -m "evals: add criteria_audit (subjective/non-discriminating/dup-scenario)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `assertions.py` — deterministic structural-assertion layer

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/assertions.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_assertions.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_assertions.py`:
```python
import unittest

from evals.assertions import all_passed, check_assertion, check_assertions


class TestCheckAssertion(unittest.TestCase):
    def test_contains_pass_and_fail(self):
        self.assertTrue(check_assertion("Total: 2400 kcal", {"type": "contains", "value": "kcal"})["passed"])
        self.assertFalse(check_assertion("no macros", {"type": "contains", "value": "kcal"})["passed"])

    def test_regex(self):
        self.assertTrue(check_assertion("2400 kcal", {"type": "regex", "pattern": r"\d+ kcal"})["passed"])

    def test_min_and_max_length(self):
        self.assertTrue(check_assertion("abcdef", {"type": "min_length", "value": 3})["passed"])
        self.assertFalse(check_assertion("abcdef", {"type": "max_length", "value": 3})["passed"])

    def test_json_valid_and_has_key(self):
        self.assertTrue(check_assertion('{"a": 1}', {"type": "json_valid"})["passed"])
        self.assertFalse(check_assertion("nope", {"type": "json_valid"})["passed"])
        self.assertTrue(check_assertion('{"a": 1}', {"type": "json_has_key", "key": "a"})["passed"])
        self.assertFalse(check_assertion('{"a": 1}', {"type": "json_has_key", "key": "b"})["passed"])

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            check_assertion("x", {"type": "bogus"})


class TestCheckAssertions(unittest.TestCase):
    def test_all_passed(self):
        specs = [{"type": "contains", "value": "kcal"}, {"type": "min_length", "value": 2}]
        results = check_assertions("2400 kcal", specs)
        self.assertEqual(len(results), 2)
        self.assertTrue(all_passed(results))

    def test_one_failure_breaks_all_passed(self):
        specs = [{"type": "contains", "value": "kcal"}, {"type": "contains", "value": "ZZZ"}]
        self.assertFalse(all_passed(check_assertions("2400 kcal", specs)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest evals.tests.test_assertions -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals.assertions'`.

- [ ] **Step 3: Write minimal implementation**

`evals/assertions.py`:
```python
"""Deterministic structural assertions checked in code — cheaper and more reliable
than the LLM judge for must-haves with a definite shape (spec §13).

A standalone engine: given an output string + a list of assertion specs, return a
pass/fail result per assertion. Result keys are ``text``/``passed``/``evidence`` to
match skill-creator's grading.json convention (see CONTRIBUTING.md). Wiring this as a
pre-judge GATE inside the run loop is deferred to the run-path work — this engine is
the reusable core, callable from a run_function or as a post-run audit over output.json.
"""

import argparse
import json
import sys


def check_assertion(output: str, spec: dict) -> dict:
    """Evaluate one assertion against ``output``. Raise ValueError on unknown type."""
    kind = spec.get("type")
    if kind == "contains":
        v = spec["value"]
        ok = v in output
        return {"text": f"contains {v!r}", "passed": ok, "evidence": f"{'found' if ok else 'missing'} {v!r}"}
    if kind == "not_contains":
        v = spec["value"]
        ok = v not in output
        return {"text": f"not_contains {v!r}", "passed": ok, "evidence": f"{'absent' if ok else 'found'} {v!r}"}
    if kind == "regex":
        import re
        p = spec["pattern"]
        m = re.search(p, output)
        return {"text": f"regex {p!r}", "passed": m is not None, "evidence": f"matched {m.group(0)!r}" if m else "no match"}
    if kind == "min_length":
        v = int(spec["value"])
        return {"text": f"min_length {v}", "passed": len(output) >= v, "evidence": f"len={len(output)}"}
    if kind == "max_length":
        v = int(spec["value"])
        return {"text": f"max_length {v}", "passed": len(output) <= v, "evidence": f"len={len(output)}"}
    if kind == "json_valid":
        try:
            json.loads(output)
            return {"text": "json_valid", "passed": True, "evidence": "valid JSON"}
        except (ValueError, TypeError):
            return {"text": "json_valid", "passed": False, "evidence": "invalid JSON"}
    if kind == "json_has_key":
        key = spec["key"]
        try:
            data = json.loads(output)
        except (ValueError, TypeError):
            return {"text": f"json_has_key {key!r}", "passed": False, "evidence": "invalid JSON"}
        ok = isinstance(data, dict) and key in data
        return {"text": f"json_has_key {key!r}", "passed": ok, "evidence": f"{'present' if ok else 'missing'} key {key!r}"}
    raise ValueError(f"unknown assertion type: {kind!r}")


def check_assertions(output: str, specs: list[dict]) -> list[dict]:
    return [check_assertion(output, s) for s in specs]


def all_passed(results: list[dict]) -> bool:
    return all(r["passed"] for r in results)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run structural assertions against an output file.")
    ap.add_argument("--output-file", required=True, help="path to the text output to check")
    ap.add_argument("--assertions", required=True, help="path to a JSON list of assertion specs")
    args = ap.parse_args(argv)
    try:
        from pathlib import Path
        output = Path(args.output_file).read_text(encoding="utf-8")
        specs = json.loads(Path(args.assertions).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    results = check_assertions(output, specs)
    for r in results:
        print(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['text']} — {r['evidence']}")
    return 0 if all_passed(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest evals.tests.test_assertions -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/assertions.py skills/prompt-evals-setup/framework/evals/tests/test_assertions.py
git commit -m "evals: add assertions (deterministic structural checks engine)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Document the utilities + full-suite verification

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/README.md` (append a section)

- [ ] **Step 1: Append the usage section**

Append to `skills/prompt-evals-setup/framework/evals/README.md`:
```markdown

## Hardening utilities (v0.2, offline)

Deterministic, no-model helpers (spec §13). Each is `python3 -m evals.<module>`; exit
`0` = clean/OK, `1` = differences/issues, `2` = unreadable input.

- **`run_delta`** — diff two runs: `python3 -m evals.run_delta --baseline runs/A/output.json --current runs/B/output.json`. Per-case + aggregate score deltas (matched by scenario). Used by `prompt-engineering-improve`.
- **`variance`** — variance across K runs of one frozen dataset: `python3 -m evals.variance runs/r1/output.json runs/r2/output.json runs/r3/output.json`. Reports per-case mean ± stddev, flags flaky cases, and prints a **suggested `regression_band`** (worst-case grading noise) to calibrate the improve loop.
- **`criteria_audit`** — static audit of a dataset's `solution_criteria`: `python3 -m evals.criteria_audit datasets/<name>.json`. Flags subjective-style, non-discriminating (identical across all cases), and duplicate scenarios.
- **`assertions`** — deterministic structural checks on an output: `python3 -m evals.assertions --output-file out.txt --assertions checks.json`. Supported types: `contains`, `not_contains`, `regex`, `min_length`, `max_length`, `json_valid`, `json_has_key`.

These compose around the framework core (no `evaluator/` change). Live-path integration
(pre-judge assertion gating; orchestrating K live runs) is owned by the run-path work.
```

- [ ] **Step 2: Run the FULL offline suite (regression + new modules)**

Run: `cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .`
Expected: `OK` with the test count raised by the new modules (was 33; now 33 + 3 + 3 + 4 + 4 + 7 = 54).

- [ ] **Step 3: Verify the smoke test still passes (composition invariant — core untouched)**

Run: `cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m evals.examples.smoke_test && rm -f evals/datasets/smoke.json && rm -rf evals/runs/smoke-*`
Expected: smoke test prints success; artifacts cleaned up.

- [ ] **Step 4: Confirm the framework core is unmodified**

Run: `cd /home/dawti/je-dev-skills && git status --short skills/prompt-evals-setup/framework/evals/evaluator skills/prompt-evals-setup/framework/evals/prompts`
Expected: empty output (no changes under `evaluator/` or `prompts/`).

- [ ] **Step 5: Commit**

```bash
cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/README.md
git commit -m "evals: document v0.2 hardening utilities + verify full offline suite

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes (for the implementer)

- **Spec coverage (§13 v0.2 hardening):** multi-run variance → Task 3; deterministic-assertion layer → Task 5; baseline/previous-run delta → Task 2; criteria-audit (non-discriminating) → Task 4. The composition constraint (top-level modules, not `evaluator/`) is enforced by Task 6 Step 4.
- **Consumer hooks named in the reconciliation addenda:** `variance.suggested_regression_band` and `run_delta.compute_delta` are the functions `improve_step.py` will consume to replace its hardcoded `regression_band = 0.5` and home-grown delta (prompt-engineering spec §8 + plan forward-note). Keep these signatures stable.
- **Deferred (documented, not silently dropped):** pre-judge assertion *gating* inside `run_evaluation`, and orchestrating K live runs for variance — both touch the run path the in-cc-execution-substrate plan rewrites; doing them here would collide. The engines + CLIs are the composition-safe deliverable.
- **Type consistency:** `case_key(result, index)` and `load_json(path)` (Task 1) are imported unchanged by Tasks 2–4. Assertion result keys are `text`/`passed`/`evidence` everywhere (Task 5).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-eval-framework-hardening.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.
