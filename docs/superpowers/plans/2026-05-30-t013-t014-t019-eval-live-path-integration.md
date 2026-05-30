# Eval Live-Path Integration Implementation Plan

Status: In progress

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the shipped deterministic eval cores into the live/report path: report-analyst rendering for `run_delta` and `variance`, assertion gating before judge calls, and explicit K-run variance orchestration.

**Architecture:** Keep deterministic cores at the vendored `evals/` top level and compose new wiring around the existing evaluator core. T-013 lands first because it is report-only and safe before T-018; T-014 and T-019 start only after the T-018 run-path architecture decision is resolved or explicitly sequenced. New code calls `evals.run_delta.compute_delta`, `evals.variance.compute_variance`, and `evals.assertions.check_assertions`; it never reimplements score deltas, standard deviation, or assertion checks.

**Tech Stack:** Python 3.10+ standard library, `unittest`, existing `evals` package modules, Markdown skill docs, Story tickets.

---

## Scope And Sequencing

- Covered tickets: `T-013`, `T-014`, `T-019`.
- Source spec: `docs/superpowers/specs/2026-05-30-eval-live-path-integration-spec.md`.
- Hard sequencing: implement `T-013` first. Before `T-014` or `T-019`, read `docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md` and confirm whether `T-018` has landed. If it has not landed, keep the new in-loop modules top-level and portable; do not harden a project-vendored `./evals` assumption beyond the existing framework layout.
- Explicit policy locked by this plan for `T-014`: default `ASSERTION_POLICY = "gate_mandatory"`. Mandatory assertion failures skip the judge and produce a synthetic score `1`; advisory assertion failures annotate and still grade. Per-assertion `policy: "annotate"` overrides the default for one mandatory assertion.
- Explicit K-run label scheme locked by this plan for `T-019`: labels are caller-provided group label plus ordinal, `"{group_label}__k{ordinal:02d}"`. The group label is an explicit input; no timestamp or "latest run" lookup is used.

## File Structure

- Modify `skills/prompt-evals-setup/framework/evals/evaluator/report.py`: accept optional report analysis data and render a report-analyst section in JSON/HTML.
- Create `skills/prompt-evals-setup/framework/evals/report_analyst.py`: load explicit run artifacts, call `compute_delta` and `compute_variance`, compute display-only movers from delta output, and render Markdown/HTML fragments.
- Modify `skills/prompt-evals-setup/framework/evals/aggregate.py`: add explicit `--baseline-output` and repeatable `--variance-output` inputs, then attach report analysis to `output.json` and `output.html`.
- Create `skills/prompt-evals-setup/framework/evals/assertion_gate.py`: normalize assertion specs into gate/annotate actions, call `check_assertions`, and build synthetic gated verdicts.
- Create `skills/prompt-evals-setup/framework/evals/live_run.py`: top-level live run orchestration around `execute`, `grade`, `assertion_gate`, and report writers. This preserves the no-edit invariant for `skills/prompt-evals-setup/framework/evals/evaluator/`.
- Modify `skills/prompt-evals-setup/framework/evals/run_eval.py`: add `ASSERTIONS`, `ASSERTION_POLICY`, use `live_run.run_evaluation` for keyed `evaluate`, and add an explicit `evaluate-variance` command.
- Create `skills/prompt-evals-setup/framework/evals/variance_runner.py`: generate deterministic K labels, run a supplied evaluator K times, enumerate output artifacts by explicit labels, and call `compute_variance`.
- Modify `skills/prompt-evals-run/SKILL.md`: document explicit report-analyst inputs, Path A assertion gate procedure, and K-run cost disclosure.
- Modify `docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`: update the section 13 live-path note to point at this spec/plan once implemented.
- Tests:
  - Create `skills/prompt-evals-setup/framework/evals/tests/test_report_analyst.py`.
  - Modify `skills/prompt-evals-setup/framework/evals/tests/test_report.py`.
  - Modify `skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py`.
  - Create `skills/prompt-evals-setup/framework/evals/tests/test_assertion_gate.py`.
  - Create `skills/prompt-evals-setup/framework/evals/tests/test_live_run.py`.
  - Create `skills/prompt-evals-setup/framework/evals/tests/test_variance_runner.py`.
  - Modify `tools/tests/test_skill_lint.py` only if linter expectations change.

---

### Task 1: Start T-013 And Add Report-Analyst Core Tests

**Files:**
- Modify: `.story/tickets/T-013.json`
- Create: `skills/prompt-evals-setup/framework/evals/tests/test_report_analyst.py`
- Create later in this task: `skills/prompt-evals-setup/framework/evals/report_analyst.py`

- [ ] **Step 1: Mark T-013 in progress**

Edit `.story/tickets/T-013.json`:

```json
{
  "blockedBy": [],
  "completedDate": null,
  "createdDate": "2026-05-29",
  "description": "Surface multi-run variance + baseline delta in the run report (report-analyst lens). Cores already built.",
  "id": "T-013",
  "order": 40,
  "phase": "review-layers",
  "spec": "docs/superpowers/specs/2026-05-30-eval-live-path-integration-spec.md",
  "status": "inprogress",
  "title": "Wire variance/run_delta into prompt-evals-run report",
  "type": "task"
}
```

- [ ] **Step 2: Write the failing report-analyst tests**

Create `skills/prompt-evals-setup/framework/evals/tests/test_report_analyst.py`:

