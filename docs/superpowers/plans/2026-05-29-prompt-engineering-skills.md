# Prompt-Engineering Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `prompt-engineering-*` skill group — `prompt-engineering-author` (write/refactor a single-shot prompt against best practices, eval-free) and `prompt-engineering-improve` (drive a deterministic, eval-driven iterate→measure→diagnose→rewrite loop) — on top of the existing `prompt-evals-*` measurement substrate.

**Architecture:** Two authored Markdown skills with progressive-disclosure `references/`. `prompt-engineering-author` is standalone and never touches `./evals`. `prompt-engineering-improve` orchestrates the eval framework and owns one deterministic helper, `improve_step.py` (delta / best-version / stop-verdict / diagnosis tally / `EXTRA_CRITERIA`-hash freeze-guard), built TDD-first with offline `unittest` fixtures mirroring `workflow-design-validate`. The loop's numeric decisions are code; the model only names the dominant failure theme and rewrites. This subsystem DEPENDS ON subsystem 1's execution substrate (`config.EXECUTION_MODE`, `evals/aggregate.py`, the prompt-prep glue, the `prompt-evals-run` run-procedure rewrite) and only edits the vendored `evals/` top level (`run_eval.py` loop-param constants) + the skill files; the framework core is unchanged.

**Tech Stack:** Python 3.10+ stdlib (`unittest`, `argparse`, `json`, `hashlib`, `dataclasses`), no third-party deps; Markdown skills with YAML frontmatter; `${CLAUDE_PLUGIN_ROOT}` references.

**Specs:** [docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md](../specs/2026-05-29-prompt-engineering-skills-design.md) (this subsystem) and [docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md](../specs/2026-05-29-agent-build-and-execution-spec.md) (the substrate this consumes). Tasks reference them by section (§).

---

## Shared interface contract (DO NOT invent variants)

These EXACT names/signatures are owned by the three composing plans. This plan
(subsystem 2) **consumes** the substrate (owned by subsystem 1) and **owns**
`improve_step.py`, the `run_eval.py` loop-param constants block, the two
`prompt-engineering-*` skills, and the `prompt-evals-run/SKILL.md` §4 re-scope.

- Framework is vendored at `skills/prompt-evals-setup/framework/evals/` and copied to `./evals` by `prompt-evals-setup`. We edit the SOURCE under `skills/prompt-evals-setup/framework/evals/`.
- `config.py`: `EXECUTION_MODE: str = "in_claude_code"` (other value `"anthropic_api"`) is **owned by the substrate plan** — this plan does NOT edit `config.py`; it only references `config.PASS_THRESHOLD` and (in prose) `config.EXECUTION_MODE`.
- `evals/aggregate.py` (NEW, vendored top level beside `run_eval.py`) is **owned by the substrate plan**: deterministic, no model calls. CLI `python -m evals.aggregate --run-label <label> --verdicts-dir <dir> --dataset <path>`. Reads per-case verdict JSON files, validates each via `from evals.evaluator.schemas import validate_verdict`, writes `evals/runs/<label>/{output.json,output.html}` via `from evals.evaluator.report import summarize, write_json, write_html`. This plan only CALLS it from `prompt-engineering-improve`/`prompt-evals-run` prose and flags the dependency.
- prompt-prep glue `check_placeholders(template: str, prompt_inputs: dict) -> dict` returning `{"declared":[...],"unused":[...],"missing":[...]}`, RAISES on missing, WARNS on unused, never auto-syncs — lives in vendored `evals/` (`run_eval.py` or `evals/promptprep.py` beside it), **owned by the substrate plan**. Reuses `from evals.evaluator.templates import render`. This plan references it; it does NOT define it.
- `skills/prompt-engineering-improve/scripts/improve_step.py` (NEW, **this plan owns it**): deterministic CLI. Reads a round's `evals/runs/<label>/output.json` + a loop-state JSON; emits per-round delta, running best version id (argmax), a `continue|stop:<rule>` verdict (rules: `threshold`/`pass_rate`/`diminishing-returns-K`/`regression_band`/`max_rounds`), a diagnosis tally (count of cases with `score<=3` = mandatory-fail per `grading.md`; %-of-cases per weakness theme), an `EXTRA_CRITERIA` hash freeze-guard, and writes `delta.json`. Offline `unittest` fixtures.
- Loop params live as a constants block at the **top of `run_eval.py`** (NOT `config.py`): `pass_rate_target=0.80`, `max_rounds=3`, `epsilon=0.25`, `diminishing_return_rounds=2`, `regression_band=0.5`; `pass_threshold` references `config.PASS_THRESHOLD` (7). **This plan owns this constants block.**
- `run_label` convention: `improve-<name>-round-NN`. `run_evaluation` already accepts `run_label` (`evaluator.py:83`) and returns `run_dir` (`evaluator.py:125`). `run_eval.py` `main()` must be MODE-AWARE (under `in_claude_code`, `evaluate` prints guidance + exits non-zero; keyed `run_evaluation` runs only under `anthropic_api`, threading `run_label`). **The mode-aware `main()` rewrite is owned by the substrate plan; this plan only adds the loop-param constants block and the `run_label` arg.** Flag the merge.
- COMPOSITION INVARIANT: framework CORE unchanged — `evaluator/{evaluator,generate,grade,run,schemas,jsonio,templates,report,client}.py` and `prompts/`. New/changed code only at the vendored `evals/` top level + the SKILL.md files.
- Subagent dispatch is the interactive Claude's job (Agent/Task tool, session auth, no key) — Python CANNOT dispatch a subagent. The no-key eval path is SKILL-ORCHESTRATED prose in `prompt-evals-run/SKILL.md`, not Python. Subagents can't nest; no-key eval is single-shot only.

---

## Verified source facts (cite these; do not re-derive)

- `evals/evaluator/templates.py` — `render(template: str, /, **values) -> str`: `{name}` substitution, `{{`/`}}` literal-brace escaping, **raises `KeyError`** on a missing placeholder, ignores extra values. Template is **positional-only**; values are keyword args.
- `evals/evaluator/schemas.py` — `validate_verdict(verdict: dict) -> dict` clamps `score` to int 1–10 and defaults `reasoning`/`strengths`/`weaknesses`; `verdict_schema()` requires `{strengths, weaknesses, reasoning, score}`.
- `evals/evaluator/report.py` — `summarize(results: list[dict]) -> dict` returns `{total, average_score, passed, pass_rate}`; a "pass" is `score >= config.PASS_THRESHOLD`. `write_json(path, results, summary, meta)` writes `{meta, summary, results}`. `write_html(path, results, summary, meta)`. Each `result` carries `{output, test_case, score, reasoning, verdict, ...}`; `test_case` carries `{scenario?, prompt_inputs, solution_criteria, task_description}` (generate.py:70 stamps `task_description`).
- `evals/evaluator/evaluator.py` — `run_evaluation(..., run_label: str | None = None) -> {"summary", "run_dir", "results"}`; writes `evals/runs/<run_label or timestamp>/output.{json,html}`.
- `evals/prompts/grading.md` — "Any violation of a MANDATORY criterion forces a score of 3 or below." → **mandatory-fail = `score <= 3`**.
- `evals/config.py` — `PASS_THRESHOLD = 7`, `RUNS_DIR = "evals/runs"`, `DATASETS_DIR = "evals/datasets"`. `GRADING_TEMPERATURE = 0.0` is IGNORED by the Opus judge (no sampling params), so re-grades are NOT bit-identical → `regression_band = 0.5`.
- `output.json` shape (the file `improve_step.py` reads): top-level `{meta, summary, results}`. `summary.average_score` (float), `summary.pass_rate` (float %), `summary.total` (int). Each `results[i]` = `{output, test_case, score, reasoning, verdict:{strengths,weaknesses,reasoning,score}}`.
- **Tests are run from the scripts dir** via `python3 -m unittest discover -s tests` so test files import the module by bare name (`from improve_step import ...`), exactly like `skills/workflow-design-validate/scripts/tests/`. `python` is NOT on PATH in this env — always use `python3`.

---

## File Structure (created/modified files + responsibilities)

```
skills/prompt-engineering-author/
  SKILL.md                                  # Task 14 — ToC + progressive disclosure; modes A/B; allowed-tools Read,Write,Edit,Glob
  references/
    techniques.md                           # Task 11 — the escalation ladder (8 rungs)
    anti-patterns.md                         # Task 12 — what-to-do / no over-prompting / north star
    rewrite-procedure.md                     # Task 13 — SHARED seam (author Mode B + improve read it)

skills/prompt-engineering-improve/
  SKILL.md                                  # Task 15 — loop ToC; preconditions; hybrid control; allowed-tools Bash,Read,Write,Edit,Glob
  references/
    diagnosis.md                            # Task 10 — SHARED (cited by prompt-evals-run); theme→rung map + priority + criteria-vs-prompt guard
  scripts/
    improve_step.py                         # Tasks 2–8 — the deterministic CLI
    requirements.txt                        # Task 1 — stdlib only (empty/comment); mirrors validate exemplar
    tests/
      __init__.py                           # Task 1
      fixtures/                             # Tasks 2–8 — fixture output.json / loop-state JSON
      test_load.py                          # Task 2 — load_output_json / load_loop_state / errors
      test_delta_best.py                    # Task 3 — per-round delta + running best (argmax)
      test_stop_verdict.py                  # Tasks 4,6 — threshold/pass_rate/diminishing-K/regression_band/max_rounds
      test_tally.py                         # Task 5 — mandatory-fail count + %-per-theme
      test_freeze_guard.py                  # Task 7 — EXTRA_CRITERIA hash freeze
      test_cli.py                           # Task 8 — argparse + delta.json write + exit codes
      test_final_report.py                  # Task 9 — finalize → final-report.json

# MODIFIED (this plan):
skills/prompt-evals-setup/framework/evals/run_eval.py   # Task 16 — ADD loop-param constants block + run_label arg to main()
skills/prompt-evals-run/SKILL.md                        # Task 17 — RE-SCOPE §4 to single-pass + cite diagnosis.md (MERGE w/ substrate plan)
README.md                                               # Task 18 — wire prompt-engineering-* group row
.claude-plugin/plugin.json                              # Task 18 — keywords/description (coordinate w/ substrate plan)
```

**Merge flags (cross-plan):**
- `run_eval.py` — substrate plan rewrites `run_prompt`/`main()` mode-awareness + prompt-prep glue; THIS plan only adds the loop-param constants block + the `run_label` arg threading. Land both edits in one coherent file (Task 16 notes the exact insertion points and assumes the substrate edits may already be present).
- `prompt-evals-run/SKILL.md` — substrate plan rewrites the run procedure (Path A subagent dispatch); THIS plan re-scopes §4 "Diagnose and iterate" to single-pass + adds the `diagnosis.md` citation (Task 17). One merged file.
- `README.md` / `plugin.json` — substrate plan rewrites them into the unified lifecycle; THIS plan adds the `prompt-engineering-*` group row/keywords (Task 18). Coordinate; do not leave islands.

---

## Tasks

### Task 1 — Scaffold `prompt-engineering-improve/scripts/` skeleton + test harness

- [ ] Create the scripts dir and an empty `requirements.txt` (stdlib only; mirrors the validate exemplar which lists only its one dep — here there are none, so a comment line):

  Write `skills/prompt-engineering-improve/scripts/requirements.txt`:
  ```
  # improve_step.py uses only the Python 3.10+ standard library (no third-party deps).
  ```

- [ ] Create the tests package init. Write `skills/prompt-engineering-improve/scripts/tests/__init__.py` as an empty file (0 bytes).

- [ ] Create the fixtures dir with a `.gitkeep` so the empty dir is tracked. Write `skills/prompt-engineering-improve/scripts/tests/fixtures/.gitkeep` as an empty file.

- [ ] Create a minimal `improve_step.py` so the first test can import it. Write `skills/prompt-engineering-improve/scripts/improve_step.py`:
  ```python
  """Deterministic loop logic for prompt-engineering-improve.

  Reads a round's evals/runs/<label>/output.json + a loop-state JSON and emits the
  per-round delta, the running best version id (argmax), a continue|stop verdict, a
  diagnosis tally, and an EXTRA_CRITERIA freeze-guard. NO model calls; NO float math,
  argmax, tally, freeze-check, or serialization is done by the SKILL prose — only here.

  CLI:
      python3 improve_step.py --output-json <path> --loop-state <path> \\
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
  ```

