# Eval Live-Path Integration — Specification & Design

A design contract for wiring the **already-shipped deterministic eval cores** into the
**live eval run path** and surfacing their results in the `prompt-evals-run` report.

> **Tickets covered:** [T-013] wire variance/run\_delta into the run report (phase
> `review-layers`), [T-014] live run-path assertion *gating* (phase `backlog`),
> [T-019] live run-path K-run variance orchestration (phase `backlog`).
>
> **Origin.** All three were deferred from the live-path integration noted in
> `PROMPT_EVAL_FRAMEWORK_SPEC.md` §13 ("v0.2 hardening — shipped"): the cores +
> offline CLIs shipped; *wiring them into `run_evaluation`* did not. This spec is the
> reference an implementation plan is derived from.

---

## 1. Purpose

The v0.2 hardening pass shipped four deterministic modules at the vendored `evals/`
top level, each with offline `unittest` fixtures and a `python -m evals.<module>` CLI:
`assertions.py`, `variance.py`, `run_delta.py`, `criteria_audit.py`. Today they are
**offline tools over existing `output.json` files** — they are *not* part of a live
run. A developer must run them by hand after a run completes.

This spec closes that gap for the three modules that belong *inside* the run loop or
*on* its report:

- **Assertions** (T-014) — run structural checks *before* the paid judge call.
- **Variance** (T-019) — orchestrate K live runs of one frozen dataset, then aggregate.
- **Run delta** (T-013) — diff this run against a baseline and surface it in the report.

`criteria_audit.py` is **out of scope** here — it audits a *dataset*, not a *run*, so it
belongs to the create-dataset lifecycle, not the run path.

**Why one spec.** The three tickets share a single seam (`run_evaluation` + the
`prompt-evals-run` report surface) and a single contract decision (how deterministic
evidence relates to judge scores and verdicts). Specifying them together keeps that
contract coherent; splitting them would re-litigate it three times.

---

## 2. Dependency on the architecture refactor (read first)

> **✅ Resolved after the fact (T-018, 2026-05-30).** This sequencing concern is now
> historical: T-013/T-014/T-019 **shipped and merged first**, against the vendored
> `./evals` layout. T-018 then landed as a **retrofit** that adds a plugin-resident
> artifact front-end **routing through the same `run_evaluation` seam these tickets
> hardened** — so assertions, K-run variance, and run-delta are inherited, not re-wired.
> No re-vendoring was required and no capability regressed. The original sequencing rule
> below is preserved for context.

[T-018] (`2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`) changes
*where* eval artifacts live and *what* "the live run path" means (plugin-resident
runner reading project-owned artifacts vs. today's vendored `./evals`). **The seam
this spec wires into is exactly the seam T-018 reshapes.**

Sequencing rule (original, now superseded by the note above): **resolve the T-018
architecture decision before building T-014/T-019's in-loop wiring.** T-013 (report-surface
only, no loop change) can land against either architecture and is the safe first step. If
T-018 lands first, the `run_evaluation` entry point and artifact layout below are expressed
in *its* terms; if this work lands first, it must not harden the vendored-`./evals`
assumption T-018 removes.

---

## 3. T-013 — Variance + baseline delta in the run report

**Smallest, highest-priority (it is in `review-layers`, not `backlog`). Cores already
built — this is a reporting change, not a new engine.**

### 3.1 Behavior
The `prompt-evals-run` report gains a **report-analyst** section that surfaces, when the
inputs exist:

- **Baseline delta** — when a prior run artifact is available, call
  `run_delta.compute_delta(current, baseline)` and render per-case + aggregate deltas
  (matched by scenario), with pass-rate movement and the argmax/argmin movers.
- **Multi-run variance** — when ≥ 2 run files of the same frozen dataset exist, call
  `variance`'s aggregator and render per-case mean ± stddev, flagged flaky cases, and
  the `suggested_regression_band`.

Both are **advisory** report content. T-013 does **not** change the run loop, gate any
verdict, or call any model — it consumes existing `output.json` artifacts.

### 3.2 Surface & contract
- The skill supplies which artifacts to diff/aggregate (baseline label; the set of run
  labels). The script never discovers "the previous run" by clock or mutable state —
  inputs are explicit, keeping the report reproducible and testable.
- When inputs are absent (no baseline, single run), the section renders a one-line
  "not available — needs ≥2 runs / a baseline" note, never an error.
- The variance summary's `suggested_regression_band` is the same value
  `prompt-engineering-improve`'s `improve_step.py` is meant to consume to calibrate its
  hardcoded `0.5` band (cross-referenced, not duplicated — that spec §6).

### 3.3 Tests (offline, no key)
Fixture `output.json` pairs/sets → asserted report fragments: delta section matches
expected movers; variance section matches expected mean/stddev/flaky/band; absent-input
path renders the note, not a crash.

---

## 4. T-014 — Live run-path assertion gating

### 4.1 Behavior
Inside the live run path, **after each prompt output is produced and before the LLM
judge grades it**, run the configured structural assertions via the shipped
`evals/assertions.py` engine: `contains`, `regex`, length bounds, `json_valid`,
`json_has_key`. Record deterministic pass/fail evidence in the run artifact and report.