```python
import unittest

from evals.report_analyst import build_report_analysis, render_markdown


def run(avg, pass_rate, passed, cases, label="run"):
    return {
        "meta": {"run_label": label, "dataset_file": "evals/datasets/meal_plan.json"},
        "summary": {"average_score": avg, "pass_rate": pass_rate, "passed": passed},
        "results": [{"test_case": {"scenario": scenario}, "score": score} for scenario, score in cases],
    }


class TestReportAnalysis(unittest.TestCase):
    def test_baseline_delta_calls_core_and_names_movers(self):
        baseline = run(7.0, 50.0, 1, [("easy", 8), ("hard", 6)], label="base")
        current = run(8.0, 100.0, 2, [("easy", 8), ("hard", 9)], label="current")

        analysis = build_report_analysis(current, baseline=baseline, variance_runs=[])

        delta = analysis["baseline_delta"]
        self.assertTrue(delta["available"])
        self.assertEqual(delta["aggregate"]["average_score"], 1.0)
        self.assertEqual(delta["aggregate"]["pass_rate"], 50.0)
        self.assertEqual(delta["movers"]["best"]["case"], "hard")
        self.assertEqual(delta["movers"]["best"]["delta"], 3)
        self.assertEqual(delta["movers"]["worst"]["case"], "easy")
        self.assertEqual(delta["movers"]["worst"]["delta"], 0)

    def test_variance_calls_core_and_surfaces_regression_band(self):
        runs = [
            run(9.0, 100.0, 2, [("stable", 8), ("flaky", 10)], label="k00"),
            run(6.5, 50.0, 1, [("stable", 8), ("flaky", 5)], label="k01"),
            run(7.5, 50.0, 1, [("stable", 8), ("flaky", 7)], label="k02"),
        ]

        analysis = build_report_analysis(runs[-1], baseline=None, variance_runs=runs)

        variance = analysis["variance"]
        self.assertTrue(variance["available"])
        self.assertEqual(variance["aggregate"]["runs"], 3)
        self.assertEqual(variance["aggregate"]["flaky_cases"], 1)
        self.assertGreater(variance["suggested_regression_band"], 0)

    def test_absent_inputs_render_notes_not_errors(self):
        current = run(8.0, 100.0, 1, [("only", 8)], label="current")

        analysis = build_report_analysis(current, baseline=None, variance_runs=[current])
        md = render_markdown(analysis)

        self.assertFalse(analysis["baseline_delta"]["available"])
        self.assertFalse(analysis["variance"]["available"])
        self.assertIn("Baseline delta: not available", md)
        self.assertIn("Variance: not available", md)
        self.assertIn("needs >=2 runs", md)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the new test to verify it fails**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_report_analyst -v)
```

Expected: FAIL with `ModuleNotFoundError: No module named 'evals.report_analyst'`.

- [ ] **Step 4: Implement the report-analyst module**

Create `skills/prompt-evals-setup/framework/evals/report_analyst.py`:

```python
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
        if best is not None:
            lines.append(f"- Biggest improvement: {best['case']} ({best['delta']:+}).")
        if worst is not None:
            lines.append(f"- Biggest regression: {worst['case']} ({worst['delta']:+}).")
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
```

- [ ] **Step 5: Run the report-analyst tests to verify they pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_report_analyst -v)
```

Expected: PASS with `Ran 3 tests`.

- [ ] **Step 6: Commit T-013 report-analyst core**

```bash
git add .story/tickets/T-013.json \
  skills/prompt-evals-setup/framework/evals/report_analyst.py \
  skills/prompt-evals-setup/framework/evals/tests/test_report_analyst.py
git commit -m "feat: add prompt eval report analyst core"
```

---

### Task 2: Render Analysis In JSON And HTML Reports

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/evaluator/report.py`
- Modify: `skills/prompt-evals-setup/framework/evals/tests/test_report.py`

- [ ] **Step 1: Add failing report writer tests**

Append to `skills/prompt-evals-setup/framework/evals/tests/test_report.py`:

```python
class TestReportAnalysisRendering(unittest.TestCase):
    def test_write_json_includes_analysis_when_supplied(self):
        import json

        payload = results([9])
        analysis = {
            "baseline_delta": {"available": False, "note": "Baseline delta: not available -- pass --baseline-output with a prior run output.json."},
            "variance": {"available": False, "note": "Variance: not available -- needs >=2 runs of the same frozen dataset."},
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.json"
            write_json(path, payload, summarize(payload), {"run_label": "x"}, analysis=analysis)
            data = json.loads(path.read_text())

        self.assertEqual(set(data.keys()), {"meta", "summary", "results", "analysis"})
        self.assertEqual(data["analysis"], analysis)

    def test_write_html_renders_analysis_section_escaped(self):
        payload = results([8])
        analysis = {
            "baseline_delta": {"available": False, "note": "Baseline delta: not available -- <script>bad()</script>"},
            "variance": {"available": False, "note": "Variance: not available -- needs >=2 runs of the same frozen dataset."},
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.html"
            write_html(path, payload, summarize(payload), {"task_description": "t"}, analysis=analysis)
            html = path.read_text()

        self.assertIn("Report Analyst", html)
        self.assertIn("&lt;script&gt;bad()&lt;/script&gt;", html)
        self.assertNotIn("<script>bad()</script>", html)
```

- [ ] **Step 2: Run report tests to verify they fail**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_report -v)
```

Expected: FAIL with `TypeError: write_json() got an unexpected keyword argument 'analysis'`.

- [ ] **Step 3: Update report writers**

Modify `skills/prompt-evals-setup/framework/evals/evaluator/report.py`:

```python
from evals.report_analyst import render_html as render_analysis_html
```

Change `write_json` to:

```python
def write_json(
    path: str | Path,
    results: list[dict],
    summary: dict,
    meta: dict,
    *,
    analysis: dict | None = None,
) -> None:
    payload = {"meta": meta, "summary": summary, "results": results}
    if analysis is not None:
        payload["analysis"] = analysis
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
```

Change `write_html` signature and insert the analysis section immediately after the summary cards:

```python
def write_html(
    path: str | Path,
    results: list[dict],
    summary: dict,
    meta: dict,
    *,
    analysis: dict | None = None,
) -> None:
    rows = []
    for r in results:
        tc = r["test_case"]
        score = r["score"]
        criteria = "".join(f"<li>{_esc(c)}</li>" for c in tc.get("solution_criteria", []))
        assertion_block = _assertion_block(r.get("assertion_gate"))
        rows.append(
            f"""
        <tr>
          <td>{_esc(tc.get('scenario', ''))}</td>
          <td><pre>{_esc(tc.get('prompt_inputs', {}))}</pre></td>
          <td><ul>{criteria}</ul>{assertion_block}</td>
          <td><pre class="output">{_esc(r.get('output', ''))}</pre></td>
          <td style="color:{_color(score)};font-weight:700;font-size:18px;text-align:center">{score}</td>
          <td>{_esc(r.get('reasoning', ''))}</td>
        </tr>"""
        )

    analysis_section = render_analysis_html(analysis, _esc) if analysis is not None else ""
```

Add the missing helper above `write_html`:

```python
def _assertion_block(assertion_gate: dict | None) -> str:
    if not assertion_gate:
        return ""
    rows = []
    for result in assertion_gate.get("results", []):
        mark = "PASS" if result.get("passed") else "FAIL"
        rows.append(
            f"<li><strong>{mark}</strong> {_esc(result.get('text', ''))}: "
            f"{_esc(result.get('evidence', ''))}</li>"
        )
    skipped = assertion_gate.get("judge_skipped")
    skipped_text = "<p><strong>Judge skipped by assertion gate.</strong></p>" if skipped else ""
    return f"<div class=\"assertions\"><h4>Assertions</h4>{skipped_text}<ul>{''.join(rows)}</ul></div>"