- [ ] Run the (empty) test discovery to confirm the harness wiring resolves. Expected: "Ran 0 tests" or a clean "NO TESTS RAN", exit 0/5 (no error). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest discover -s tests -v
  ```
  Expected output (no test files yet, so discovery finds nothing): `Ran 0 tests in 0.000s` followed by `OK` (or `NO TESTS RAN`). NO `ImportError`/`ModuleNotFoundError`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts
  git commit -m "Scaffold prompt-engineering-improve scripts + test harness

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 2 — TDD: load + validate `output.json` and loop-state (RED → GREEN)

- [ ] Write fixtures. Write `skills/prompt-engineering-improve/scripts/tests/fixtures/round00_output.json` (a baseline run: 4 cases, two mandatory-fails ≤3, avg 5.0, pass_rate 25.0):
  ```json
  {
    "meta": {"run_label": "improve-mealplan-round-00", "extra_criteria": "Must include a caloric total and a macro breakdown."},
    "summary": {"total": 4, "average_score": 5.0, "passed": 1, "pass_rate": 25.0},
    "results": [
      {"output": "o1", "score": 8, "reasoning": "good", "test_case": {"scenario": "s1", "prompt_inputs": {"goal": "cut"}, "solution_criteria": ["c1"]}, "verdict": {"strengths": ["clear"], "weaknesses": [], "reasoning": "good", "score": 8}},
      {"output": "o2", "score": 6, "reasoning": "format drift", "test_case": {"scenario": "s2", "prompt_inputs": {"goal": "bulk"}, "solution_criteria": ["c2"]}, "verdict": {"strengths": [], "weaknesses": ["output format inconsistent across sections"], "reasoning": "format drift", "score": 6}},
      {"output": "o3", "score": 3, "reasoning": "missing macro breakdown", "test_case": {"scenario": "s3", "prompt_inputs": {"goal": "maintain"}, "solution_criteria": ["c3"]}, "verdict": {"strengths": [], "weaknesses": ["missing required macro breakdown"], "reasoning": "missing macro breakdown", "score": 3}},
      {"output": "o4", "score": 3, "reasoning": "missing caloric total", "test_case": {"scenario": "s4", "prompt_inputs": {"goal": "cut"}, "solution_criteria": ["c4"]}, "verdict": {"strengths": [], "weaknesses": ["missing caloric total content"], "reasoning": "missing caloric total", "score": 3}}
    ]
  }
  ```

- [ ] Write `skills/prompt-engineering-improve/scripts/tests/fixtures/loopstate_round00.json` (loop-state after the baseline; no prior rounds yet):
  ```json
  {
    "name": "mealplan",
    "current_version": "v1",
    "extra_criteria_hash": "PLACEHOLDER_FILLED_BY_TEST",
    "params": {"pass_threshold": 7, "pass_rate_target": 0.80, "max_rounds": 3, "epsilon": 0.25, "diminishing_return_rounds": 2, "regression_band": 0.5},
    "rounds": []
  }
  ```

- [ ] Write the failing test. Write `skills/prompt-engineering-improve/scripts/tests/test_load.py`:
  ```python
  import json
  import os
  import unittest

  from improve_step import load_output_json, load_loop_state

  FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


  class TestLoad(unittest.TestCase):
      def test_load_output_json_returns_summary_and_results(self):
          out = load_output_json(os.path.join(FIXTURES, "round00_output.json"))
          self.assertEqual(out["summary"]["average_score"], 5.0)
          self.assertEqual(len(out["results"]), 4)

      def test_load_output_json_missing_file_raises(self):
          with self.assertRaises(FileNotFoundError):
              load_output_json(os.path.join(FIXTURES, "nope.json"))

      def test_load_output_json_missing_summary_raises_valueerror(self):
          path = os.path.join(FIXTURES, "_bad.json")
          with open(path, "w", encoding="utf-8") as f:
              json.dump({"results": []}, f)
          try:
              with self.assertRaises(ValueError):
                  load_output_json(path)
          finally:
              os.remove(path)

      def test_load_loop_state_returns_params_and_rounds(self):
          st = load_loop_state(os.path.join(FIXTURES, "loopstate_round00.json"))
          self.assertEqual(st["params"]["max_rounds"], 3)
          self.assertEqual(st["rounds"], [])
  ```

- [ ] Run it; expect FAIL (ImportError: cannot import name `load_output_json`):
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_load -v
  ```
  Expected: `ImportError: cannot import name 'load_output_json' from 'improve_step'`.

- [ ] Implement minimally. Add to `skills/prompt-engineering-improve/scripts/improve_step.py` (after the constants):
  ```python
  def load_output_json(path: str) -> dict:
      """Load an evals/runs/<label>/output.json. Raises FileNotFoundError if absent,
      ValueError if it lacks the {summary, results} shape report.py writes."""
      with open(path, encoding="utf-8") as f:
          data = json.load(f)
      if not isinstance(data, dict) or "summary" not in data or "results" not in data:
          raise ValueError(
              f"{path}: not a report (expected top-level 'summary' and 'results')")
      if not isinstance(data["summary"], dict) or "average_score" not in data["summary"]:
          raise ValueError(f"{path}: 'summary' missing 'average_score'")
      return data


  def load_loop_state(path: str) -> dict:
      """Load the small loop-state JSON. Raises FileNotFoundError if absent,
      ValueError if it lacks 'params' or 'rounds'."""
      with open(path, encoding="utf-8") as f:
          data = json.load(f)
      for key in ("params", "rounds"):
          if key not in data:
              raise ValueError(f"{path}: loop-state missing '{key}'")
      return data
  ```

- [ ] Run again; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_load -v
  ```
  Expected: `Ran 4 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: load+validate output.json and loop-state (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 3 — TDD: per-round delta + running best version (argmax)

- [ ] Write the failing test. Write `skills/prompt-engineering-improve/scripts/tests/test_delta_best.py`:
  ```python
  import unittest

  from improve_step import compute_delta, running_best, RoundRecord


  class TestDeltaBest(unittest.TestCase):
      def test_delta_first_round_is_none(self):
          # No prior round -> delta is None (baseline has nothing to compare to).
          self.assertIsNone(compute_delta(current_avg=5.0, prior_avg=None))

      def test_delta_positive(self):
          self.assertEqual(compute_delta(current_avg=6.5, prior_avg=5.0), 1.5)

      def test_delta_negative(self):
          self.assertEqual(compute_delta(current_avg=4.5, prior_avg=5.0), -0.5)

      def test_delta_rounds_to_two_dp(self):
          self.assertEqual(compute_delta(current_avg=5.3333, prior_avg=5.0), 0.33)

      def test_running_best_argmax_returns_highest_avg_version(self):
          rounds = [
              RoundRecord(version="v1", avg=5.0, pass_rate=25.0),
              RoundRecord(version="v2", avg=7.2, pass_rate=75.0),
              RoundRecord(version="v3", avg=6.8, pass_rate=50.0),
          ]
          self.assertEqual(running_best(rounds).version, "v2")

      def test_running_best_tie_keeps_earliest(self):
          rounds = [
              RoundRecord(version="v1", avg=7.0, pass_rate=50.0),
              RoundRecord(version="v2", avg=7.0, pass_rate=75.0),
          ]
          # Ties broken by earliest (the baseline-of-equal-quality is kept; spec §6 tie-break).
          self.assertEqual(running_best(rounds).version, "v1")

      def test_running_best_empty_returns_none(self):
          self.assertIsNone(running_best([]))
  ```

- [ ] Run it; expect FAIL (ImportError). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_delta_best -v
  ```
  Expected: `ImportError: cannot import name 'compute_delta' from 'improve_step'`.

- [ ] Implement. Add to `improve_step.py`:
  ```python
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
      """The highest-avg round so far (argmax). Ties → earliest (stable max by index)."""
      if not rounds:
          return None
      best = rounds[0]
      for r in rounds[1:]:
          if r.avg > best.avg:  # strict > keeps the earliest on a tie
              best = r
      return best
  ```

- [ ] Run again; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_delta_best -v
  ```
  Expected: `Ran 7 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: per-round delta + running-best argmax (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 4 — TDD: stop verdict — threshold, pass_rate, max_rounds

- [ ] Write the failing test. Write `skills/prompt-engineering-improve/scripts/tests/test_stop_verdict.py`:
  ```python
  import unittest

  from improve_step import stop_verdict, RoundRecord, LoopParams

  PARAMS = LoopParams(
      pass_threshold=7, pass_rate_target=0.80, max_rounds=3,
      epsilon=0.25, diminishing_return_rounds=2, regression_band=0.5,
  )


  class TestStopVerdict(unittest.TestCase):
      def _rr(self, version, avg, pr):
          return RoundRecord(version=version, avg=avg, pass_rate=pr)

      def test_continue_when_below_bar_and_rounds_remain(self):
          rounds = [self._rr("v1", 5.0, 25.0)]
          v = stop_verdict(rounds, PARAMS, round_index=0)
          self.assertEqual(v.decision, "continue")
          self.assertIsNone(v.rule)

      def test_stop_threshold_when_avg_meets_pass_threshold(self):
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 7.0, 60.0)]
          v = stop_verdict(rounds, PARAMS, round_index=1)
          self.assertEqual(v.decision, "stop")
          self.assertEqual(v.rule, "threshold")

      def test_stop_pass_rate_when_target_reached(self):
          # avg below 7 but pass_rate >= 80% -> stop on pass_rate.
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 6.9, 80.0)]
          v = stop_verdict(rounds, PARAMS, round_index=1)
          self.assertEqual(v.decision, "stop")
          self.assertEqual(v.rule, "pass_rate")

      def test_stop_max_rounds_when_cap_reached(self):
          # round_index counts the baseline as round 0; max_rounds=3 improvement
          # rounds means baseline=0, r1=1, r2=2, r3=3 -> the cap fires at index 3
          # (round_index >= max_rounds). Four rounds total: baseline + 3 improvements.
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 5.5, 30.0),
                    self._rr("v3", 5.8, 35.0), self._rr("v4", 6.0, 40.0)]
          v = stop_verdict(rounds, PARAMS, round_index=3)
          self.assertEqual(v.decision, "stop")
          self.assertEqual(v.rule, "max_rounds")

      def test_threshold_takes_priority_over_max_rounds(self):
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 6.0, 40.0),
                    self._rr("v3", 6.5, 50.0), self._rr("v4", 8.0, 90.0)]
          v = stop_verdict(rounds, PARAMS, round_index=3)
          self.assertEqual(v.rule, "threshold")  # report the success rule, not the budget cap
  ```

- [ ] Run it; expect FAIL (ImportError). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_stop_verdict -v
  ```
  Expected: `ImportError: cannot import name 'stop_verdict' from 'improve_step'`.

- [ ] Implement. Add to `improve_step.py`:
  ```python
  @dataclass
  class LoopParams:
      """The five loop params (run_eval.py constants block) + pass_threshold (config)."""
      pass_threshold: int
      pass_rate_target: float
      max_rounds: int
      epsilon: float
      diminishing_return_rounds: int
      regression_band: float


  @dataclass
  class Verdict:
      decision: str           # "continue" | "stop"
      rule: str | None        # threshold | pass_rate | diminishing-returns-K | regression_band | max_rounds
      detail: str = ""


  def stop_verdict(rounds: list[RoundRecord], params: LoopParams, *, round_index: int) -> Verdict:
      """Decide continue|stop:<rule> from the completed rounds. If several rules
      fire, report the FIRST in this priority order so success/regression beat the
      budget cap: threshold, pass_rate, regression_band, diminishing-returns-K,
      max_rounds. (The caller keeps the best version regardless.)

      round_index CONVENTION: 0-based, where the BASELINE is round 0 and the
      improvement rounds are 1..max_rounds. So round_index == len(all_rounds) - 1
      with all_rounds = [baseline, r1, r2, ...]. The budget cap therefore fires
      when round_index >= max_rounds (i.e. after max_rounds improvement rounds
      beyond the baseline): max_rounds=3 -> baseline=0, r1=1, r2=2, r3=3 -> stop
      at round_index==3."""
      if not rounds:
          return Verdict("continue", None, "no rounds yet")
      latest = rounds[-1]

      # 1. Success: avg bar met.
      if latest.avg >= params.pass_threshold:
          return Verdict("stop", "threshold",
                         f"avg {latest.avg} >= pass_threshold {params.pass_threshold}")
      # 2. Success: pass-rate target reached (pass_rate is a percentage 0-100).
      if latest.pass_rate >= params.pass_rate_target * 100:
          return Verdict("stop", "pass_rate",
                         f"pass_rate {latest.pass_rate}% >= target {params.pass_rate_target * 100}%")
      # 3. Regression: latest is > band below the best -> stop and revert (Task 6 fills the math).
      reg = _regression_rule(rounds, params)
      if reg is not None:
          return reg
      # 4. Diminishing returns: K consecutive sub-epsilon rounds (Task 6 fills the math).
      dim = _diminishing_rule(rounds, params)
      if dim is not None:
          return dim
      # 5. Budget cap: baseline is round 0, improvement rounds are 1..max_rounds,
      #    so the cap fires when round_index >= max_rounds (max_rounds rounds done).
      if round_index >= params.max_rounds:
          return Verdict("stop", "max_rounds",
                         f"round_index {round_index} reached cap {params.max_rounds}")
      return Verdict("continue", None, f"round_index {round_index} of cap {params.max_rounds}")


  def _regression_rule(rounds, params):  # filled in Task 6
      return None


  def _diminishing_rule(rounds, params):  # filled in Task 6
      return None
  ```