### 4.2 The contract decision (the consequential part)
Define **how a failed assertion affects the judge and the verdict.** Options, to be
locked in the plan:

- **gate (default)** — a failed mandatory assertion marks the case failed and **skips
  the paid judge call** (assertions are cheaper and definite; no point grading output
  that already violates a must-have). The case's score is the deterministic floor.
- **annotate** — assertions always run and are recorded, but the judge still grades;
  failures are surfaced as evidence, not a hard gate.

Recommended default: **gate on `mandatory` assertions, annotate on advisory ones**, with
per-eval config to opt a case into annotate-only. The chosen policy is recorded in the
run artifact so the report can explain why a judge call was or wasn't made.

### 4.3 Invariants
- **No edits to `evaluator/` core.** The assertion engine is composed *around* the run
  loop, honoring the composition invariant named in `PROMPT_EVAL_FRAMEWORK_SPEC.md` §13
  and the architecture spec §5. Assertions are a pre-judge stage, not a judge change.
- **The offline CLI stays usable** — `python -m evals.assertions` over existing files
  must keep working unchanged.
- Deterministic evidence (which assertions ran, which passed/failed, whether the judge
  was skipped) is persisted in the run artifact, not just printed.

### 4.4 Tests (offline, no key)
Each assertion type pass/fail; gate-vs-annotate policy drives judge-skip correctly with
a fake judge client; persisted evidence shape; offline CLI unchanged.

---

## 5. T-019 — Live K-run variance orchestration

### 5.1 Behavior
Add orchestration that runs the **same frozen eval dataset K times** through the live
eval path, writes **K distinct run artifacts**, then invokes/reuses `evals/variance.py`
to compute per-case mean/stddev, flag flaky cases, compute aggregate score variance, and
emit the `suggested_regression_band`.

### 5.2 Run layout & labels
- Define a deterministic run-label scheme for the K runs (e.g. a shared variance-run
  group id + ordinal), and an artifact layout the variance aggregator can enumerate
  without guessing. Labels are inputs, not clock-derived.
- The report (or the `prompt-evals-run` skill) surfaces the variance summary using the
  **same renderer T-013 introduces** (§3) — one variance section, two producers (a
  pre-existing set of runs vs. a freshly orchestrated K-run group).

### 5.3 Invariants
- `evals/variance.py` **remains available as an offline CLI** over existing `output.json`
  files — orchestration is additive, not a replacement.
- K is explicit config; cost is `K × (run + grade) × num_cases` and the skill must state
  the budget implication before launching (mirrors the cost note in the framework spec).

### 5.4 Tests (offline, no key)
Fake run executor produces K deterministic artifacts; aggregator output matches expected
mean/stddev/flaky/band; label/layout scheme is enumerable; offline CLI unchanged.

---

## 6. Shared design rules

1. **Cores are not reimplemented.** All three tickets *call* the shipped modules
   (`assertions`, `variance`, `run_delta`). Any new code is orchestration/wiring/report
   rendering only. Re-implementing delta/argmax or stddev is a defect.
2. **Deterministic over non-deterministic.** Everything added here is closed-form and
   offline-testable. The only model call in scope is the *existing* judge — and T-014 can
   *avoid* it (gate), never add new ones beyond T-019's K multiplier.
3. **Explicit inputs, reproducible reports.** No module reads the clock or "latest run"
   from mutable state; labels, baselines, and K are passed in.
4. **Advisory by default.** T-013 and T-019 only inform. T-014 is the only one that can
   change a verdict, and only under its declared gate policy.
5. **Offline CLIs preserved.** Each module keeps its `python -m evals.<module>` entry.

---

## 7. Definition of done

- **T-013:** report renders baseline-delta + multi-run-variance sections from existing
  artifacts; absent-input note path; offline tests green; no loop/model change.
- **T-014:** assertions run pre-judge in the live path; gate-vs-annotate policy
  implemented + configurable; deterministic evidence persisted; `evaluator/` untouched;
  offline CLI unchanged; offline tests green.
- **T-019:** K-run orchestration writes K labeled artifacts and produces a variance
  summary via the shared renderer; offline CLI unchanged; offline tests green.
- Cross-spec links updated: this spec referenced from `PROMPT_EVAL_FRAMEWORK_SPEC.md`
  §13's live-path note; the T-018 sequencing constraint (§2) honored.
- Skill linter + full offline suite pass, with actual output shown (per `AGENTS.md`).

---

## 8. Scope boundaries

- **Not here:** `criteria_audit.py` wiring (dataset audit, not run path — belongs to the
  create-dataset lifecycle).
- **Not here:** judge panels / multi-sample grading beyond T-019's K live runs
  (`PROMPT_EVAL_FRAMEWORK_SPEC.md` §13 keeps that "consider").
- **Not here:** the artifact-location/vendoring redesign — that is T-018 (§2), a hard
  upstream dependency for T-014/T-019.
- **Not here:** any CI gate. This stays a dev-time tool; the gate policy in T-014 governs
  a single run's verdict, not cross-run regression blocking.