```

Add CSS rules inside the existing `<style>` block:

```css
  .analysis { border: 1px solid #d0d7de; border-radius: 8px; padding: 12px 20px; margin: 0 0 24px; }
  .analysis h2 { margin: 0 0 8px; }
  .assertions { margin-top: 8px; font-size: 12px; }
  .assertions h4 { margin: 8px 0 4px; }
```

Insert `{analysis_section}` in the HTML document after `</div>` for the summary cards and before `<table>`.

- [ ] **Step 4: Update the existing JSON shape test**

In `TestWriteJson.test_roundtrip_shape`, keep the no-analysis call and assert the old keys are preserved:

```python
self.assertEqual(set(data.keys()), {"meta", "summary", "results"})
```

This assertion should remain unchanged. It proves `analysis` is opt-in for callers that have not joined T-013 yet.

- [ ] **Step 5: Run report tests to verify they pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_report -v)
```

Expected: PASS with all report tests green.

- [ ] **Step 6: Commit report rendering**

```bash
git add skills/prompt-evals-setup/framework/evals/evaluator/report.py \
  skills/prompt-evals-setup/framework/evals/tests/test_report.py
git commit -m "feat: render prompt eval report analysis"
```

---

### Task 3: Attach Report Analysis From Aggregate CLI

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/aggregate.py`
- Modify: `skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py`
- Modify: `skills/prompt-evals-run/SKILL.md`

- [ ] **Step 1: Add failing aggregate tests for explicit inputs**

Append to `skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py`:

```python
class TestAggregateReportAnalysis(unittest.TestCase):
    def test_aggregate_writes_absent_input_analysis_notes(self):
        with tempfile.TemporaryDirectory() as d:
            verdicts = Path(d) / "verdicts"
            verdicts.mkdir()
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            case = {
                "task_description": "task",
                "scenario": "case",
                "prompt_inputs": {},
                "solution_criteria": ["criterion"],
            }
            dataset.write_text(json.dumps({"provenance": {"task_description": "task"}, "cases": [case]}))
            (verdicts / "case-00.json").write_text(json.dumps({
                "test_case": case,
                "output": "answer",
                "verdict": {"strengths": [], "weaknesses": [], "reasoning": "ok", "score": 8},
            }))

            out_dir = aggregate(
                run_label="current",
                verdicts_dir=verdicts,
                dataset=dataset,
                runs_dir=str(runs_dir),
                extra_criteria=None,
                include_analysis=True,
            )
            payload = json.loads((Path(out_dir) / "output.json").read_text())

        self.assertIn("analysis", payload)
        self.assertFalse(payload["analysis"]["baseline_delta"]["available"])
        self.assertFalse(payload["analysis"]["variance"]["available"])

    def test_aggregate_accepts_baseline_and_variance_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "base.json"
            k1 = Path(d) / "k1.json"
            k2 = Path(d) / "k2.json"
            current = {
                "summary": {"average_score": 8.0, "pass_rate": 100.0, "passed": 1},
                "results": [{"test_case": {"scenario": "case"}, "score": 8}],
            }
            baseline = {
                "summary": {"average_score": 6.0, "pass_rate": 0.0, "passed": 0},
                "results": [{"test_case": {"scenario": "case"}, "score": 6}],
            }
            for path, payload in ((base, baseline), (k1, baseline), (k2, current)):
                path.write_text(json.dumps(payload))

            analysis = build_report_analysis_for_output(
                current,
                baseline_output=base,
                variance_outputs=[k1, k2],
            )

        self.assertTrue(analysis["baseline_delta"]["available"])
        self.assertTrue(analysis["variance"]["available"])
```

If `test_aggregate.py` does not already import `json`, `tempfile`, and `Path`, add:

```python
import json
import tempfile
from pathlib import Path
```

And add:

```python
from evals.aggregate import aggregate, build_report_analysis_for_output
```

- [ ] **Step 2: Run aggregate tests to verify they fail**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_aggregate -v)
```

Expected: FAIL with `ImportError` or `TypeError` for missing analysis arguments/functions.

- [ ] **Step 3: Implement aggregate analysis attachment**

Modify `skills/prompt-evals-setup/framework/evals/aggregate.py` imports:

```python
from evals.report_analyst import build_report_analysis
from evals.runs_util import load_json
```

Add this helper above `aggregate`:

```python
def build_report_analysis_for_output(
    current_output: dict,
    *,
    baseline_output: str | Path | None = None,
    variance_outputs: list[str | Path] | None = None,
) -> dict:
    baseline = load_json(baseline_output) if baseline_output else None
    variance_runs = [load_json(path) for path in (variance_outputs or [])]
    return build_report_analysis(current_output, baseline=baseline, variance_runs=variance_runs)
```

Change the `aggregate` signature:

```python
def aggregate(
    *,
    run_label: str,
    verdicts_dir: str | Path,
    dataset: str | None = None,
    runs_dir: str = config.RUNS_DIR,
    extra_criteria: str | None = None,
    baseline_output: str | Path | None = None,
    variance_outputs: list[str | Path] | None = None,
    include_analysis: bool = True,
) -> str:
```

Replace the write calls:

```python
    current_output = {"meta": meta, "summary": summary, "results": results}
    analysis = (
        build_report_analysis_for_output(
            current_output,
            baseline_output=baseline_output,
            variance_outputs=variance_outputs,
        )
        if include_analysis
        else None
    )

    out_dir = Path(runs_dir) / run_label
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "output.json", results, summary, meta, analysis=analysis)
    write_html(out_dir / "output.html", results, summary, meta, analysis=analysis)
    return str(out_dir)
```

Add parser args:

```python
    parser.add_argument(
        "--baseline-output",
        default=None,
        help="explicit baseline run output.json for report-analyst delta",
    )
    parser.add_argument(
        "--variance-output",
        action="append",
        default=[],
        help="explicit run output.json for variance; pass once per run",
    )
```

Pass `baseline_output=args.baseline_output` and `variance_outputs=args.variance_output` into the existing `aggregate(` call.

- [ ] **Step 4: Run aggregate tests to verify they pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_aggregate -v)
```

Expected: PASS.

- [ ] **Step 5: Update prompt-evals-run report procedure**

In `skills/prompt-evals-run/SKILL.md`, update the Path A aggregate command block to include optional explicit report-analyst inputs:

```bash
python3 -m evals.aggregate \
  --run-label "$RUN_LABEL" \
  --verdicts-dir "$VERDICTS_DIR" \
  --dataset evals/datasets/<name>.json \
  --baseline-output evals/runs/<baseline-label>/output.json \
  --variance-output evals/runs/<run-a>/output.json \
  --variance-output evals/runs/<run-b>/output.json