- [ ] Run again; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_stop_verdict -v
  ```
  Expected: `Ran 5 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: stop verdict — threshold/pass_rate/max_rounds (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 5 — TDD: diagnosis tally — mandatory-fail count + %-per-theme

- [ ] Write the failing test. Write `skills/prompt-engineering-improve/scripts/tests/test_tally.py`:
  ```python
  import json
  import os
  import unittest

  from improve_step import diagnose_tally, load_output_json

  FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


  class TestTally(unittest.TestCase):
      def test_mandatory_fail_count_uses_score_le_3(self):
          out = load_output_json(os.path.join(FIXTURES, "round00_output.json"))
          tally = diagnose_tally(out["results"])
          # round00 fixture: scores 8,6,3,3 -> two cases <=3.
          self.assertEqual(tally["mandatory_fail_count"], 2)
          self.assertEqual(tally["total_cases"], 4)
          self.assertEqual(tally["mandatory_fail_pct"], 50.0)

      def test_theme_percentages_from_weakness_keywords(self):
          out = load_output_json(os.path.join(FIXTURES, "round00_output.json"))
          tally = diagnose_tally(out["results"])
          themes = tally["theme_pct"]
          # 2 cases mention 'missing required/missing ... content' -> missing_content theme.
          self.assertIn("missing_content", themes)
          self.assertEqual(themes["missing_content"], 50.0)
          # 1 case mentions 'output format inconsistent' -> format_structure theme.
          self.assertIn("format_structure", themes)
          self.assertEqual(themes["format_structure"], 25.0)

      def test_empty_results_is_zeroed(self):
          tally = diagnose_tally([])
          self.assertEqual(tally["mandatory_fail_count"], 0)
          self.assertEqual(tally["total_cases"], 0)
          self.assertEqual(tally["mandatory_fail_pct"], 0.0)
          self.assertEqual(tally["theme_pct"], {})
  ```

- [ ] Run it; expect FAIL (ImportError). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_tally -v
  ```
  Expected: `ImportError: cannot import name 'diagnose_tally' from 'improve_step'`.

- [ ] Implement. Add to `improve_step.py`. The theme keyword table is the deterministic half of the diagnosis (the model NAMES the dominant theme separately; this only counts keyword hits the judge already wrote, giving the model a tally to anchor on):
  ```python
  # Weakness-theme keyword table. Deterministic substring match over each verdict's
  # 'weaknesses' strings. Mirrors references/diagnosis.md's themes. A case counts once
  # per theme it matches. NOT a classifier — it tallies what the judge already wrote so
  # the model can name the DOMINANT theme against real counts.
  THEME_KEYWORDS = {
      "missing_content": ["missing", "omitted", "absent", "did not include", "left out"],
      "format_structure": ["format", "structure", "inconsistent", "ordering", "schema"],
      "reasoning": ["reasoning", "logic", "incorrect", "wrong", "shallow", "hallucin"],
      "tone_style": ["tone", "style", "voice", "register", "verbose", "terse"],
      "conflicting": ["conflict", "ambiguous", "contradict", "unclear instruction"],
  }


  def diagnose_tally(results: list[dict]) -> dict:
      """Count mandatory-fails (score <= 3, per grading.md) and %-of-cases per
      weakness theme. Pure tally over the verdict JSON — no model call."""
      total = len(results)
      if total == 0:
          return {"mandatory_fail_count": 0, "total_cases": 0,
                  "mandatory_fail_pct": 0.0, "theme_pct": {}}
      mandatory = sum(1 for r in results if int(r.get("score", 0)) <= MANDATORY_FAIL_MAX)
      theme_hits = {theme: 0 for theme in THEME_KEYWORDS}
      for r in results:
          weaknesses = " ".join(r.get("verdict", {}).get("weaknesses", [])).lower()
          for theme, keywords in THEME_KEYWORDS.items():
              if any(kw in weaknesses for kw in keywords):
                  theme_hits[theme] += 1
      theme_pct = {
          theme: round(100.0 * hits / total, 1)
          for theme, hits in theme_hits.items() if hits > 0
      }
      return {
          "mandatory_fail_count": mandatory,
          "total_cases": total,
          "mandatory_fail_pct": round(100.0 * mandatory / total, 1),
          "theme_pct": theme_pct,
      }
  ```

- [ ] Run again; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_tally -v
  ```
  Expected: `Ran 3 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: diagnosis tally — mandatory-fails + theme percentages (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 6 — TDD: regression_band + diminishing-returns-K rules (fill the stubs)

- [ ] Add failing tests. Append to `skills/prompt-engineering-improve/scripts/tests/test_stop_verdict.py` (add these methods inside `TestStopVerdict`):
  ```python
      def test_stop_regression_when_more_than_band_below_best(self):
          # best v2=7.2; v3=6.5 is 0.7 below best > band 0.5 -> stop:regression_band.
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 7.2, 75.0),
                    self._rr("v3", 6.5, 50.0)]
          v = stop_verdict(rounds, PARAMS, round_index=2)
          self.assertEqual(v.decision, "stop")
          self.assertEqual(v.rule, "regression_band")

      def test_no_regression_within_band(self):
          # best v2=7.2 already meets threshold 7 -> threshold fires first, not regression.
          # Use a sub-threshold best to isolate the band: best v2=6.9; v3=6.5 is 0.4 below -> within band.
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 6.9, 60.0),
                    self._rr("v3", 6.5, 55.0)]
          v = stop_verdict(rounds, PARAMS, round_index=2)
          # 0.4 <= band 0.5 -> not a regression; rounds remain (index 2, cap 3) -> continue.
          self.assertEqual(v.decision, "continue")

      def test_stop_diminishing_returns_after_K_subepsilon_rounds(self):
          # epsilon 0.25, K=2: two consecutive deltas below 0.25 (0.1 then 0.1) -> stop.
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 5.1, 26.0),
                    self._rr("v3", 5.2, 27.0)]
          v = stop_verdict(rounds, PARAMS, round_index=2)
          self.assertEqual(v.decision, "stop")
          self.assertEqual(v.rule, "diminishing-returns-2")

      def test_one_subepsilon_round_is_not_diminishing(self):
          rounds = [self._rr("v1", 5.0, 25.0), self._rr("v2", 5.1, 26.0)]
          v = stop_verdict(rounds, PARAMS, round_index=1)
          self.assertEqual(v.decision, "continue")
  ```

- [ ] Run them; expect FAIL (the stubs return None, so regression/diminishing assertions fail). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_stop_verdict -v
  ```
  Expected: failures on `test_stop_regression_when_more_than_band_below_best` and `test_stop_diminishing_returns_after_K_subepsilon_rounds` (AssertionError: 'continue' != 'stop').

- [ ] Implement — replace the two stubs in `improve_step.py`:
  ```python
  def _regression_rule(rounds, params):
      """A round is a regression only if it scores MORE than regression_band below the
      best round so far (spec §6: 0.5, not 0.0, for judge-noise robustness)."""
      if len(rounds) < 2:
          return None
      best = running_best(rounds[:-1])  # best among PRIOR rounds
      latest = rounds[-1]
      if best is not None and (best.avg - latest.avg) > params.regression_band:
          return Verdict(
              "stop", "regression_band",
              f"avg {latest.avg} is {round(best.avg - latest.avg, 2)} below best "
              f"{best.avg} (> band {params.regression_band}); revert to {best.version}")
      return None


  def _diminishing_rule(rounds, params):
      """Stop when the last K consecutive per-round deltas are all below epsilon."""
      k = params.diminishing_return_rounds
      if len(rounds) < k + 1:  # need K deltas -> K+1 rounds
          return None
      deltas = [round(rounds[i].avg - rounds[i - 1].avg, 2) for i in range(1, len(rounds))]
      last_k = deltas[-k:]
      if all(d < params.epsilon for d in last_k):
          return Verdict(
              "stop", f"diminishing-returns-{k}",
              f"last {k} deltas {last_k} all < epsilon {params.epsilon}")
      return None
  ```