```

Add this prose immediately below the command:

```markdown
The `--baseline-output` and `--variance-output` flags are explicit. Do not infer a
"previous" or "latest" run by timestamp. If no baseline is supplied, the report
analyst section says the baseline delta is not available. If fewer than two variance
outputs are supplied, it says variance needs >=2 runs. These are advisory report
sections only; they do not change the run verdict.
```

- [ ] **Step 6: Run the targeted tests and skill linter**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_report_analyst evals.tests.test_report evals.tests.test_aggregate -v)
python3 tools/skill_lint.py --root .
```

Expected: targeted tests PASS; skill linter reports `0 errors`.

- [ ] **Step 7: Commit T-013 CLI and docs**

```bash
git add skills/prompt-evals-setup/framework/evals/aggregate.py \
  skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py \
  skills/prompt-evals-run/SKILL.md
git commit -m "feat: attach prompt eval report analysis"
```

---

### Task 4: Add Assertion Gate Core

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/assertion_gate.py`
- Create: `skills/prompt-evals-setup/framework/evals/tests/test_assertion_gate.py`

- [ ] **Step 1: Confirm T-018 sequencing before T-014**

Run:

```bash
sed -n '1,220p' docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md
sed -n '1,220p' .story/tickets/T-018.json
```

Expected: you can state one of these before coding:

```text
T-018 has landed, so T-014 targets the plugin-resident run path.
```

or:

```text
T-018 has not landed, so T-014 will be built as top-level portable orchestration under evals/ and will not edit evals/evaluator/.
```

- [ ] **Step 2: Mark T-014 in progress**

Edit `.story/tickets/T-014.json` so `"status": "inprogress"`.

- [ ] **Step 3: Write failing assertion gate tests**

Create `skills/prompt-evals-setup/framework/evals/tests/test_assertion_gate.py`:

```python
import unittest

from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict


class TestAssertionGate(unittest.TestCase):
    def test_mandatory_failure_skips_judge_by_default(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory"}],
            policy="gate_mandatory",
        )

        self.assertTrue(gate["mandatory_failed"])
        self.assertTrue(gate["judge_skipped"])
        self.assertEqual(gate["results"][0]["action"], "gate")

    def test_advisory_failure_does_not_skip_judge(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "advisory"}],
            policy="gate_mandatory",
        )

        self.assertFalse(gate["mandatory_failed"])
        self.assertFalse(gate["judge_skipped"])
        self.assertEqual(gate["results"][0]["action"], "annotate")

    def test_per_assertion_annotate_override_keeps_judge(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory", "policy": "annotate"}],
            policy="gate_mandatory",
        )

        self.assertTrue(gate["mandatory_failed"])
        self.assertFalse(gate["judge_skipped"])
        self.assertEqual(gate["results"][0]["action"], "annotate")

    def test_annotate_only_policy_keeps_judge(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory"}],
            policy="annotate_only",
        )

        self.assertTrue(gate["mandatory_failed"])
        self.assertFalse(gate["judge_skipped"])

    def test_synthetic_verdict_is_deterministic_floor(self):
        gate = evaluate_assertion_gate(
            "no calories here",
            [{"type": "contains", "value": "kcal", "severity": "mandatory"}],
            policy="gate_mandatory",
        )

        verdict = synthetic_gated_verdict(gate)

        self.assertEqual(verdict["score"], 1)
        self.assertEqual(verdict["strengths"], [])
        self.assertIn("Skipped judge", verdict["reasoning"])
        self.assertIn("missing 'kcal'", verdict["weaknesses"][0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run assertion gate tests to verify they fail**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_assertion_gate -v)
```

Expected: FAIL with `ModuleNotFoundError: No module named 'evals.assertion_gate'`.

- [ ] **Step 5: Implement assertion gate**

Create `skills/prompt-evals-setup/framework/evals/assertion_gate.py`:

```python
"""Gate/annotate policy around deterministic structural assertions."""

from __future__ import annotations

from evals.assertions import check_assertions

VALID_POLICIES = {"gate_mandatory", "annotate_only"}
VALID_ACTIONS = {"gate", "annotate"}


def _severity(spec: dict) -> str:
    value = spec.get("severity", "mandatory")
    if value not in {"mandatory", "advisory"}:
        raise ValueError(f"unknown assertion severity: {value!r}")
    return value


def _action(spec: dict, severity: str, policy: str) -> str:
    override = spec.get("policy")
    if override is not None:
        if override not in VALID_ACTIONS:
            raise ValueError(f"unknown assertion policy override: {override!r}")
        return override
    if policy == "gate_mandatory" and severity == "mandatory":
        return "gate"
    return "annotate"


def evaluate_assertion_gate(output: str, specs: list[dict], *, policy: str = "gate_mandatory") -> dict:
    if policy not in VALID_POLICIES:
        raise ValueError(f"unknown assertion policy: {policy!r}")

    raw_results = check_assertions(output, specs)
    results = []
    mandatory_failed = False
    judge_skipped = False
    for spec, raw in zip(specs, raw_results):
        severity = _severity(spec)
        action = _action(spec, severity, policy)
        passed = bool(raw["passed"])
        mandatory_failed = mandatory_failed or (severity == "mandatory" and not passed)
        judge_skipped = judge_skipped or (action == "gate" and not passed)
        results.append(
            {
                **raw,
                "severity": severity,
                "action": action,
            }
        )

    return {
        "policy": policy,
        "results": results,
        "mandatory_failed": mandatory_failed,
        "judge_skipped": judge_skipped,
    }


def synthetic_gated_verdict(gate: dict) -> dict:
    failures = [r for r in gate.get("results", []) if not r.get("passed") and r.get("action") == "gate"]
    weaknesses = [f"{r.get('text', '')}: {r.get('evidence', '')}" for r in failures]
    return {
        "strengths": [],
        "weaknesses": weaknesses,
        "reasoning": "Skipped judge because one or more mandatory structural assertions failed.",
        "score": 1,
    }
```

- [ ] **Step 6: Run assertion gate tests to verify they pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_assertion_gate -v)
```

Expected: PASS with `Ran 5 tests`.

- [ ] **Step 7: Confirm the original assertions CLI still passes**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_assertions -v)
```

Expected: PASS. This confirms `evals/assertions.py` behavior and CLI-facing core stayed unchanged.

- [ ] **Step 8: Commit assertion gate core**

```bash
git add .story/tickets/T-014.json \
  skills/prompt-evals-setup/framework/evals/assertion_gate.py \
  skills/prompt-evals-setup/framework/evals/tests/test_assertion_gate.py
git commit -m "feat: add prompt eval assertion gate"
```

---

### Task 5: Add Live Run Orchestration Without Editing Evaluator Core

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/live_run.py`
- Create: `skills/prompt-evals-setup/framework/evals/tests/test_live_run.py`

- [ ] **Step 1: Write failing live-run tests**

Create `skills/prompt-evals-setup/framework/evals/tests/test_live_run.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from evals.examples.fake_client import FakeLLMClient
from evals.live_run import run_evaluation


def write_dataset(path):
    payload = {
        "provenance": {"task_description": "Write a meal plan."},
        "cases": [
            {
                "task_description": "Write a meal plan.",
                "scenario": "missing mandatory output",
                "prompt_inputs": {"goal": "bulk"},
                "solution_criteria": ["Includes calories."],
            }
        ],
    }
    path.write_text(json.dumps(payload))


class CountingJudge(FakeLLMClient):
    def __init__(self, *, fixed_score=8):
        super().__init__(fixed_score=fixed_score)
        self.grade_calls = 0

    def complete_json(self, **kwargs):
        if kwargs.get("tag") == "grade":
            self.grade_calls += 1
        return super().complete_json(**kwargs)


class TestLiveRunAssertions(unittest.TestCase):
    def test_mandatory_assertion_failure_skips_judge_and_persists_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            runs_dir = Path(d) / "runs"
            write_dataset(dataset)
            judge = CountingJudge()

            result = run_evaluation(
                judge_client=judge,
                run_function=lambda inputs: "plain answer",
                dataset_file=str(dataset),
                assertions=[{"type": "contains", "value": "kcal", "severity": "mandatory"}],
                assertion_policy="gate_mandatory",
                runs_dir=str(runs_dir),
                run_label="assertion-gated",
            )

            self.assertEqual(judge.grade_calls, 0)
            self.assertEqual(result["summary"]["passed"], 0)
            case = result["results"][0]
            self.assertEqual(case["score"], 1)
            self.assertTrue(case["assertion_gate"]["judge_skipped"])
            output = json.loads((runs_dir / "assertion-gated" / "output.json").read_text())
            self.assertTrue(output["results"][0]["assertion_gate"]["judge_skipped"])

    def test_advisory_assertion_failure_still_calls_judge(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            write_dataset(dataset)
            judge = CountingJudge(fixed_score=8)

            result = run_evaluation(
                judge_client=judge,
                run_function=lambda inputs: "plain answer",
                dataset_file=str(dataset),
                assertions=[{"type": "contains", "value": "kcal", "severity": "advisory"}],
                assertion_policy="gate_mandatory",
                runs_dir=str(Path(d) / "runs"),
                run_label="assertion-annotated",
            )

            self.assertEqual(judge.grade_calls, 1)
            self.assertEqual(result["results"][0]["score"], 8)
            self.assertFalse(result["results"][0]["assertion_gate"]["judge_skipped"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run live-run tests to verify they fail**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_live_run -v)
```

Expected: FAIL with `ModuleNotFoundError: No module named 'evals.live_run'`.

- [ ] **Step 3: Implement top-level live run orchestration**

Create `skills/prompt-evals-setup/framework/evals/live_run.py`:

```python
"""Live eval run orchestration composed around the evaluator core."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from evals import config
from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict
from evals.evaluator.grade import grade
from evals.evaluator.report import summarize, write_html, write_json
from evals.evaluator.run import RunFunction, execute
from evals.report_analyst import build_report_analysis


def _map_ordered(fn: Callable[[dict], dict], items: list[dict], *, max_workers: int) -> list[dict]:
    results: list[dict | None] = [None] * len(items)
    lock = threading.Lock()

    def wrapped(index_item):
        index, item = index_item
        value = fn(item)
        with lock:
            results[index] = value

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(wrapped, enumerate(items)))
    return [r for r in results if r is not None]


def _assertions_for_case(global_assertions: list[dict], case: dict) -> list[dict]:
    return [*global_assertions, *case.get("assertions", [])]


def run_evaluation(
    *,
    judge_client,
    run_function: RunFunction,
    dataset_file: str,
    extra_criteria: str | None = None,
    process_criteria: str | None = None,
    assertions: list[dict] | None = None,
    assertion_policy: str = "gate_mandatory",
    runs_dir: str = config.RUNS_DIR,
    run_label: str | None = None,
    max_concurrent_tasks: int = config.MAX_CONCURRENT_TASKS,
    baseline: dict | None = None,
    variance_runs: list[dict] | None = None,
) -> dict:
    dataset = json.loads(Path(dataset_file).read_text(encoding="utf-8"))
    cases = dataset["cases"]
    assertion_specs = assertions or []

    def work(case: dict) -> dict:
        trajectory = execute(run_function, case["prompt_inputs"])
        gate = evaluate_assertion_gate(
            trajectory.final_output,
            _assertions_for_case(assertion_specs, case),
            policy=assertion_policy,
        )
        if gate["judge_skipped"]:
            verdict = synthetic_gated_verdict(gate)
        else:
            verdict = grade(
                judge_client,
                case,
                trajectory,
                extra_criteria=extra_criteria,
                process_criteria=process_criteria,
            )
        return {
            "output": trajectory.final_output,
            "trajectory": trajectory.to_dict(),
            "test_case": case,
            "score": verdict["score"],
            "reasoning": verdict.get("reasoning", ""),
            "verdict": verdict,
            "assertion_gate": gate,
        }

    results = _map_ordered(work, cases, max_workers=max_concurrent_tasks)
    summary = summarize(results)
    label = run_label or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(runs_dir) / label
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "task_description": dataset.get("provenance", {}).get("task_description", ""),
        "dataset_file": dataset_file,
        "judge_model": getattr(judge_client, "model", "unknown"),
        "run_label": label,
        "extra_criteria": extra_criteria,
        "assertion_policy": assertion_policy,
    }
    current_output = {"meta": meta, "summary": summary, "results": results}
    analysis = build_report_analysis(
        current_output,
        baseline=baseline,
        variance_runs=variance_runs or [],
    )
    write_json(out_dir / "output.json", results, summary, meta, analysis=analysis)
    write_html(out_dir / "output.html", results, summary, meta, analysis=analysis)
    return {"summary": summary, "run_dir": str(out_dir), "results": results, "analysis": analysis}
```