- [ ] Run again; expect PASS (all of test_stop_verdict, now 9 tests):
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_stop_verdict -v
  ```
  Expected: `Ran 9 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: regression_band + diminishing-returns-K rules (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 7 — TDD: `EXTRA_CRITERIA` hash freeze-guard

- [ ] Write the failing test. Write `skills/prompt-engineering-improve/scripts/tests/test_freeze_guard.py`:
  ```python
  import unittest

  from improve_step import extra_criteria_hash, assert_freeze, FreezeViolation


  class TestFreezeGuard(unittest.TestCase):
      def test_hash_is_stable_for_same_text(self):
          a = extra_criteria_hash("Must include a caloric total and a macro breakdown.")
          b = extra_criteria_hash("Must include a caloric total and a macro breakdown.")
          self.assertEqual(a, b)
          self.assertEqual(len(a), 64)  # sha256 hexdigest

      def test_hash_ignores_surrounding_whitespace(self):
          a = extra_criteria_hash("  Must include X.  ")
          b = extra_criteria_hash("Must include X.")
          self.assertEqual(a, b)

      def test_hash_differs_for_different_text(self):
          self.assertNotEqual(extra_criteria_hash("A"), extra_criteria_hash("B"))

      def test_assert_freeze_passes_when_unchanged(self):
          h = extra_criteria_hash("frozen")
          # Returns the hash on success (no raise).
          self.assertEqual(assert_freeze(frozen_hash=h, current_text="frozen"), h)

      def test_assert_freeze_raises_when_changed(self):
          h = extra_criteria_hash("frozen")
          with self.assertRaises(FreezeViolation):
              assert_freeze(frozen_hash=h, current_text="tampered")
  ```

- [ ] Run it; expect FAIL (ImportError). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_freeze_guard -v
  ```
  Expected: `ImportError: cannot import name 'extra_criteria_hash' from 'improve_step'`.

- [ ] Implement. Add to `improve_step.py`:
  ```python
  class FreezeViolation(RuntimeError):
      """Raised when EXTRA_CRITERIA changed after the freeze snapshot (spec §6)."""


  def extra_criteria_hash(text: str | None) -> str:
      """SHA-256 of the stripped EXTRA_CRITERIA text. None -> hash of empty string."""
      normalized = (text or "").strip().encode("utf-8")
      return hashlib.sha256(normalized).hexdigest()


  def assert_freeze(*, frozen_hash: str, current_text: str | None) -> str:
      """Assert EXTRA_CRITERIA is unchanged vs. the loop-start snapshot. Returns the
      current hash on success; raises FreezeViolation otherwise. Deterministic
      enforcement of the freeze (spec §6) — not a prose reminder."""
      current = extra_criteria_hash(current_text)
      if current != frozen_hash:
          raise FreezeViolation(
              f"EXTRA_CRITERIA changed during the loop (frozen {frozen_hash[:12]}…, "
              f"now {current[:12]}…). Held-out claims are forfeit; regenerate a held-out set.")
      return current
  ```

- [ ] Run again; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_freeze_guard -v
  ```
  Expected: `Ran 5 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: EXTRA_CRITERIA hash freeze-guard (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 8 — TDD: the `main()` CLI — assemble `delta.json` + exit codes

- [ ] Add a fixture for a round-01 output (a clear improvement over round00) so the CLI can compute a real delta. Write `skills/prompt-engineering-improve/scripts/tests/fixtures/round01_output.json`:
  ```json
  {
    "meta": {"run_label": "improve-mealplan-round-01", "extra_criteria": "Must include a caloric total and a macro breakdown."},
    "summary": {"total": 4, "average_score": 7.5, "passed": 3, "pass_rate": 75.0},
    "results": [
      {"output": "o1", "score": 8, "reasoning": "good", "test_case": {"scenario": "s1", "prompt_inputs": {"goal": "cut"}, "solution_criteria": ["c1"]}, "verdict": {"strengths": ["clear"], "weaknesses": [], "reasoning": "good", "score": 8}},
      {"output": "o2", "score": 8, "reasoning": "fixed", "test_case": {"scenario": "s2", "prompt_inputs": {"goal": "bulk"}, "solution_criteria": ["c2"]}, "verdict": {"strengths": ["consistent format"], "weaknesses": [], "reasoning": "fixed", "score": 8}},
      {"output": "o3", "score": 8, "reasoning": "now has macros", "test_case": {"scenario": "s3", "prompt_inputs": {"goal": "maintain"}, "solution_criteria": ["c3"]}, "verdict": {"strengths": ["macros present"], "weaknesses": [], "reasoning": "now has macros", "score": 8}},
      {"output": "o4", "score": 6, "reasoning": "caloric total still terse", "test_case": {"scenario": "s4", "prompt_inputs": {"goal": "cut"}, "solution_criteria": ["c4"]}, "verdict": {"strengths": [], "weaknesses": ["caloric total format terse"], "reasoning": "caloric total still terse", "score": 6}}
    ]
  }
  ```

- [ ] Add a loop-state fixture for round 01 carrying the baseline round + a matching frozen hash. The `extra_criteria_hash` of the criteria text must be precomputed; the test computes it at runtime to avoid a hardcoded digest. Write `skills/prompt-engineering-improve/scripts/tests/fixtures/loopstate_round01.json`:
  ```json
  {
    "name": "mealplan",
    "current_version": "v2",
    "extra_criteria": "Must include a caloric total and a macro breakdown.",
    "extra_criteria_hash": "FILLED_BY_TEST_AT_RUNTIME",
    "params": {"pass_threshold": 7, "pass_rate_target": 0.80, "max_rounds": 3, "epsilon": 0.25, "diminishing_return_rounds": 2, "regression_band": 0.5},
    "rounds": [
      {"version": "v1", "avg": 5.0, "pass_rate": 25.0}
    ]
  }
  ```

- [ ] Write the failing CLI test. Write `skills/prompt-engineering-improve/scripts/tests/test_cli.py`:
  ```python
  import json
  import os
  import tempfile
  import unittest

  from improve_step import main, extra_criteria_hash

  FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


  def _loopstate_with_hash(tmpdir):
      """Copy loopstate_round01.json into tmpdir with the real EXTRA_CRITERIA hash."""
      src = os.path.join(FIXTURES, "loopstate_round01.json")
      with open(src, encoding="utf-8") as f:
          st = json.load(f)
      st["extra_criteria_hash"] = extra_criteria_hash(st["extra_criteria"])
      path = os.path.join(tmpdir, "loopstate.json")
      with open(path, "w", encoding="utf-8") as f:
          json.dump(st, f)
      return path


  class TestCli(unittest.TestCase):
      def test_round01_improvement_writes_delta_and_exits_stop_threshold(self):
          with tempfile.TemporaryDirectory() as d:
              loopstate = _loopstate_with_hash(d)
              delta_out = os.path.join(d, "delta.json")
              rc = main([
                  "--output-json", os.path.join(FIXTURES, "round01_output.json"),
                  "--loop-state", loopstate,
                  "--delta-out", delta_out,
                  "--check-freeze",
              ])
              # round01 avg 7.5 >= pass_threshold 7 -> stop:threshold -> exit 1.
              self.assertEqual(rc, 1)
              with open(delta_out, encoding="utf-8") as f:
                  payload = json.load(f)
          self.assertEqual(payload["delta"], 2.5)          # 7.5 - 5.0
          self.assertEqual(payload["best"]["version"], "v2")
          self.assertEqual(payload["verdict"]["decision"], "stop")
          self.assertEqual(payload["verdict"]["rule"], "threshold")
          self.assertEqual(payload["tally"]["mandatory_fail_count"], 0)
          self.assertIn("params", payload)                 # resolved params stamped in
          self.assertIn("extra_criteria_hash", payload)

      def test_continue_exits_zero(self):
          # round00 baseline alone (avg 5.0, no prior) -> continue -> exit 0.
          with tempfile.TemporaryDirectory() as d:
              rc = main([
                  "--output-json", os.path.join(FIXTURES, "round00_output.json"),
                  "--loop-state", os.path.join(FIXTURES, "loopstate_round00.json"),
                  "--delta-out", os.path.join(d, "delta.json"),
              ])
              self.assertEqual(rc, 0)

      def test_freeze_violation_exits_two(self):
          with tempfile.TemporaryDirectory() as d:
              src = os.path.join(FIXTURES, "loopstate_round01.json")
              with open(src, encoding="utf-8") as f:
                  st = json.load(f)
              st["extra_criteria_hash"] = extra_criteria_hash("a DIFFERENT frozen value")
              loopstate = os.path.join(d, "loopstate.json")
              with open(loopstate, "w", encoding="utf-8") as f:
                  json.dump(st, f)
              rc = main([
                  "--output-json", os.path.join(FIXTURES, "round01_output.json"),
                  "--loop-state", loopstate,
                  "--delta-out", os.path.join(d, "delta.json"),
                  "--check-freeze",
              ])
              self.assertEqual(rc, 2)

      def test_bad_output_json_exits_two(self):
          with tempfile.TemporaryDirectory() as d:
              rc = main([
                  "--output-json", os.path.join(FIXTURES, "does_not_exist.json"),
                  "--loop-state", os.path.join(FIXTURES, "loopstate_round00.json"),
                  "--delta-out", os.path.join(d, "delta.json"),
              ])
              self.assertEqual(rc, 2)
  ```

- [ ] Run it; expect FAIL (ImportError: cannot import `main`). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_cli -v
  ```
  Expected: `ImportError: cannot import name 'main' from 'improve_step'`.

- [ ] Implement `main()` + a `build_delta_payload` assembler. Add to `improve_step.py`:
  ```python
  def build_delta_payload(*, output: dict, state: dict) -> dict:
      """Assemble the deterministic delta.json payload from this round's output.json
      and the loop-state. The model does NONE of this arithmetic (spec §6)."""
      params = LoopParams(**state["params"])
      summary = output["summary"]
      version = state.get("current_version", "v?")

      prior = state.get("rounds", [])
      prior_records = [RoundRecord(version=r["version"], avg=r["avg"],
                                   pass_rate=r["pass_rate"]) for r in prior]
      prior_avg = prior_records[-1].avg if prior_records else None

      this_round = RoundRecord(version=version, avg=summary["average_score"],
                               pass_rate=summary["pass_rate"])
      all_rounds = prior_records + [this_round]
      round_index = len(all_rounds) - 1  # 0-based

      delta = compute_delta(current_avg=this_round.avg, prior_avg=prior_avg)
      best = running_best(all_rounds)
      verdict = stop_verdict(all_rounds, params, round_index=round_index)
      tally = diagnose_tally(output["results"])

      return {
          "version": version,
          "round_index": round_index,
          "delta": delta,
          "best": {"version": best.version, "avg": best.avg, "pass_rate": best.pass_rate},
          "verdict": {"decision": verdict.decision, "rule": verdict.rule, "detail": verdict.detail},
          "tally": tally,
          "params": asdict(params),
          "extra_criteria_hash": state.get("extra_criteria_hash", ""),
      }


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(
          description="Deterministic per-round loop logic for prompt-engineering-improve.")
      parser.add_argument("--output-json", required=True,
                          help="this round's evals/runs/<label>/output.json")
      parser.add_argument("--loop-state", required=True,
                          help="the loop-state JSON (params, prior rounds, frozen hash)")
      parser.add_argument("--delta-out", default=None,
                          help="where to write delta.json (default: alongside loop-state)")
      parser.add_argument("--check-freeze", action="store_true",
                          help="assert EXTRA_CRITERIA hash unchanged before emitting")
      args = parser.parse_args(argv)

      try:
          output = load_output_json(args.output_json)
          state = load_loop_state(args.loop_state)
      except (OSError, ValueError, json.JSONDecodeError) as exc:
          print(f"ERROR: {exc}")
          return 2

      if args.check_freeze:
          try:
              assert_freeze(frozen_hash=state.get("extra_criteria_hash", ""),
                            current_text=state.get("extra_criteria"))
          except FreezeViolation as exc:
              print(f"FREEZE VIOLATION: {exc}")
              return 2

      payload = build_delta_payload(output=output, state=state)

      delta_out = args.delta_out
      if delta_out is None:
          import os
          delta_out = os.path.join(os.path.dirname(args.loop_state) or ".", "delta.json")
      with open(delta_out, "w", encoding="utf-8") as f:
          json.dump(payload, f, indent=2, ensure_ascii=False)

      d = payload["delta"]
      print(f"delta: {d if d is not None else 'baseline (no prior)'}")
      print(f"best: {payload['best']['version']} (avg {payload['best']['avg']})")
      print(f"verdict: {payload['verdict']['decision']}"
            + (f":{payload['verdict']['rule']}" if payload['verdict']['rule'] else ""))
      print(f"mandatory-fails: {payload['tally']['mandatory_fail_count']}/"
            f"{payload['tally']['total_cases']}; themes: {payload['tally']['theme_pct']}")
      print(f"wrote {delta_out}")

      return 1 if payload["verdict"]["decision"] == "stop" else 0


  if __name__ == "__main__":
      sys.exit(main())
  ```

- [ ] Run the CLI test; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_cli -v
  ```
  Expected: `Ran 4 tests in ...` + `OK`.

- [ ] Run the FULL suite to confirm no regressions:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest discover -s tests -v
  ```
  Expected: `Ran 32 tests in ...` + `OK` (4 load + 7 delta/best + 9 stop + 3 tally + 5 freeze + 4 cli = 32).

- [ ] Verify the CLI runs as a real subprocess (the way the SKILL invokes it) and exits 1 on stop:threshold:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 - <<'PY'
  import json, subprocess, sys, tempfile, os
  from improve_step import extra_criteria_hash
  d = tempfile.mkdtemp()
  st = json.load(open("tests/fixtures/loopstate_round01.json"))
  st["extra_criteria_hash"] = extra_criteria_hash(st["extra_criteria"])
  ls = os.path.join(d, "loopstate.json"); json.dump(st, open(ls, "w"))
  rc = subprocess.call([sys.executable, "improve_step.py",
      "--output-json", "tests/fixtures/round01_output.json",
      "--loop-state", ls, "--delta-out", os.path.join(d, "delta.json"), "--check-freeze"])
  print("EXIT", rc); assert rc == 1, rc
  PY
  ```
  Expected: prints `delta: 2.5`, `best: v2 ...`, `verdict: stop:threshold`, then `EXIT 1`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: main() CLI assembles delta.json + exit codes (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 9 — TDD: deterministic `finalize` mode — assemble `final-report.json`

The per-round `delta.json` covers one round. The **final report** is the loop's
deterministic, end-of-run serialization: resolved loop params, the round-by-round trace,
the winning version (argmax over all rounds), `held_out_run_count`, the `EXTRA_CRITERIA`
hash, and the held-out result (or `"skipped"`). It MUST be code, not model prose — the
skill (Task 15) CALLS this so the model never hand-serializes `held_out_run_count` or the
`EXTRA_CRITERIA` hash (that would violate `improve_step.py`'s own determinism docstring).
Depends only on the helper functions from Tasks 2–8 (`LoopParams`, `RoundRecord`,
`compute_delta`, `running_best`, `assert_freeze`); placed here, right after the CLI, so it
extends the same `main()`.

- [ ] Add a finalize loop-state fixture: the full loop accumulated into one state file (the
  baseline + one improvement round that hit threshold, each round carrying the strings the
  skill records — `technique`, `decision`, `run_dir` — plus a held-out block run once). The
  `extra_criteria_hash` is filled at runtime by the test. Write
  `skills/prompt-engineering-improve/scripts/tests/fixtures/loopstate_final.json`:
  ```json
  {
    "name": "mealplan",
    "current_version": "v2",
    "extra_criteria": "Must include a caloric total and a macro breakdown.",
    "extra_criteria_hash": "FILLED_BY_TEST_AT_RUNTIME",
    "params": {"pass_threshold": 7, "pass_rate_target": 0.80, "max_rounds": 3, "epsilon": 0.25, "diminishing_return_rounds": 2, "regression_band": 0.5},
    "rounds": [
      {"version": "v1", "avg": 5.0, "pass_rate": 25.0, "technique": "baseline", "decision": "continue", "run_dir": "evals/runs/improve-mealplan-round-00"},
      {"version": "v2", "avg": 7.5, "pass_rate": 75.0, "technique": "process steps + multishot examples", "decision": "stop:threshold", "run_dir": "evals/runs/improve-mealplan-round-01"}
    ],
    "held_out": {"run_count": 1, "result": {"average_score": 7.2, "pass_rate": 70.0}}
  }
  ```

- [ ] Add a finalize loop-state fixture WITHOUT a held-out block (held-out skipped). Write
  `skills/prompt-engineering-improve/scripts/tests/fixtures/loopstate_final_noheldout.json`:
  ```json
  {
    "name": "mealplan",
    "current_version": "v2",
    "extra_criteria": "Must include a caloric total and a macro breakdown.",
    "extra_criteria_hash": "FILLED_BY_TEST_AT_RUNTIME",
    "params": {"pass_threshold": 7, "pass_rate_target": 0.80, "max_rounds": 3, "epsilon": 0.25, "diminishing_return_rounds": 2, "regression_band": 0.5},
    "rounds": [
      {"version": "v1", "avg": 5.0, "pass_rate": 25.0, "technique": "baseline", "decision": "continue", "run_dir": "evals/runs/improve-mealplan-round-00"},
      {"version": "v2", "avg": 7.5, "pass_rate": 75.0, "technique": "process steps + multishot examples", "decision": "stop:threshold", "run_dir": "evals/runs/improve-mealplan-round-01"}
    ]
  }
  ```

- [ ] Write the failing test. Write `skills/prompt-engineering-improve/scripts/tests/test_final_report.py`:
  ```python
  import json
  import os
  import tempfile
  import unittest

  from improve_step import build_final_report, main, extra_criteria_hash, load_loop_state

  FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


  def _state_with_hash(name, tmpdir):
      src = os.path.join(FIXTURES, name)
      with open(src, encoding="utf-8") as f:
          st = json.load(f)
      st["extra_criteria_hash"] = extra_criteria_hash(st["extra_criteria"])
      path = os.path.join(tmpdir, name)
      with open(path, "w", encoding="utf-8") as f:
          json.dump(st, f)
      return path


  class TestFinalReport(unittest.TestCase):
      def test_trace_best_and_held_out(self):
          state = load_loop_state(os.path.join(FIXTURES, "loopstate_final.json"))
          report = build_final_report(state=state)
          # argmax over [v1=5.0, v2=7.5] -> v2.
          self.assertEqual(report["best_version"], "v2")
          # Round-by-round trace: 2 rounds, baseline delta None, round-01 delta 2.5.
          self.assertEqual(len(report["rounds"]), 2)
          self.assertIsNone(report["rounds"][0]["delta"])
          self.assertEqual(report["rounds"][1]["delta"], 2.5)
          # Trace carries the recorded strings (NOT arithmetic) verbatim.
          self.assertEqual(report["rounds"][1]["technique"], "process steps + multishot examples")
          self.assertEqual(report["rounds"][1]["decision"], "stop:threshold")
          self.assertEqual(report["rounds"][1]["run_dir"], "evals/runs/improve-mealplan-round-01")
          # Resolved loop params stamped in.
          self.assertEqual(report["params"]["max_rounds"], 3)
          # Held-out ran exactly once and its result is recorded (not "skipped").
          self.assertEqual(report["held_out_run_count"], 1)
          self.assertEqual(report["held_out_result"]["average_score"], 7.2)

      def test_held_out_skipped_when_absent(self):
          state = load_loop_state(os.path.join(FIXTURES, "loopstate_final_noheldout.json"))
          report = build_final_report(state=state)
          self.assertEqual(report["held_out_run_count"], 0)
          self.assertEqual(report["held_out_result"], "skipped")

      def test_cli_finalize_writes_final_report(self):
          with tempfile.TemporaryDirectory() as d:
              loopstate = _state_with_hash("loopstate_final.json", d)
              out = os.path.join(d, "final-report.json")
              rc = main([
                  "--loop-state", loopstate,
                  "--final-report-out", out,
                  "--check-freeze",
              ])
              self.assertEqual(rc, 0)  # finalize success -> exit 0
              with open(out, encoding="utf-8") as f:
                  report = json.load(f)
          self.assertEqual(report["best_version"], "v2")
          self.assertEqual(report["held_out_run_count"], 1)
          self.assertIn("extra_criteria_hash", report)
          self.assertIn("params", report)

      def test_cli_finalize_freeze_violation_exits_two(self):
          with tempfile.TemporaryDirectory() as d:
              src = os.path.join(FIXTURES, "loopstate_final.json")
              with open(src, encoding="utf-8") as f:
                  st = json.load(f)
              st["extra_criteria_hash"] = extra_criteria_hash("a DIFFERENT frozen value")
              loopstate = os.path.join(d, "loopstate.json")
              with open(loopstate, "w", encoding="utf-8") as f:
                  json.dump(st, f)
              rc = main([
                  "--loop-state", loopstate,
                  "--final-report-out", os.path.join(d, "final-report.json"),
                  "--check-freeze",
              ])
              self.assertEqual(rc, 2)
  ```

- [ ] Run it; expect FAIL (ImportError: cannot import `build_final_report`). Command:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_final_report -v
  ```
  Expected: `ImportError: cannot import name 'build_final_report' from 'improve_step'`.

- [ ] Implement. Add `build_final_report` to `improve_step.py` (after `build_delta_payload`):
  ```python
  def build_final_report(*, state: dict) -> dict:
      """Assemble the deterministic final-report.json for a finished loop. Reads the
      loop-state JSON whose 'rounds' accumulated every round's {version, avg, pass_rate}
      plus the strings the skill recorded per round (technique, decision, run_dir). The
      model serializes NONE of this (spec §6): the trace deltas, the argmax best version,
      held_out_run_count, and the EXTRA_CRITERIA hash are all produced HERE."""
      params = LoopParams(**state["params"])
      rounds_raw = state.get("rounds", [])
      records = [RoundRecord(version=r["version"], avg=r["avg"], pass_rate=r["pass_rate"])
                 for r in rounds_raw]

      trace = []
      prior_avg = None
      for i, r in enumerate(rounds_raw):
          delta = compute_delta(current_avg=r["avg"], prior_avg=prior_avg)
          trace.append({
              "round_index": i,
              "version": r["version"],
              "avg": r["avg"],
              "pass_rate": r["pass_rate"],
              "delta": delta,                       # recomputed here, never by the model
              "technique": r.get("technique", ""),  # recorded string, passed through
              "decision": r.get("decision", ""),
              "run_dir": r.get("run_dir", ""),
          })
          prior_avg = r["avg"]

      best = running_best(records)
      held = state.get("held_out")
      if held is None:
          held_out_run_count = 0
          held_out_result = "skipped"
      else:
          held_out_run_count = int(held.get("run_count", 0))
          held_out_result = held.get("result", "skipped")

      return {
          "name": state.get("name", ""),
          "params": asdict(params),
          "rounds": trace,
          "best_version": best.version if best is not None else None,
          "best": ({"version": best.version, "avg": best.avg, "pass_rate": best.pass_rate}
                   if best is not None else None),
          "held_out_run_count": held_out_run_count,
          "held_out_result": held_out_result,
          "extra_criteria_hash": state.get("extra_criteria_hash", ""),
      }
  ```
  Then add a `--final-report-out` arg and a finalize branch to `main()`. Add the argument
  next to the others:
  ```python
      parser.add_argument("--final-report-out", default=None,
                          help="finalize mode: write the deterministic final-report.json "
                               "(round trace + best version + held_out_run_count + hash) "
                               "and exit; --output-json is not required in this mode")
  ```
  and make `--output-json` optional (finalize mode does not read a round's output.json) —
  change its declaration from `required=True` to `required=False, default=None`. Then,
  immediately after the `args = parser.parse_args(argv)` line, insert the finalize branch
  BEFORE the existing per-round logic:
  ```python
      # --- finalize mode -------------------------------------------------------
      if args.final_report_out is not None:
          try:
              state = load_loop_state(args.loop_state)
          except (OSError, ValueError, json.JSONDecodeError) as exc:
              print(f"ERROR: {exc}")
              return 2
          if args.check_freeze:
              try:
                  assert_freeze(frozen_hash=state.get("extra_criteria_hash", ""),
                                current_text=state.get("extra_criteria"))
              except FreezeViolation as exc:
                  print(f"FREEZE VIOLATION: {exc}")
                  return 2
          report = build_final_report(state=state)
          with open(args.final_report_out, "w", encoding="utf-8") as f:
              json.dump(report, f, indent=2, ensure_ascii=False)
          print(f"best version: {report['best_version']}")
          print(f"held_out_run_count: {report['held_out_run_count']}")
          print(f"wrote {args.final_report_out}")
          return 0
  ```
  This sits before the `try: output = load_output_json(...)` block, so per-round mode is
  unchanged. (Per-round mode still requires `--output-json`; finalize mode does not.)
  Guard the per-round path so a missing `--output-json` in NON-finalize mode is a clean
  exit 2 rather than a `None`-path crash — replace the per-round load block:
  ```python
      try:
          output = load_output_json(args.output_json)
          state = load_loop_state(args.loop_state)
      except (OSError, ValueError, json.JSONDecodeError) as exc:
          print(f"ERROR: {exc}")
          return 2
  ```
  with:
  ```python
      if args.output_json is None:
          print("ERROR: --output-json is required unless --final-report-out is given")
          return 2
      try:
          output = load_output_json(args.output_json)
          state = load_loop_state(args.loop_state)
      except (OSError, ValueError, json.JSONDecodeError) as exc:
          print(f"ERROR: {exc}")
          return 2
  ```

- [ ] Run again; expect PASS:
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest tests.test_final_report -v
  ```
  Expected: `Ran 4 tests in ...` + `OK`.

- [ ] Run the FULL suite to confirm no regressions (now 36 tests: 4 load + 7 delta/best + 9 stop + 3 tally + 5 freeze + 4 cli + 4 final-report = 36):
  ```bash
  cd skills/prompt-engineering-improve/scripts && python3 -m unittest discover -s tests -v 2>&1 | tail -8
  ```
  Expected: `Ran 36 tests in ...` + `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/scripts && git commit -m "improve_step: deterministic finalize mode — final-report.json (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 10 — Author the SHARED `references/diagnosis.md` (cited by improve + prompt-evals-run)

This is a prose reference. Its "test" is a structural grep for the required sections + a documented scenario, not a unit test (spec/WRITING-PLANS: prose gets structural checks).

- [ ] Write `skills/prompt-engineering-improve/references/diagnosis.md`:
  ```markdown
  # Diagnosis: turning a scored report into the next move

  Shared reference. Read by **prompt-engineering-improve** (at the diagnose step of the
  loop) and cited by **prompt-evals-run** (its single-pass "what's wrong; fix and re-run,
  or invoke prompt-engineering-improve to automate the loop" step). This file is part of
  the group contract — it cannot move/rename without updating both readers
  (`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`).

  The numbers are computed by `improve_step.py` (mandatory-fail count, %-per-theme). This
  file is the *interpretation*: which theme dominates, whether the prompt or the criteria
  is at fault, and which technique rung to escalate to. The model names the dominant
  theme; the script supplies the tally; the table below maps theme → rung.

  ## 1. First gate: is it the prompt or the criteria? (criteria-vs-prompt guard)

  Before changing the prompt, decide whether the *dataset* is the problem. Route to
  `/je-dev-skills:prompt-evals-create-dataset` (do NOT rewrite the prompt) when:

  - The judge complains about content that is **not in the inputs** (the case can't be solved).
  - The rubric demands an **unstated style/format** the prompt was never told about.
  - The judge's rationale **conflicts with the rubric** (the rubric itself is ambiguous).
  - The answer needs **hidden domain knowledge** not provided to the prompt.

  **Investigate** (possible prompt non-determinism, not a fix yet) when failures are
  **inconsistent across similar cases** — same kind of input, divergent scores.

  Do **NOT** route to create-dataset (it is a real prompt fix) when the prompt:
  - **omitted instructions** the criteria clearly require,
  - **ignored a stated format**, or
  - **failed a recurring reasoning step**.

  ## 2. Mandatory criterion first

  Any case scoring **≤ 3** failed a mandatory criterion (the global `EXTRA_CRITERIA`, per
  `prompts/grading.md`: "Any violation of a MANDATORY criterion forces a score of 3 or
  below"). `improve_step.py` reports `mandatory_fail_count`. **Fix that gate before any
  secondary-criteria polish** — a single mandatory miss caps the score no matter how good
  the rest is.

  ## 3. Theme → next ladder rung

  Map the **dominant** failure theme (the one the tally shows across the most cases) to the
  cheapest technique rung that addresses it. Rungs are defined in
  `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/techniques.md`.

  | Dominant failure theme | Tally key | Next rung to escalate to |
  |---|---|---|
  | Mandatory-criterion failures (score ≤ 3) | `mandatory_fail_count` | Fix that gate **first** |
  | Missing required content | `missing_content` | Process steps; examples showing the requirement |
  | Format / structure drift, inconsistency | `format_structure` | XML structure + multishot examples |
  | Shallow / wrong reasoning on hard cases | `reasoning` | Adaptive thinking / reasoning scaffolding |
  | Tone / style off | `tone_style` | Role framing + output guidelines + examples |
  | Conflicting / ambiguous instructions | `conflicting` | Resolve the conflict (anti-pattern) — do not add more |

  ## 4. Priority + tie-break (the order improve_step.py applies)

  When several themes are present, address them in this priority order:

  1. Mandatory-criterion failures.
  2. Failures across **≥ 30%** of cases (`theme_pct >= 30`).
  3. Largest score-impacting weakness.
  4. Format / structure.
  5. Tone / style.

  **Ties → earliest item** in this list, unless the user overrides. Pick the **minimum**
  rung that fixes the diagnosed weakness — do not max out the ladder (see
  `rewrite-procedure.md`).

  ## 5. Hand-off to the rewrite

  Once the dominant theme and rung are chosen, follow
  `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`
  to produce the next prompt version + a short changelog of techniques applied.
  ```

- [ ] Structural check — assert the required sections + both reader citations + the theme keys match `improve_step.py`'s `THEME_KEYWORDS`/tally keys. Run:
  ```bash
  cd /home/dawti/je-dev-skills && \
    f=skills/prompt-engineering-improve/references/diagnosis.md && \
    grep -q "criteria-vs-prompt guard" "$f" && \
    grep -q "Mandatory criterion first" "$f" && \
    grep -q "Theme → next ladder rung" "$f" && \
    grep -q "Priority + tie-break" "$f" && \
    grep -q "mandatory_fail_count" "$f" && \
    grep -q "missing_content" "$f" && grep -q "format_structure" "$f" && \
    grep -q "reasoning" "$f" && grep -q "tone_style" "$f" && grep -q "conflicting" "$f" && \
    grep -q "prompt-evals-create-dataset" "$f" && \
    grep -q "rewrite-procedure.md" "$f" && \
    echo "DIAGNOSIS STRUCTURE OK"
  ```
  Expected: `DIAGNOSIS STRUCTURE OK`.

- [ ] Cross-check: every tally key in diagnosis.md exists in `improve_step.py` (no drift between the table and the code):
  ```bash
  cd /home/dawti/je-dev-skills && for k in missing_content format_structure reasoning tone_style conflicting; do \
    grep -q "\"$k\"" skills/prompt-engineering-improve/scripts/improve_step.py || { echo "MISSING KEY $k IN CODE"; exit 1; }; done && echo "TALLY KEYS MATCH CODE"
  ```
  Expected: `TALLY KEYS MATCH CODE`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/references/diagnosis.md && git commit -m "Add shared diagnosis.md reference (improve + prompt-evals-run)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 11 — Author `prompt-engineering-author/references/techniques.md` (the escalation ladder)

- [ ] Write `skills/prompt-engineering-author/references/techniques.md`:
  ```markdown
  # Technique catalogue — the escalation ladder

  An **escalation ladder**: cheapest / highest-leverage first. When authoring or
  rewriting, climb only as far as the diagnosed need requires (see
  `rewrite-procedure.md`: pick the minimum rungs; do not max out). Each rung names what
  it fixes and the smallest version that delivers it.

  ## Rung 1 — Clear & direct
  State the task, the deliverable, and its scope in plain imperative prose. Name the
  audience and the success condition. Most prompts that "don't work" are under-specified,
  not under-engineered. **Fixes:** vague output, off-scope answers, missing deliverable.

  ## Rung 2 — Output guidelines + process steps
  Specify the output shape (sections, length as a concrete range, ordering) and, when the
  task has a procedure, enumerate the steps the model should follow. Prefer concrete
  ranges ("3–5 bullets") over "be concise". **Fixes:** inconsistent length/shape, skipped
  sub-tasks, missing required content.

  ## Rung 3 — Examples (one-shot / multishot)
  Show 1–3 worked examples wrapped in `<example>` tags. Make them **diverse** and include
  a **corner case**. Examples teach format and edge handling faster than prose rules.
  Keep examples **consistent** with the current instructions (an example that contradicts
  an edited rule is an anti-pattern). **Fixes:** format drift, edge-case failures,
  "almost-right" structure.

  ## Rung 4 — XML structure (separate instructions from data)
  Wrap instructions, input data, and examples in distinct tags (`<instructions>`,
  `<input>`, `<examples>`) so the model never confuses what to *do* with what to *read*.
  **Fixes:** the model treating data as instructions, structure bleed, injection-ish
  confusion on long inputs.

  ## Rung 5 — Role framing (in-text, v1)
  Open with a one-line role ("You are an exacting nutrition coach…") **in the prompt text**
  (v1 uses in-text role, not a system/user split — see the skill's non-goals). A role
  calibrates tone, vocabulary, and rigor. **Fixes:** wrong register, tone/style off,
  under-rigorous answers.

  ## Rung 6 — Adaptive thinking / reasoning scaffolding
  Ask the model to reason before answering on genuinely hard cases — prefer **adaptive
  thinking** (let the model decide depth) and private reasoning over forced *exposed*
  chain-of-thought. Do **not** set manual `budget_tokens`; prefer `effort`. **Fixes:**
  shallow or wrong reasoning on the hard cases, arithmetic/logic slips.

  ## Rung 7 — Chaining (the single-shot boundary)
  When one prompt is doing two jobs (e.g. extract then summarize), splitting into a chain
  helps — but a chain is **beyond single-shot** (v1 scope). **Flag it**: recommend the
  user consider `workflow-design-*` / `agent-build-*` rather than cramming two jobs into
  one prompt.

  ## Rung 8 — Long-context tips
  For long inputs: put the **documents first, the query last**; reference data by tag;
  ask the model to quote the relevant span before answering. **Fixes:** lost-in-the-middle
  misses, ignored late instructions.

  ---

  **Climbing rule.** Start at the lowest rung that could fix the diagnosed weakness. Each
  added rung costs tokens and risks over-prompting (see `anti-patterns.md`). The
  diagnosis→rung map in
  `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md` tells
  you which rung a given failure theme points to.
  ```

- [ ] Structural check — all 8 rungs present + the climbing rule + cross-ref to diagnosis:
  ```bash
  cd /home/dawti/je-dev-skills && f=skills/prompt-engineering-author/references/techniques.md && \
    for r in "Rung 1" "Rung 2" "Rung 3" "Rung 4" "Rung 5" "Rung 6" "Rung 7" "Rung 8"; do \
      grep -q "## $r" "$f" || { echo "MISSING $r"; exit 1; }; done && \
    grep -q "Climbing rule" "$f" && grep -q "diagnosis.md" "$f" && \
    grep -qi "adaptive thinking" "$f" && grep -qi "do not max out\|minimum rungs" "$f" && \
    echo "TECHNIQUES STRUCTURE OK"
  ```
  Expected: `TECHNIQUES STRUCTURE OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-author/references/techniques.md && git commit -m "Add prompt-engineering-author techniques.md (escalation ladder)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 12 — Author `prompt-engineering-author/references/anti-patterns.md`

- [ ] Write `skills/prompt-engineering-author/references/anti-patterns.md`:
  ```markdown
  # Anti-patterns — what NOT to do

  Read alongside `techniques.md`. Every rung you climb risks one of these. The north-star
  thesis (shared with `workflow-design-*`): **don't ask the LLM to do what code should.**

  ## Say what to do, not what to avoid
  "Write 3–5 bullets" beats "don't be too long." Positive, concrete instructions are
  followed more reliably than prohibitions.

  ## No over-prompting
  Avoid shouting (`CRITICAL: YOU MUST ALWAYS…`), stacked all-caps, and threat-language.
  It does not increase compliance and it crowds out the actual instruction. State the
  requirement once, plainly.

  ## Keep examples consistent with the instructions
  When you edit a rule, **update every example** that demonstrated the old rule. A
  contradicting example is worse than no example — the model follows the example.

  ## Concrete ranges over vague adjectives
  "Concise", "detailed", "professional" are unmeasurable. Give a range, a section list,
  a word budget, or a worked example.

  ## Don't ask the LLM to do what code should (the north star)
  If a step is deterministic — validation, formatting, arithmetic on given numbers,
  key-set checks — do it in code, not in the prompt. The plugin's whole stance: code for
  the reliable/repeatable/auditable; the model only for genuinely open-ended judgment.
  A prompt that says "carefully count and verify the JSON keys" should be a validator.

  ## Resolve conflicting rules
  Two instructions that can't both hold ("be exhaustive" + "answer in one sentence") make
  output unpredictable. Find the conflict and pick one; don't paper over it with more rules.

  ## Prefer private reasoning over forced exposed chain-of-thought
  Let the model reason adaptively; don't force a verbose visible "Let me think step by
  step…" preamble into the user-facing output unless the output spec asks for it.

  ## Model-aware by construction
  - **No assistant prefill** — prefilling the last assistant turn 400s on Claude Opus 4.7+
    (and the framework already moved off it).
  - **No manual `budget_tokens`** — prefer adaptive thinking + `effort`.
  - **No sampling-param fiddling** for Opus 4.7+ (temperature/top_p/top_k are rejected).

  These are best-practice-only and current as of 2026-05; volatile model specifics belong
  in a dated citations reference, not hardcoded into a prompt.
  ```

- [ ] Structural check:
  ```bash
  cd /home/dawti/je-dev-skills && f=skills/prompt-engineering-author/references/anti-patterns.md && \
    grep -qi "Say what to do" "$f" && grep -qi "over-prompting" "$f" && \
    grep -qi "examples consistent" "$f" && grep -qi "Concrete ranges" "$f" && \
    grep -qi "do what code should" "$f" && grep -qi "conflicting rules\|Resolve conflict" "$f" && \
    grep -qi "assistant prefill" "$f" && grep -qi "budget_tokens" "$f" && \
    echo "ANTI-PATTERNS STRUCTURE OK"
  ```
  Expected: `ANTI-PATTERNS STRUCTURE OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-author/references/anti-patterns.md && git commit -m "Add prompt-engineering-author anti-patterns.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 13 — Author the SHARED `prompt-engineering-author/references/rewrite-procedure.md`

- [ ] Write `skills/prompt-engineering-author/references/rewrite-procedure.md`:
  ```markdown
  # Rewrite procedure — the shared seam

  The single home for *how* to produce or improve a prompt. Read by **two** callers:
  `prompt-engineering-author` Mode B (improve an existing prompt) **and**
  `prompt-engineering-improve`'s rewrite step (after diagnosis). Both read this file by
  `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`.
  It is part of the group contract — moving/renaming it breaks `prompt-engineering-improve`.

  ## Inputs to a rewrite
  - The current prompt text (or, for Mode A generate, the task description).
  - The diagnosed weakness (from a user-supplied issue list, or from
    `prompt-engineering-improve`'s diagnosis: the dominant theme + the chosen ladder rung).
  - The technique ladder (`techniques.md`) and the constraints (`anti-patterns.md`).

  ## The procedure
  1. **Name the single most important fix.** One dominant weakness per round. If the
     diagnosis flags a **mandatory-criterion failure**, that is the fix — nothing else
     matters until the gate passes.
  2. **Pick the MINIMUM rungs that fix it.** Use the diagnosis→rung map. Do **not** max
     out the ladder; every added rung costs tokens and risks over-prompting. Prefer the
     lowest rung that plausibly resolves the diagnosed theme.
  3. **Apply the rung(s)** to the prompt text, obeying every anti-pattern: say what to do,
     keep examples consistent with edited instructions, concrete ranges, no over-prompting,
     resolve conflicts, prefer adaptive thinking over forced exposed chain-of-thought.
  4. **Preserve the placeholders.** The set of `{placeholder}` variables must stay exactly
     the closed key set the dataset uses — do not add, drop, or rename a placeholder during
     a rewrite (that breaks the frozen dataset's contract; if the input set must change,
     that is a `prompt-evals-create-dataset` change, not a rewrite).
  5. **Soften imperatives.** Replace shouting/threats with plain, single statements.
  6. **Emit two things:** the rewritten prompt (Layer-1 text) and a **short changelog** —
     one line per technique applied and which weakness it targets.

  ## Output contract
  - **The prompt** as a text file. In standalone author use, write to a path the user
    chooses (never under `./evals`). In the improve loop, write the candidate to
    `evals/prompts_under_test/<name>.vN.md`, then copy the chosen candidate into
    `evals/prompts_under_test/<name>.current.md` *before* measuring.
  - **The changelog** as a short bullet list (technique → weakness targeted), shown to the
    user / recorded in the round's trace.

  ## What stays the model's job vs. code's job
  The model **names the dominant theme and writes the new prompt text**. The float math,
  argmax, stop verdict, tally, and `EXTRA_CRITERIA` freeze are `improve_step.py`'s job —
  never re-derive them in prose.
  ```

- [ ] Structural check — the load-bearing constraints are present:
  ```bash
  cd /home/dawti/je-dev-skills && f=skills/prompt-engineering-author/references/rewrite-procedure.md && \
    grep -qi "minimum rungs" "$f" && grep -qi "do not max out\|don't max out" "$f" && \
    grep -qi "Preserve the placeholders\|closed key set" "$f" && \
    grep -qi "changelog" "$f" && grep -qi "<name>.current.md" "$f" && \
    grep -qi "mandatory-criterion failure" "$f" && \
    grep -qi "improve_step.py" "$f" && echo "REWRITE-PROCEDURE STRUCTURE OK"
  ```
  Expected: `REWRITE-PROCEDURE STRUCTURE OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-author/references/rewrite-procedure.md && git commit -m "Add shared rewrite-procedure.md (author Mode B + improve)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 14 — Author `prompt-engineering-author/SKILL.md`

- [ ] Write `skills/prompt-engineering-author/SKILL.md`:
  ```markdown
  ---
  name: prompt-engineering-author
  description: This skill should be used when the user asks to "write a prompt", "author a prompt", "draft a system prompt", "improve this prompt", "refactor my prompt", "make this prompt better", "apply prompt best practices", or wants a strong single-shot prompt built from a task description or an existing prompt refactored against best practices. Standalone and eval-free — it never touches ./evals.
  argument-hint: "[task description to author from, OR path to an existing prompt to improve]"
  allowed-tools: Read, Write, Edit, Glob
  version: 0.1.0
  ---

  # Prompt Engineering: Author

  Turn a task (or an existing prompt) into a well-built **single-shot** prompt. Standalone,
  eval-free, fast. **Never touches `./evals`.** To then measure and iterate the prompt,
  hand it to `/je-dev-skills:prompt-engineering-improve` (which needs a frozen dataset).

  This SKILL is a table of contents. **Load each reference only when its step is reached** —
  never all up front.

  ## Modes

  - **Mode A — generate:** a task description (+ optional input variables / output
    expectations) → a new prompt.
  - **Mode B — improve:** an existing prompt (+ optional issue list, or a diagnosis handed
    over from `prompt-engineering-improve`) → a refactored prompt + a short changelog.

  Pick the mode from the argument: a task description → A; a path to / paste of an existing
  prompt → B.

  ## Procedure

  ### Mode A — generate
  1. **Clarify the task.** Name the deliverable, its scope, the audience, and the success
     condition. Identify the input variables — each becomes a `{placeholder}`. Identify the
     output shape (sections, length as a concrete range).
  2. **Climb the ladder only as far as needed.** Read
     `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/techniques.md` and
     start at Rung 1, adding rungs only if the task genuinely needs them.
  3. **Obey the constraints.** Read
     `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/anti-patterns.md`
     and apply it as you write.
  4. **Emit the prompt** as a text file at a path the user chooses, plus the list of
     declared `{placeholder}` variables. Do **not** write anything under `./evals`.

  ### Mode B — improve
  1. **Gather the diagnosis.** Use the user's issue list, or the dominant theme + chosen
     rung handed over from `prompt-engineering-improve`.
  2. **Follow the shared rewrite procedure.** Read and follow
     `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`
     (which itself pulls in `techniques.md` + `anti-patterns.md`).
  3. **Emit** the refactored prompt + a short changelog (technique → weakness targeted).
     Preserve the prompt's `{placeholder}` set exactly.

  ## Definition of done

  - A valid prompt text file exists at the user-chosen path with its declared
    `{placeholder}` variables listed back to the user.
  - **Mode B** additionally emits a changelog of techniques applied.
  - **Nothing under `./evals` was created or modified** (this skill is eval-free).

  ## Boundaries

  - **Single-shot prompts only** in v1. If the task needs two jobs (extract→summarize) or
    multiple tools, that is chaining/agentic — flag it and point to `workflow-design-*` /
    `agent-build-*`, do not cram it into one prompt (techniques.md Rung 7).
  - This skill does **not** define success criteria or build datasets (that is
    `prompt-evals-create-dataset`) and does **not** run evals (that is
    `prompt-evals-run` / `prompt-engineering-improve`).
  ```

- [ ] Structural / frontmatter check:
  ```bash
  cd /home/dawti/je-dev-skills && f=skills/prompt-engineering-author/SKILL.md && \
    head -1 "$f" | grep -q '^---$' && \
    grep -q "^name: prompt-engineering-author$" "$f" && \
    grep -q "^allowed-tools: Read, Write, Edit, Glob$" "$f" && \
    grep -q "^argument-hint:" "$f" && grep -q "^version:" "$f" && \
    grep -q "Mode A" "$f" && grep -q "Mode B" "$f" && \
    grep -q "never touches" "$f" && grep -q "techniques.md" "$f" && \
    grep -q "anti-patterns.md" "$f" && grep -q "rewrite-procedure.md" "$f" && \
    grep -q "Definition of done" "$f" && echo "AUTHOR SKILL STRUCTURE OK"
  ```
  Expected: `AUTHOR SKILL STRUCTURE OK`.

- [ ] Scenario check (manual, documented) — confirms the eval-free boundary is honored. Document in the commit body: "Mode A on a task description writes a prompt + lists placeholders to a user path; Mode B on a prompt+issues writes a refactor + changelog; `git status ./evals` shows no changes." Verify the allowed-tools exclude Bash (so it physically cannot run evals):
  ```bash
  cd /home/dawti/je-dev-skills && grep "^allowed-tools:" skills/prompt-engineering-author/SKILL.md | grep -vq "Bash" && echo "NO BASH -> CANNOT RUN EVALS: OK"
  ```
  Expected: `NO BASH -> CANNOT RUN EVALS: OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-author/SKILL.md && git commit -m "Add prompt-engineering-author SKILL.md (modes A/B, progressive disclosure)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 15 — Author `prompt-engineering-improve/SKILL.md`

- [ ] Write `skills/prompt-engineering-improve/SKILL.md`:
  ```markdown
  ---
  name: prompt-engineering-improve
  description: This skill should be used when the user asks to "improve my prompt with evals", "iterate on my prompt", "make my prompt measurably better", "run the improvement loop", "optimize my prompt against the dataset", or wants an eval-driven iterate→measure→diagnose→rewrite loop with explicit stopping rules. It orchestrates the existing ./evals framework; every numeric decision (delta, best version, stop verdict, diagnosis tally) is computed by a deterministic helper.
  argument-hint: "[prompt name under evals/prompts_under_test, e.g. meal-plan]"
  allowed-tools: Bash, Read, Write, Edit, Glob
  version: 0.1.0
  ---

  # Prompt Engineering: Improve (the eval-driven loop)

  Drive an **iterate → measure → diagnose → rewrite** loop that makes a prompt
  *measurably* better, with explicit, **deterministically-evaluated** stopping rules. This
  skill **orchestrates** the eval framework — it never reimplements it. Every numeric
  decision (per-round delta, running-best version, the continue/stop verdict, the diagnosis
  tally, the `EXTRA_CRITERIA` freeze) is computed by `scripts/improve_step.py`; the model's
  only jobs are **naming the dominant failure theme** and **the rewrite**.

  This SKILL is a table of contents. **Load each reference only at its step** — never all
  four up front.

  ## Preconditions

  - `./evals` exists (else stop and route to `/je-dev-skills:prompt-evals-setup`).
  - A **frozen dataset** exists in `evals/datasets/` (else route to
    `/je-dev-skills:prompt-evals-create-dataset`). This skill owns **no** eval engine and
    does **not** define success criteria or build datasets.
  - The prompt-under-test lives at `evals/prompts_under_test/<name>.current.md`. On first
    use, migrate any custom `run_prompt` per the substrate's migration note (extract the
    prompt text to `<name>.current.md`; map system/user content to subagent options; route
    raw `messages.create`/`max_tokens`/tools to the keyed fallback; **show the diff and get
    explicit confirmation** before the first eval).

  ## Execution paths (from the architecture spec — consumed, not redefined)

  - **No-key path (canonical, `EXECUTION_MODE=in_claude_code`):** `/je-dev-skills:prompt-evals-run`
    drives measurement by dispatching execute+grade **subagents** per case (session auth, no
    API key), and `python -m evals.aggregate --run-label <label> --verdicts-dir <dir> --dataset <path>`
    writes `evals/runs/<label>/{output.json,output.html}`. **Single-shot only** (subagents
    can't nest). Auto mode is no-key only while an interactive session drives it.
  - **Keyed fallback (`EXECUTION_MODE=anthropic_api`, headless/CI):** `python3 -m evals.run_eval evaluate`
    runs `run_evaluation` in-process with `ANTHROPIC_API_KEY`; supports agentic prompts.

  ## Loop parameters (one home)

  The five loop params live as a **constants block at the top of `evals/run_eval.py`**;
  `pass_threshold` references `config.PASS_THRESHOLD` (7). `improve_step.py` reads them
  from the loop-state JSON and stamps the resolved values into each `delta.json` + the
  final report. Defaults: `pass_rate_target=0.80`, `max_rounds=3`, `epsilon=0.25`,
  `diminishing_return_rounds=2`, `regression_band=0.5`.

  ## Token cost & optional cheap subset (optimization)

  One full evaluation ≈ `2N` model calls (N execute + N grade); a loop is baseline + N re-evals
  + 1 held-out ≈ `(N+2)` full evaluations (single-shot; agentic execute is unbounded per case on
  the keyed path). **Optional:** to cut recurring cost, mid-loop *diagnosis* may run against a
  **deterministically sampled K-case subset** written from the frozen dataset (a helper writes the
  subset and passes it as `--dataset`); always run the **full** frozen set at every decision point
  (delta / stop verdict / version selection). This is an optimization, not required.

  ## One round

  ```
  baseline:  prompt-evals-run → evals/runs/improve-<name>-round-NN/output.json
  diagnose:  improve_step.py tallies mandatory-fails + %-per-theme → model names the dominant theme
     ├─ criteria problem? (diagnosis.md guard) → STOP, route to prompt-evals-create-dataset
  select:    map theme → next ladder rung (diagnosis.md table)
  rewrite:   follow rewrite-procedure.md + the diagnosis → <name>.vN+1.md → copy into <name>.current.md
  re-eval:   prompt-evals-run on the SAME frozen dataset → new output.json
  delta:     improve_step.py → delta + best + continue/stop verdict
  ```

  ### Step detail

  1. **Baseline.** Run `/je-dev-skills:prompt-evals-run` with
     `run_label=improve-<name>-round-00` against the frozen dataset. Build the **loop-state
     JSON** (`evals/improve/<name>/<timestamp>/loop-state.json`): the resolved `params`,
     the frozen `extra_criteria` + its hash (`improve_step.py`'s `extra_criteria_hash`),
     `current_version`, and an empty `rounds` list.
  2. **Diagnose.** Read
     `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`. Run
     the helper to get the tally:
     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts/improve_step.py \
       --output-json evals/runs/improve-<name>-round-NN/output.json \
       --loop-state evals/improve/<name>/<timestamp>/loop-state.json \
       --delta-out evals/improve/<name>/<timestamp>/round-NN/delta.json
     ```
     Use the tally (mandatory-fail count, %-per-theme) to **name the dominant theme**. Apply
     the criteria-vs-prompt guard: if it's a criteria problem, **STOP** and route to
     `prompt-evals-create-dataset`.
  3. **Select.** Map the dominant theme → the minimum ladder rung (diagnosis.md table +
     priority/tie-break).
  4. **Rewrite.** Read and follow
     `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`
     (it pulls in `techniques.md` + `anti-patterns.md`). Write the candidate to
     `evals/prompts_under_test/<name>.vN+1.md`, then **copy it into `<name>.current.md`**
     before re-measuring. Never change the `{placeholder}` set.
  5. **Re-eval + decide.** Re-run `/je-dev-skills:prompt-evals-run` with
     `run_label=improve-<name>-round-NN` on the **same** frozen dataset, append the new
     round's `{version, avg, pass_rate}` to the loop-state `rounds`, then run
     `improve_step.py` again. **Act on its verdict, do not recompute it:** exit 0 →
     continue; exit 1 → stop (a rule fired; the printed `verdict.rule` says which) and keep
     the printed `best.version`; exit 2 → bad input or freeze violation.

  ## Hybrid control

  - **Checkpointed (default):** pause each round with the diagnosis + chosen technique +
    delta + remaining weaknesses; ask the user continue / stop / adjust.
  - **Auto, up to N rounds:** stream each delta; stop early on the helper's verdict; then
    return to checkpointed. Auto mode is **no-key only while an interactive session drives
    it** (subagent dispatch). A genuinely unattended/CI auto-loop uses the keyed
    `anthropic_api` fallback and requires `ANTHROPIC_API_KEY`.

  ## Stopping rules (all evaluated by improve_step.py)

  threshold (avg ≥ `pass_threshold`) · pass_rate (≥ `pass_rate_target`) · regression
  (> `regression_band` below best → discard the round, keep best) · diminishing-returns
  (delta < ε for K consecutive rounds) · budget cap (`max_rounds`). If several fire, the
  helper reports the first by priority and you keep the **best** version.

  ## Held-out validation (final, at most once)

  After the loop, run **once** against a separate, **independent** held-out dataset (distinct
  scenarios — not a near-duplicate). Never use it for diagnosis/rewrite/selection. Before
  any held-out run, `EXTRA_CRITERIA` is **frozen** — run `improve_step.py --check-freeze`
  (exit 2 = violation → the held-out claim is forfeit; regenerate a held-out set). Record
  `held_out_run_count` (must stay ≤ 1) in the final report. Absent held-out set → mark final
  validation **skipped, not failed**.

  ## Finalize (deterministic — never hand-serialized)

  After the loop stops, write the final report **with the helper, not by hand**:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts/improve_step.py \
    --loop-state evals/improve/<name>/<timestamp>/loop-state.json \
    --final-report-out evals/improve/<name>/<timestamp>/final-report.json
  ```
  This stamps the resolved loop params, the round-by-round trace, the winning `best.version`,
  `held_out_run_count`, and the frozen `EXTRA_CRITERIA` hash into `final-report.json` (exit 2 =
  freeze violation). The model never serializes these by hand.

  ## Output / trace

  ```
  evals/improve/<name>/<timestamp>/
    loop-state.json
    round-00-baseline/ { delta.json, diagnosis notes, run_dir → ../../../runs/improve-<name>-round-00 }
    round-01/          { <name>.v2.md (or id), delta.json, technique, decision, run_dir → … }
    ...
    final-report.md    (round-by-round trace, winning version, held-out result or "skipped")
    final-report.json  (resolved loop params + held_out_run_count + EXTRA_CRITERIA hash)
  ```

  Versioned prompt files (`<name>.vN.md` + `<name>.current.md`) + the trace + a final report.

  ## Definition of done

  - The loop ran with each numeric decision produced by `improve_step.py` (not by hand).
  - A winning version is named (the helper's `best.version`), with the trace + final report.
  - If a criteria problem was found, the user was routed to `prompt-evals-create-dataset`
    and the loop stopped.
  - Held-out validation ran at most once (recorded) or is marked "skipped, not failed".

  ## Offline check (no API key)

  The deterministic helper is fully offline-tested:
  ```bash
  cd ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts && \
    python3 -m unittest discover -s tests
  ```

  ## Cross-skill reference coupling (flag)

  This skill reads `rewrite-procedure.md` + `techniques.md` + `anti-patterns.md` from
  **`prompt-engineering-author`**, and its own `references/diagnosis.md` is read by
  **`prompt-evals-run`**. These `${CLAUDE_PLUGIN_ROOT}` path dependencies are part of the
  group contract — the files cannot move/rename without updating every reader.
  ```

- [ ] Structural / frontmatter check:
  ```bash
  cd /home/dawti/je-dev-skills && f=skills/prompt-engineering-improve/SKILL.md && \
    head -1 "$f" | grep -q '^---$' && \
    grep -q "^name: prompt-engineering-improve$" "$f" && \
    grep -q "^allowed-tools: Bash, Read, Write, Edit, Glob$" "$f" && \
    grep -q "Preconditions" "$f" && grep -q "improve_step.py" "$f" && \
    grep -q "diagnosis.md" "$f" && grep -q "rewrite-procedure.md" "$f" && \
    grep -q "improve-<name>-round-NN" "$f" && \
    grep -q "Held-out" "$f" && grep -q "check-freeze" "$f" && \
    grep -q "Cross-skill reference coupling" "$f" && \
    grep -q "aggregate" "$f" && grep -q "Offline check" "$f" && \
    grep -q "final-report-out" "$f" && grep -q "Finalize" "$f" && \
    echo "IMPROVE SKILL STRUCTURE OK"
  ```
  Expected: `IMPROVE SKILL STRUCTURE OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-engineering-improve/SKILL.md && git commit -m "Add prompt-engineering-improve SKILL.md (deterministic eval-driven loop)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 16 — Add the loop-param constants block + `run_label` arg to `run_eval.py`

This edits the vendored framework source. **Merge note:** the substrate plan rewrites
`run_prompt`/`main()` for mode-awareness and the prompt-prep glue in this same file. THIS
plan adds (a) the loop-param constants block and (b) the `run_label` arg threaded through
`main()`. The edits below are written to apply cleanly whether or not the substrate edits
are present yet (they touch disjoint regions: the constants block goes after the
`EXTRA_CRITERIA` area; the `run_label` arg goes into the `evaluate` branch and `main()`'s
signature). If the substrate plan already added a `run_label` thread, skip step (b) and
keep only the constants block.

- [ ] Read the current file first (required before Edit), confirming the exact text at the
  `EXTRA_CRITERIA`/`PROCESS_CRITERIA` region and the `evaluate` branch:
  ```bash
  cd /home/dawti/je-dev-skills && python3 -c "print(open('skills/prompt-evals-setup/framework/evals/run_eval.py').read())" | sed -n '19,89p'
  ```

- [ ] Add the loop-param constants block. Using the Edit tool, insert immediately AFTER the
  `DATASET_FILE = ...` / `NUM_CASES = ...` lines (the end of the "Describe the task" block),
  the following:
  ```python

  # --- Loop parameters (prompt-engineering-improve) ----------------------------
  # The five loop params live HERE (not config.py) — the existing per-project edit
  # surface. improve_step.py reads them from the loop-state JSON it is handed and
  # stamps the resolved values into each delta.json + the final report.
  # pass_threshold is the one intentional reference back to config.PASS_THRESHOLD.
  LOOP_PARAMS = {
      "pass_threshold": config.PASS_THRESHOLD,  # 7 — avg-score bar (referenced, not redefined)
      "pass_rate_target": 0.80,                 # fraction of cases >= threshold to target
      "max_rounds": 3,                          # hard cap on improvement rounds
      "epsilon": 0.25,                          # min per-round avg gain that counts as progress
      "diminishing_return_rounds": 2,           # consecutive sub-epsilon rounds before stopping
      "regression_band": 0.5,                   # a round regresses only if > band below best
  }
  ```

- [ ] Thread `run_label` through `main()` (skip if the substrate plan already did this).
  Change the `main` signature and the `evaluate` branch. Replace:
  ```python
  def main(argv: list[str]) -> int:
      command = argv[1] if len(argv) > 1 else "evaluate"
      evaluator = build_evaluator()
  ```
  with:
  ```python
  def main(argv: list[str]) -> int:
      command = argv[1] if len(argv) > 1 else "evaluate"
      # Optional 3rd positional arg: a run_label so each improve round names its run dir
      # deterministically (improve-<name>-round-NN). run_evaluation already accepts it.
      run_label = argv[2] if len(argv) > 2 else None
      evaluator = build_evaluator()
  ```
  and replace the `evaluate` branch body:
  ```python
      if command == "evaluate":
          evaluator.run_evaluation(
              run_function=run_prompt,
              dataset_file=DATASET_FILE,
              extra_criteria=EXTRA_CRITERIA,
              process_criteria=PROCESS_CRITERIA,
          )
          return 0
  ```
  with:
  ```python
      if command == "evaluate":
          evaluator.run_evaluation(
              run_function=run_prompt,
              dataset_file=DATASET_FILE,
              extra_criteria=EXTRA_CRITERIA,
              process_criteria=PROCESS_CRITERIA,
              run_label=run_label,
          )
          return 0
  ```

- [ ] Verify the file still imports cleanly and the constants resolve (offline, no key — it
  imports `config` only, does not call the SDK):
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
    python3 -c "import evals.run_eval as r; print(sorted(r.LOOP_PARAMS)); assert r.LOOP_PARAMS['pass_threshold'] == 7; assert r.LOOP_PARAMS['regression_band'] == 0.5; print('LOOP_PARAMS OK')"
  ```
  Expected: prints the sorted keys then `LOOP_PARAMS OK`. (`import evals.run_eval` does not
  call the SDK at import time — the SDK is only touched inside `run_prompt`/`build_evaluator`.)

- [ ] Confirm the framework core test suite still passes (composition invariant: core unchanged):
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
    python3 -m unittest discover -s evals/tests -t . 2>&1 | tail -5
  ```
  Expected: `OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-evals-setup/framework/evals/run_eval.py && git commit -m "run_eval.py: add loop-param constants block + run_label arg

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 17 — Re-scope `prompt-evals-run/SKILL.md` §4 to single-pass + cite diagnosis.md

**Merge note:** the substrate plan rewrites this file's run procedure (Steps 1–3) into the
Path A subagent-dispatch flow. THIS plan owns ONLY the §4 "Diagnose and iterate" re-scope +
the `diagnosis.md` citation. Land both in one coherent file. The edit below targets the
current §4 block; if the substrate plan reworded surrounding steps, re-anchor on the
"### 4. Diagnose and iterate" heading.

- [ ] Read the current §4 block (required before Edit):
  ```bash
  cd /home/dawti/je-dev-skills && sed -n '/### 4. Diagnose and iterate/,/## Definition of done/p' skills/prompt-evals-run/SKILL.md
  ```

- [ ] Replace the §4 body. Using the Edit tool, replace the block from `### 4. Diagnose and iterate`
  up to (but not including) `## Definition of done` with:
  ```markdown
  ### 4. Diagnose (single pass) and choose the next move

  This is a **single-pass** diagnosis — "here's what's wrong; fix and re-run, **or invoke
  `/je-dev-skills:prompt-engineering-improve` to automate the multi-round loop**." The
  multi-round loop, stopping rules, and version selection belong to
  `prompt-engineering-improve`, not here.

  Read the shared diagnosis reference:
  `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`. It is
  the single home for the **criteria-vs-prompt guard** and the **mandatory-criterion-first**
  rule, and it maps failure themes → technique rungs. Use it to decide:

  - **Real output flaws** (the prompt omitted instructions, ignored a stated format, or
    failed a recurring reasoning step) → fix the prompt and re-run against the **same**
    dataset; or hand off to `prompt-engineering-improve` for a measured loop.
  - **Bad criteria** (off-scope, demands unstated content/style, needs hidden knowledge) →
    the dataset is the problem; fix via `/je-dev-skills:prompt-evals-create-dataset`.
  - **Mandatory-criterion failures** cap a score at ≤ 3 — check `extra_criteria` first when
    scores cluster low.

  Beware judge/executor leakage: keep `JUDGE_MODEL` strong and **distinct** from
  `EXECUTOR_MODEL`. For higher confidence on close calls, widen the dataset.

  ```

- [ ] Structural check — §4 now single-pass + cites diagnosis.md + points at improve:
  ```bash
  cd /home/dawti/je-dev-skills && f=skills/prompt-evals-run/SKILL.md && \
    grep -q "single-pass" "$f" && \
    grep -q "prompt-engineering-improve/references/diagnosis.md" "$f" && \
    grep -q "prompt-engineering-improve to automate" "$f" && \
    grep -q "criteria-vs-prompt guard" "$f" && \
    echo "PROMPT-EVALS-RUN §4 RE-SCOPE OK"
  ```
  Expected: `PROMPT-EVALS-RUN §4 RE-SCOPE OK`.

- [ ] Commit:
  ```bash
  git add skills/prompt-evals-run/SKILL.md && git commit -m "prompt-evals-run: re-scope §4 to single-pass diagnosis + cite diagnosis.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 18 — Wire the group into `README.md` + `.claude-plugin/plugin.json`

**Merge note:** the substrate plan rewrites README/plugin.json into the unified
design→author→build→measure→improve lifecycle. THIS plan adds the `prompt-engineering-*`
group rows/keywords. If the substrate plan already added the unified narrative, only add the
two skill rows + the `prompt-engineering` keyword refinements; do not re-create islands.

- [ ] Read `README.md` (already read above) and add a `prompt-engineering-*` group section.
  Using the Edit tool, insert AFTER the "## Workflow Design skills" block (after its
  lifecycle paragraph ending in `docs/WORKFLOW_DESIGN_SPEC.md).`) the following:
  ```markdown

  ## Prompt Engineering skills

  | Skill | Invoke | What it does |
  |-------|--------|--------------|
  | `prompt-engineering-author` | `/je-dev-skills:prompt-engineering-author` | Author a strong single-shot prompt from a task description, or refactor an existing prompt against best practices. Standalone, eval-free — never touches `./evals`. |
  | `prompt-engineering-improve` | `/je-dev-skills:prompt-engineering-improve` | Drive an eval-driven iterate→measure→diagnose→rewrite loop with explicit, deterministically-evaluated stopping rules, on top of the `prompt-evals-*` substrate. |

  These sit on top of `prompt-evals-*`: **author** a prompt, then **improve** it through a
  measured loop. Every numeric decision in the loop (delta, best version, stop verdict,
  diagnosis tally, `EXTRA_CRITERIA` freeze) is computed by a deterministic helper
  (`improve_step.py`) — code, not prose. The improve loop runs on the no-API-key interactive
  path (subagent dispatch) by default, with a keyed fallback for headless/CI. See the design
  spec at
  [docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md](docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md).
  ```

- [ ] Update `.claude-plugin/plugin.json`. Read it (already read above), then update
  `description` and `keywords`. Using the Edit tool, replace the `description` line with one
  that names the prompt-engineering group, and the `keywords` array to add
  `"prompt-authoring"` and `"prompt-improvement"`:
  ```json
    "description": "A personal collection of Claude Code skills. Includes a prompt/agent evaluation lifecycle (prompt-evals-*: setup, create-dataset, run), a prompt-engineering lifecycle (prompt-engineering-*: author, improve) that writes and eval-improves prompts, and a workflow-design lifecycle (workflow-design-*: interview, validate) that turns an idea into a checked workflow blueprint.",
  ```
  and
  ```json
    "keywords": ["evaluation", "evals", "prompt-engineering", "prompt-authoring", "prompt-improvement", "llm-as-judge", "testing", "agents", "workflow", "orchestration", "blueprint", "agent-design"]
  ```

- [ ] Validate the JSON is well-formed:
  ```bash
  cd /home/dawti/je-dev-skills && python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert 'prompt-authoring' in d['keywords']; assert 'prompt-engineering-' in d['description'] or 'prompt-engineering' in d['description']; print('PLUGIN.JSON OK')"
  ```
  Expected: `PLUGIN.JSON OK`.

- [ ] Structural check on README:
  ```bash
  cd /home/dawti/je-dev-skills && grep -q "## Prompt Engineering skills" README.md && \
    grep -q "prompt-engineering-author" README.md && \
    grep -q "prompt-engineering-improve" README.md && \
    grep -q "deterministic helper" README.md && echo "README WIRING OK"
  ```
  Expected: `README WIRING OK`.

- [ ] Commit:
  ```bash
  git add README.md .claude-plugin/plugin.json && git commit -m "Wire prompt-engineering-* group into README + plugin.json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

### Task 19 — Full-suite verification (gate before done)

- [ ] Run the complete `improve_step.py` suite once more from the scripts dir:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-engineering-improve/scripts && \
    python3 -m unittest discover -s tests -v 2>&1 | tail -8
  ```
  Expected: `Ran 36 tests in ...` + `OK`.

- [ ] Confirm the framework core suite is still green (composition invariant):
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
    python3 -m unittest discover -s evals/tests -t . 2>&1 | tail -3
  ```
  Expected: `OK`.

- [ ] Confirm the composition invariant by diffing the framework core against `main` — only
  `run_eval.py` may have changed under `framework/evals/` (NOT anything in `evaluator/` or
  `prompts/`):
  ```bash
  cd /home/dawti/je-dev-skills && git fetch -q origin main && \
    git diff --name-only origin/main...HEAD -- skills/prompt-evals-setup/framework/evals/ | sort
  ```
  Expected: the ONLY line under `framework/evals/` is `skills/prompt-evals-setup/framework/evals/run_eval.py`.
  If anything under `evaluator/` or `prompts/` appears, STOP — the invariant is broken.

- [ ] Confirm `prompt-engineering-author` never gained Bash (eval-free boundary):
  ```bash
  cd /home/dawti/je-dev-skills && grep "^allowed-tools:" skills/prompt-engineering-author/SKILL.md
  ```
  Expected: `allowed-tools: Read, Write, Edit, Glob` (no `Bash`).

- [ ] Final commit (if any uncommitted verification artifacts remain — there should be none;
  this step is a guard):
  ```bash
  cd /home/dawti/je-dev-skills && git status --porcelain
  ```
  Expected: empty (all work committed in prior tasks).

---

## Coverage map (spec § → task)

- prompt-eng spec §5 (author skill) → Tasks 11, 12, 13, 14.
- prompt-eng spec §6 (improve loop + `improve_step.py` determinism + loop params + stopping + held-out + freeze) → Tasks 2–9 (helper incl. finalize), 10 (diagnosis), 15 (SKILL), 16 (loop params).
- prompt-eng spec §4 (file seam; prompt-prep glue / aggregate are substrate-owned — referenced only) → Tasks 15, 17 (prose pointers).
- prompt-eng spec §3 / §7 (boundaries, cross-skill coupling, wiring) → Tasks 14, 15, 17, 18.
- prompt-eng spec §9 DoD (unit-tested helper; behavioral criteria) → Tasks 2–9 (tests), 14/15 (skill behaviors), 19 (gate).
- arch spec §2.2 (two paths) / §2.4 (single-shot no-key) → referenced in Tasks 15, 17.
- WORKFLOW_DESIGN_SPEC §4 four-part contract → referenced via north-star anti-pattern (Task 12) and the agent-build hand-off note (Task 14); not re-implemented here.
```