- [ ] **Step 4: Run live-run tests to verify they pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_live_run -v)
```

Expected: PASS with `Ran 2 tests`.

- [ ] **Step 5: Verify evaluator core was not edited**

Run:

```bash
git diff -- skills/prompt-evals-setup/framework/evals/evaluator
```

Expected: only the intended `report.py` changes from Task 2 appear; no changes to `evaluator/evaluator.py`, `evaluator/grade.py`, `evaluator/run.py`, or `evaluator/prompts.py`.

- [ ] **Step 6: Commit live run orchestration**

```bash
git add skills/prompt-evals-setup/framework/evals/live_run.py \
  skills/prompt-evals-setup/framework/evals/tests/test_live_run.py
git commit -m "feat: run prompt eval assertions before judging"
```

---

### Task 6: Wire Keyed Evaluate And Path A Skill Instructions

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/run_eval.py`
- Modify: `skills/prompt-evals-run/SKILL.md`
- Modify: `skills/prompt-evals-setup/framework/evals/examples/smoke_test.py`

- [ ] **Step 1: Add run_eval assertion config**

In `skills/prompt-evals-setup/framework/evals/run_eval.py`, add below `EXTRA_CRITERIA`:

```python
ASSERTIONS = [
    {"type": "contains", "value": "kcal", "severity": "advisory"},
    {"type": "regex", "pattern": r"\bProtein\b|\bprotein\b", "severity": "advisory"},
]
ASSERTION_POLICY = "gate_mandatory"
```

These bundled defaults are advisory so the smoke example still exercises judge grading. Project users can change severities to `mandatory` for hard gates.

- [ ] **Step 2: Wire keyed evaluate through live_run**

In `run_eval.py`, add:

```python
from evals.live_run import run_evaluation as run_live_evaluation
```

Replace the keyed `build_evaluator().run_evaluation` call with:

```python
        run_live_evaluation(
            judge_client=AnthropicClient(config.JUDGE_MODEL),
            run_function=run_prompt,
            dataset_file=DATASET_FILE,
            extra_criteria=EXTRA_CRITERIA,
            process_criteria=PROCESS_CRITERIA,
            assertions=ASSERTIONS,
            assertion_policy=ASSERTION_POLICY,
            run_label=run_label,
        )
```

- [ ] **Step 3: Update smoke test to assert assertion evidence exists**

In `skills/prompt-evals-setup/framework/evals/examples/smoke_test.py`, after the artifact checks are built, add:

```python
            "assertion evidence recorded": all(
                "assertion_gate" in row for row in result["results"]
            ),
```

- [ ] **Step 4: Update Path A in prompt-evals-run**

In `skills/prompt-evals-run/SKILL.md`, change Path A step 2 so the order for each case is:

```markdown
1. Render the prompt deterministically.
2. Dispatch the execute-subagent and capture only the raw output.
3. Run configured structural assertions from `evals.run_eval.ASSERTIONS` using the
   same `ASSERTION_POLICY` that keyed mode uses.
4. If the assertion gate says `judge_skipped: true`, write a verdict JSON with the
   synthetic score `1`, the assertion evidence, and no grade-subagent dispatch.
5. Otherwise dispatch the grade-subagent and include the assertion evidence beside
   the judge verdict.
```

Add this Python helper command block for Path A:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from evals import run_eval
from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict

output_path = Path("evals/runs/_outputs/$RUN_LABEL/case-<i:02d>.txt")
gate = evaluate_assertion_gate(
    output_path.read_text(encoding="utf-8"),
    run_eval.ASSERTIONS,
    policy=run_eval.ASSERTION_POLICY,
)
print(json.dumps({
    "gate": gate,
    "synthetic_verdict": synthetic_gated_verdict(gate) if gate["judge_skipped"] else None,
}, indent=2))
PY
```

Document that the skill writes `assertion_gate` into each verdict JSON:

```json
{
  "test_case": {
    "task_description": "Write a compact 1-day meal plan for one athlete.",
    "scenario": "A cyclist maintaining weight",
    "prompt_inputs": {"goal": "maintain weight"},
    "solution_criteria": ["Includes calories and macros."]
  },
  "output": "raw output",
  "assertion_gate": { "policy": "gate_mandatory", "results": [], "mandatory_failed": false, "judge_skipped": false },
  "verdict": { "strengths": [], "weaknesses": [], "reasoning": "ok", "score": 8 }
}
```

- [ ] **Step 5: Teach aggregate to preserve assertion evidence from Path A verdicts**

Modify `skills/prompt-evals-setup/framework/evals/aggregate.py` inside `load_results` so the appended result includes assertion evidence:

```python
                "assertion_gate": record.get("assertion_gate"),
```

Place it beside `"verdict": verdict`.

- [ ] **Step 6: Add aggregate test for assertion evidence preservation**

In `skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py`, add:

```python
class TestAggregateAssertionEvidence(unittest.TestCase):
    def test_load_results_preserves_assertion_gate(self):
        with tempfile.TemporaryDirectory() as d:
            verdicts = Path(d)
            case = {
                "task_description": "task",
                "scenario": "case",
                "prompt_inputs": {},
                "solution_criteria": ["criterion"],
            }
            gate = {
                "policy": "gate_mandatory",
                "results": [{"text": "contains 'kcal'", "passed": False, "evidence": "missing 'kcal'", "severity": "mandatory", "action": "gate"}],
                "mandatory_failed": True,
                "judge_skipped": True,
            }
            (verdicts / "case-00.json").write_text(json.dumps({
                "test_case": case,
                "output": "answer",
                "assertion_gate": gate,
                "verdict": {"strengths": [], "weaknesses": ["missing"], "reasoning": "Skipped judge.", "score": 1},
            }))

            loaded = load_results(verdicts)

        self.assertEqual(loaded[0]["assertion_gate"], gate)
```

Add `load_results` to the aggregate imports in the test file if needed.

- [ ] **Step 7: Run assertion/live/aggregate/smoke checks**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_assertion_gate evals.tests.test_live_run evals.tests.test_aggregate -v)
(cd skills/prompt-evals-setup/framework && python3 -m evals.examples.smoke_test)
```

Expected: unit tests PASS; smoke prints `SMOKE TEST: PASS`.

- [ ] **Step 8: Commit T-014 wiring**

```bash
git add skills/prompt-evals-setup/framework/evals/run_eval.py \
  skills/prompt-evals-setup/framework/evals/aggregate.py \
  skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py \
  skills/prompt-evals-setup/framework/evals/examples/smoke_test.py \
  skills/prompt-evals-run/SKILL.md
git commit -m "feat: wire assertion gate into prompt eval runs"
```

---

### Task 7: Add K-Run Variance Runner

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/variance_runner.py`
- Create: `skills/prompt-evals-setup/framework/evals/tests/test_variance_runner.py`

- [ ] **Step 1: Mark T-019 in progress**

Edit `.story/tickets/T-019.json` so `"status": "inprogress"`.

- [ ] **Step 2: Write failing variance-runner tests**

Create `skills/prompt-evals-setup/framework/evals/tests/test_variance_runner.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from evals.variance_runner import output_paths_for_labels, run_k_variance, variance_labels


class TestVarianceLabels(unittest.TestCase):
    def test_labels_are_explicit_group_plus_ordinal(self):
        self.assertEqual(
            variance_labels("meal-plan-variance", 3),
            ["meal-plan-variance__k00", "meal-plan-variance__k01", "meal-plan-variance__k02"],
        )

    def test_k_must_be_at_least_two(self):
        with self.assertRaises(ValueError):
            variance_labels("group", 1)


class TestRunKVariance(unittest.TestCase):
    def test_runs_k_times_and_computes_variance(self):
        with tempfile.TemporaryDirectory() as d:
            runs_dir = Path(d) / "runs"
            scores = [8, 6, 10]
            calls = []

            def run_once(label):
                calls.append(label)
                run_dir = runs_dir / label
                run_dir.mkdir(parents=True)
                payload = {
                    "summary": {"average_score": float(scores[len(calls) - 1])},
                    "results": [{"test_case": {"scenario": "case"}, "score": scores[len(calls) - 1]}],
                }
                (run_dir / "output.json").write_text(json.dumps(payload))
                return {"run_dir": str(run_dir)}

            result = run_k_variance(
                group_label="meal-plan-variance",
                k=3,
                runs_dir=str(runs_dir),
                run_once=run_once,
            )

        self.assertEqual(calls, ["meal-plan-variance__k00", "meal-plan-variance__k01", "meal-plan-variance__k02"])
        self.assertEqual(result["aggregate"]["runs"], 3)
        self.assertGreater(result["suggested_regression_band"], 0)

    def test_output_paths_are_enumerated_without_guessing(self):
        paths = output_paths_for_labels("evals/runs", ["g__k00", "g__k01"])
        self.assertEqual(paths, [Path("evals/runs/g__k00/output.json"), Path("evals/runs/g__k01/output.json")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run variance-runner tests to verify they fail**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_variance_runner -v)
```

Expected: FAIL with `ModuleNotFoundError: No module named 'evals.variance_runner'`.

- [ ] **Step 4: Implement variance runner**

Create `skills/prompt-evals-setup/framework/evals/variance_runner.py`:

```python
"""Explicit K-run orchestration for live eval variance."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from evals.runs_util import load_json
from evals.variance import compute_variance


def variance_labels(group_label: str, k: int) -> list[str]:
    if k < 2:
        raise ValueError("K-run variance requires k >= 2")
    if not group_label or "/" in group_label or "\\" in group_label:
        raise ValueError("group_label must be a non-empty run label, not a path")
    return [f"{group_label}__k{ordinal:02d}" for ordinal in range(k)]


def output_paths_for_labels(runs_dir: str | Path, labels: list[str]) -> list[Path]:
    base = Path(runs_dir)
    return [base / label / "output.json" for label in labels]


def run_k_variance(
    *,
    group_label: str,
    k: int,
    runs_dir: str | Path,
    run_once: Callable[[str], dict],
) -> dict:
    labels = variance_labels(group_label, k)
    for label in labels:
        run_once(label)
    outputs = output_paths_for_labels(runs_dir, labels)
    return compute_variance([load_json(path) for path in outputs])
```

- [ ] **Step 5: Run variance-runner tests to verify they pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_variance_runner -v)
```

Expected: PASS with `Ran 4 tests`.

- [ ] **Step 6: Confirm the original variance CLI tests still pass**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_variance -v)
```

Expected: PASS. This confirms `evals/variance.py` remains the offline core.

- [ ] **Step 7: Commit variance runner core**

```bash
git add .story/tickets/T-019.json \
  skills/prompt-evals-setup/framework/evals/variance_runner.py \
  skills/prompt-evals-setup/framework/evals/tests/test_variance_runner.py
git commit -m "feat: add prompt eval k-run variance runner"
```

---

### Task 8: Wire K-Run Command And Skill Cost Disclosure

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/run_eval.py`
- Modify: `skills/prompt-evals-run/SKILL.md`

- [ ] **Step 1: Add evaluate-variance command to run_eval.py**

Modify the usage docstring in `run_eval.py`:

```python
    python -m evals.run_eval generate                         # build + freeze the dataset (one-time)
    python -m evals.run_eval evaluate [run_label]             # keyed-mode only; see EXECUTION_MODE
    python -m evals.run_eval evaluate-variance <group> <k>    # keyed-mode K-run variance
```

Add this import:

```python
from evals.variance_runner import run_k_variance
```

Add this branch in `main(argv)` before the unknown-command branch:

```python
    if command == "evaluate-variance":
        if config.EXECUTION_MODE != "anthropic_api":
            print(_IN_CC_GUIDANCE)
            return 3
        if len(argv) != 4:
            print("usage: python -m evals.run_eval evaluate-variance <group_label> <k>")
            return 2
        group_label = argv[2]
        k = int(argv[3])

        def run_once(label: str) -> dict:
            return run_live_evaluation(
                judge_client=AnthropicClient(config.JUDGE_MODEL),
                run_function=run_prompt,
                dataset_file=DATASET_FILE,
                extra_criteria=EXTRA_CRITERIA,
                process_criteria=PROCESS_CRITERIA,
                assertions=ASSERTIONS,
                assertion_policy=ASSERTION_POLICY,
                run_label=label,
            )

        variance = run_k_variance(
            group_label=group_label,
            k=k,
            runs_dir=config.RUNS_DIR,
            run_once=run_once,
        )
        print(json.dumps(variance, indent=2))
        return 0
```

Add `import json` at the top of `run_eval.py`.

- [ ] **Step 2: Document K-run Path B usage**

In `skills/prompt-evals-run/SKILL.md`, add to Path B after the normal `evaluate` command:

```bash
python3 -m evals.run_eval evaluate-variance <group_label> <k>
```

Add this cost disclosure:

```markdown
K-run variance multiplies cost by `K x (run + grade) x num_cases`. State that budget
to the user before launching. The labels are deterministic and explicit:
`<group_label>__k00`, `<group_label>__k01`, and so on. Use the resulting
`output.json` files as `--variance-output` inputs to the report analyst section.
```

- [ ] **Step 3: Document K-run Path A usage**

In Path A, add:

```markdown
For no-key K-run variance, repeat the Path A case loop once per explicit label
generated from `<group_label>__kNN`. Do not derive labels from wall-clock time. After
the K runs exist, pass each `evals/runs/<group_label>__kNN/output.json` to
`python3 -m evals.aggregate` using repeated `--variance-output` flags.
```

- [ ] **Step 4: Run targeted K-run tests and linter**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_variance_runner evals.tests.test_variance -v)
python3 tools/skill_lint.py --root .
```

Expected: tests PASS; skill linter reports `0 errors`.

- [ ] **Step 5: Commit K-run command and docs**

```bash
git add skills/prompt-evals-setup/framework/evals/run_eval.py \
  skills/prompt-evals-run/SKILL.md
git commit -m "feat: document and expose k-run prompt eval variance"
```

---

### Task 9: Cross-Spec Updates And Ticket Closure

**Files:**
- Modify: `docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`
- Modify: `.story/tickets/T-013.json`
- Modify: `.story/tickets/T-014.json`
- Modify: `.story/tickets/T-019.json`

- [ ] **Step 1: Update the framework spec live-path note**

Find the section 13 live-path note in `docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md` and update it to this wording:

```markdown
Live-path wiring for the shipped deterministic cores is covered by
`docs/superpowers/specs/2026-05-30-eval-live-path-integration-spec.md`.
Implemented wiring composes top-level orchestration around the evaluator core:
report analysis calls `run_delta.py` and `variance.py`; assertion gating calls
`assertions.py` before judge grading; K-run orchestration writes explicit run labels
and then calls `variance.py`.
```

- [ ] **Step 2: Mark tickets complete after verification passes**

After Task 10 passes, edit `.story/tickets/T-013.json`, `.story/tickets/T-014.json`, and `.story/tickets/T-019.json` so each has:

```json
"status": "complete",
"completedDate": "2026-05-30"
```

- [ ] **Step 3: Commit docs and tickets**

```bash
git add docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md \
  .story/tickets/T-013.json \
  .story/tickets/T-014.json \
  .story/tickets/T-019.json
git commit -m "docs: record eval live-path integration"
```

---

### Task 10: Full Verification, Reviews, Handover, And Plan Cleanup

**Files:**
- Create: `.story/handovers/<generated-by-storybloq>.md` via Story handover tooling
- Optional create: `.story/lessons/<generated-by-storybloq>.json` only if a reusable lesson emerges
- Delete after merge: `docs/superpowers/plans/2026-05-30-t013-t014-t019-eval-live-path-integration.md`

- [ ] **Step 1: Run the full offline test suite**

Run:

```bash
python3 tools/skill_lint.py --root .
python3 -m unittest discover -s tools/tests -t tools
(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)
python3 -m unittest discover -s skills/workflow-design-validate/scripts/tests -t skills/workflow-design-validate/scripts
```

Expected:

```text
skill_lint.py: 0 errors
tools/tests: OK
evals/tests: OK
workflow-design-validate tests: OK
```

- [ ] **Step 2: Run the offline smoke test**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m evals.examples.smoke_test)
```

Expected: output ends with:

```text
SMOKE TEST: PASS
```

- [ ] **Step 3: Confirm prohibited paths were not changed**

Run:

```bash
git diff -- skills/prompt-evals-setup/framework/evals/evaluator/evaluator.py \
  skills/prompt-evals-setup/framework/evals/evaluator/grade.py \
  skills/prompt-evals-setup/framework/evals/evaluator/run.py \
  skills/prompt-evals-setup/framework/evals/prompts
```

Expected: no diff. `evaluator/report.py` is allowed because report rendering is the T-013/T-014 surface.

- [ ] **Step 4: Run two independent review rounds**

Use the Story review-lenses workflow for the plan/code diff. The review context is:

```text
Review stage: CODE_REVIEW
Tickets: T-013, T-014, T-019
Spec: docs/superpowers/specs/2026-05-30-eval-live-path-integration-spec.md
Key risks: accidental evaluator-core changes, reimplemented variance/delta math, hidden latest-run discovery, assertion gate skipping judge for advisory failures, K-run labels derived from time.
```

Address all blocking findings, then run the full verification commands again.

- [ ] **Step 5: Create a Story handover**

Before handover, run a snapshot:

```bash
storybloq snapshot
```

Then create a handover that records:

```markdown
# Eval live-path integration

## Summary

Implemented T-013, T-014, and T-019 from
docs/superpowers/specs/2026-05-30-eval-live-path-integration-spec.md.

## Key changes

- Report analyst section renders explicit baseline deltas and variance.
- Assertion gate runs before judge grading and persists deterministic evidence.
- K-run variance uses explicit labels <group_label>__kNN and reuses evals.variance.

## Verification

- Include the exact command output from Task 10 steps 1-3.

## Plan cleanup

Implementation plan:
docs/superpowers/plans/2026-05-30-t013-t014-t019-eval-live-path-integration.md
Delete this plan after the change is merged to the default branch.
```

- [ ] **Step 6: Delete the plan after merge**

Only after the ticket changes are merged to the default branch, run:

```bash
git rm docs/superpowers/plans/2026-05-30-t013-t014-t019-eval-live-path-integration.md
git commit -m "chore: remove completed eval live-path plan"
```

This follows `AGENTS.md`: plans are ephemeral; handovers are the narrative of record.

---

## Self-Review

- Spec coverage: T-013 is covered by Tasks 1-3; T-014 is covered by Tasks 4-6; T-019 is covered by Tasks 7-8; cross-spec and verification requirements are covered by Tasks 9-10.
- Placeholder scan: no task asks the implementer to invent missing behavior. The assertion policy, score floor, label scheme, command flags, file names, and test commands are specified.
- Type consistency: report analysis keys are consistently `baseline_delta` and `variance`; assertion evidence is consistently `assertion_gate`; K-run functions consistently use `group_label`, `k`, and `runs_dir`.
