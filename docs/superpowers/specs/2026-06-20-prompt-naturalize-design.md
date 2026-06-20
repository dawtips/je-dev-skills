# `prompt-engineering-naturalize` — Specification & Design

A design contract for a new standalone skill that drives an **iterate → measure → rewrite**
loop to make a prompt's *generated content* read more **natural / human**, using a
**modular, pluggable AI-likeness checker** (Originality.ai, a free local heuristic, a
locally-hosted model, or a test fake) as the optimization signal. The loop **reuses the
existing `prompt-engineering-improve` deterministic machinery** rather than cloning it.

> **Ticket covered:** [T-027] `prompt-engineering-naturalize` (phase `prompt-engineering`,
> type `feature`). Origin: the user wants to use Originality.ai to iterate a prompt so its
> drafts don't read like AI.
>
> **Relationship to other specs / skills.**
> - Reuses the eval-driven loop defined in `2026-05-29-prompt-engineering-skills-design.md`
>   and implemented by `skills/prompt-engineering-improve/` (its `improve_step.py` computes
>   every numeric decision: per-round delta, running-best version, continue/stop verdict).
> - Runs prompts through the same execution substrate as `prompt-evals-run` (Path A
>   `in_claude_code` subagents, or the Path B `anthropic_api` keyed fallback) per the
>   plugin-resident architecture spec (`2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`).
> - Reuses the rewrite guidance in `prompt-engineering-author/references/rewrite-procedure.md`
>   (+ `techniques.md`, `anti-patterns.md`) via `${CLAUDE_PLUGIN_ROOT}`, and adds one new
>   naturalness-specific reference.

---

## 1. Purpose & problem

A user authors a prompt that generates **prose-style content** (marketing copy, emails,
summaries, narrative). They want the *output* to read more like a person wrote it and less
like a machine. AI-content **detectors** (e.g. Originality.ai) produce a numeric signal for
exactly this — but a detector alone doesn't improve anything; you need a loop that *uses*
that signal to revise the prompt and re-measure.

This repo already has that loop shape (`prompt-engineering-improve`): iterate the prompt →
measure outputs against graders → diagnose → rewrite → re-measure, with deterministic
stopping rules. The missing pieces are (a) **a new way to measure** — "how natural does this
read?" — and (b) **a purpose-built front door** so a user can run "make this prompt's output
read human" without first standing up a full quality eval.

### Why a *standalone* skill (not a flag on `improve`)
Naturalness is **domain-specific**: it is meaningless for prompts that emit JSON, code, or
classifications, so it must never be a mandatory criterion of the general loop. A dedicated
skill is more discoverable, can offer a **cold-start** (no pre-existing eval required), and
keeps the general loop simple. To avoid the standalone's characteristic failure mode —
"more human but now subtly wrong" — it **reuses** the existing loop's deterministic stop /
trace logic and offers an **optional regression guard** against the user's other quality
criteria (§7).

## 2. Scope & non-goals

**In scope:** the checker contract + four providers; a naturalness-eval adapter that emits
the existing loop's verdict shape; an optional regression guard; cold-start scaffolding;
offline deterministic tests; the `SKILL.md` + references.

**Non-goals (explicit YAGNI):**
- **No promise to "beat" any specific detector.** The skill optimizes *reads natural*; it
  does not guarantee a given third-party detector will pass the text, and it says so. This
  is a writing-quality tool, framed honestly — not a detector-evasion tool.
- **No live external API call in the test suite** (recorded/mocked responses only).
- **No new HTML/GUI viewer** beyond the existing run report.
- **One hosted provider** (Originality.ai). Other hosted detectors are "swap a provider
  later," not built now.
- **`local_model` is one OpenAI-compatible adapter** (base URL + model name), not a set of
  per-vendor SDKs.

## 3. The checker contract (the one genuinely new abstraction)

A single, narrow interface that every provider implements. The loop is **provider-agnostic**:

```
score(text: str, context: dict | None) -> NaturalnessResult

NaturalnessResult = {
  naturalness: float,     # normalized 0..100; 100 = reads fully human, 0 = reads fully machine
  rationale:   str | None,
  raw:         dict,      # provider's untouched payload (for the trace)
  provider:    str        # which provider produced this score
}
```

**Score semantics are fixed and one-directional:** higher `naturalness` = more human; the
loop always **maximizes** it. Each provider is responsible for **normalizing its native
output into 0..100** so downstream code never branches on provider type. A provider either
returns a `NaturalnessResult` or raises a typed `CheckerError` (the adapter decides
retry / fallback / surface — §6, §8).

## 4. Providers

Each provider is an isolated unit with one job, independently testable.

| Provider | Source | Normalization to `naturalness` | Needs |
|---|---|---|---|
| `originality_ai` | Hosted API | `100 * human_fraction` (i.e. `100 * (1 − ai_probability)`) from the scan response | `ORIGINALITY_API_KEY` |
| `local_heuristic` | Offline, deterministic | Weighted blend of text features → squashed to 0..100 | nothing |
| `local_model` | Local LLM (Ollama / any OpenAI-compatible endpoint) | Model rates 0..100 human-likeness via a rubric prompt; parse strict result | base URL + model name |
| `fake` | Test stub | Returns scripted scores from config | nothing |

- **`originality_ai`** — POSTs the text to the scan endpoint; maps the documented AI/human
  field to `naturalness`. The exact response-field mapping is **pinned against a recorded
  fixture** and unit-tested (so an API shape change is caught by a failing test, not a
  silent miscalibration). Surfaces rate-limit / HTTP errors as `CheckerError`; never crashes
  the loop, never fabricates a score.
- **`local_heuristic`** — free, fully offline, **deterministic**. Combines signals that
  correlate with machine-flatness: **sentence-length variance ("burstiness")**, lexical
  diversity, **formulaic discourse-marker density** (e.g. "moreover", "in conclusion", "it's
  important to note"), and structural regularity, into a 0..100 estimate. Exact features +
  weights are pinned in code and unit-tested for **deterministic, monotonic** behavior on
  fixtures (a known-flat text scores below a known-varied text). Doubles as the **no-key
  default fallback**.
- **`local_model`** — calls an OpenAI-compatible local endpoint with a **naturalness-rating
  rubric** ("rate 0–100 how human this reads, and why"), parsing a strict `{rating,
  rationale}` result; `naturalness = rating`. This is the repo's existing **LLM-as-judge**
  pattern (open models are not trained detectors, so this is an explicit *rater*, not a
  pretend-detector). Unit-tested against a recorded model response (no live model).
- **`fake`** — returns a configured sequence of scores so the adapter and loop are verified
  end-to-end with **no key, no network, no model**.

### Selection & no-key fallback
Provider + provider-settings are chosen by config (provider name + the provider's settings).
**Default when nothing is configured: `local_heuristic`** (always works). If `originality_ai`
is selected but `ORIGINALITY_API_KEY` is absent, the skill **falls back to `local_heuristic`
and prints a notice** — it never silently pretends a real detector ran. The run report
always names the provider that produced the scores.

## 5. Reuse of the existing loop (no clone)

The naturalness checker is adapted into the **same grader/verdict shape the eval framework
already emits**, so the existing deterministic helper (`prompt-engineering-improve/scripts/improve_step.py`)
drives this loop unchanged.

**`naturalness_eval` adapter** — for each sample input:
1. Render + run the prompt-under-test to produce an output (the **same execution substrate**
   as `prompt-evals-run`: Path A subagents with no key, or the Path B keyed fallback).
2. Score that output with the configured checker → a per-case verdict.
3. Map `naturalness` (0..100) onto the framework's numeric grade scale by a **linear map**
   (`grade = naturalness / 10`, clamped to the framework's grade range), so **every existing
   loop parameter applies verbatim** (`PASS_THRESHOLD=7`, `epsilon=0.25`, `regression_band=0.5`,
   etc.). The user-facing `naturalness_target` (0..100) maps to the grade threshold
   (`target/10`); default `70` ⇒ the existing `7.0`. The exact clamp/rounding is pinned in
   code and unit-tested.
4. Emit the same `output.json` shape `improve_step.py` consumes (per-case grades, `avg`,
   `pass_rate`).

The model's only jobs remain **naming the dominant weakness** and **doing the rewrite**
(reusing `rewrite-procedure.md` + a new naturalness-techniques reference). **Every numeric
decision — delta, running-best, continue/stop — is computed by `improve_step.py`**, never by
hand. Versioned prompt files (`<name>.vN.md` + `<name>.current.md`), the round-by-round
trace, and the final report all come for free from that machinery.

## 6. The loop — one round, params, stops

```text
baseline:  naturalness_eval(prompt, samples, checker) -> output.json ; improve_step.py -> tally
diagnose:  model names the dominant naturalness weakness (filler density / low burstiness / generic voice ...)
rewrite:   rewrite-procedure.md + naturalness-techniques.md -> <name>.vN+1.md -> copy to <name>.current.md
re-eval:   naturalness_eval on the SAME sample set -> output.json
decide:    improve_step.py -> delta + best + continue/stop verdict   (+ regression guard, §7)
```

**Noise handling:** one generation is noisy, so each round scores **`samples_per_round`
outputs** (default **4**) and the framework aggregates them (each sample input is one
dataset case; the per-case naturalness is its grade; the round score is the aggregate).

**New params** (one constants block, stamped into the report like the existing loop):
`naturalness_target = 70` (user-facing 0..100), `samples_per_round = 4`. All other
stops are inherited unchanged: **target reached**, **diminishing returns** (Δ < `epsilon`
for K rounds), **max rounds**, **regression** (discard the round, keep best).

## 7. Optional regression guard (the safety net)

- **Default — naturalness-only:** the naturalness eval is the only signal; the loop
  optimizes and stops on it alone.
- **Guarded — opt-in:** the user supplies their **existing eval** (a separate dataset +
  quality criteria). Each round, a candidate rewrite that **raises naturalness** is *also*
  run through the user's eval; if a guarded criterion **regresses beyond `regression_band`**
  versus the prior best, the candidate is **rejected** (the loop keeps the prior best) and
  the rejection is recorded in the trace. This reuses the loop's regression logic as an
  **accept/reject gate on the candidate**, not just a loop-stop. It is what prevents
  "more human, but the legal disclaimer quietly dropped a required clause."

The accept/reject decision is a small **deterministic** helper (`naturalize_step.py`) that
compares the naturalness gain against the guarded-eval movement; it does not introduce any
hand-computed numbers. Naturalness-only mode is the strict subset where no guarded eval is
supplied.

## 8. Cold-start, error handling & honesty

- **Cold-start (no eval required):** if no dataset exists, the skill scaffolds a minimal
  naturalness eval — collect a handful (default 4) of representative sample inputs, write
  them as the dataset, set the single criterion to "reads natural (score ≥ target)". It
  **states plainly** that a 4-sample cold start is noisy and recommends more samples for a
  trustworthy result.
- **Errors:** provider/API/rate-limit failure → surfaced as `CheckerError`, with optional
  bounded retry; **never a fabricated score**. Missing key for a hosted provider → documented
  fallback with a printed notice.
- **Honesty:** the report names the provider, records the resolved params + per-round trace,
  and frames the outcome as "reads more natural by this checker," **not** "guaranteed to pass
  detector X." Detector scores are noisy; the skill does not over-claim.

## 9. Testing strategy (deterministic-first, fully offline)

Mirrors how `prompt-engineering-improve` is tested — no key, no network, no live model in CI:

- **`test_checkers`** — each provider's normalization. `originality_ai` and `local_model`
  run against **recorded fixture responses** (HTTP JSON / model text). `local_heuristic` is
  pure-deterministic (known-flat text scores below known-varied text; same input → same
  score). `fake` is trivial.
- **`test_naturalness_eval`** — feed the `fake` provider scripted scores; assert the emitted
  `output.json` shape, the `naturalness → grade` mapping, and aggregation.
- **`test_naturalize_loop`** — drive the full loop with a `fake` provider emitting an
  improving-then-plateauing sequence; assert each deterministic stop fires (target,
  diminishing-returns, max-rounds, regression) **and** the regression-guard accept/reject
  fires when a guarded eval is supplied.

The new suite is registered in `AGENTS.md` (run from the skill's `scripts/`).

## 10. File layout

```text
skills/prompt-engineering-naturalize/
  SKILL.md                       # table-of-contents skill; references loaded per-step
  scripts/
    checkers/
      __init__.py                # the contract (NaturalnessResult, CheckerError, base) + registry/selection
      originality_ai.py
      local_heuristic.py
      local_model.py
      fake.py
    naturalness_eval.py          # adapter: run prompt on samples -> score -> emit output.json shape
    naturalize_step.py           # deterministic: wraps improve_step.py decisions + regression-guard accept/reject
    tests/
      test_checkers.py
      test_naturalness_eval.py
      test_naturalize_loop.py
      fixtures/                  # recorded API/model responses + sample texts
  references/
    naturalness-techniques.md    # rewrite guidance for naturalness (burstiness, voice, cut filler/hedges)
                                 # rewrite-procedure.md/techniques.md/anti-patterns.md reused from prompt-engineering-author
```

## 11. Definition of done

- New `skills/prompt-engineering-naturalize/` passes `python3 tools/skill_lint.py --root .`.
- All three offline suites pass; **actual output shown** (not claimed from memory).
- The new suite is added to the test list in `AGENTS.md`.
- Loop reuses `improve_step.py` for every numeric decision; `naturalize_step.py` adds only
  the deterministic regression-guard accept/reject.
- Honest framing present in `SKILL.md` and the report (no detector-evasion promise; provider
  named; noise caveat for small sample counts).
- Two independent review rounds addressed; handover + lesson written; **ephemeral plan
  deleted before merge**; plugin version bumped after merge (both manifest files).

## 12. Deferred / future (tracked, not built)

Additional hosted detectors; per-vendor local-model SDKs; a naturalness "diagnosis ladder"
mapping specific weaknesses → specific rewrite techniques (start with the author skill's
generic ladder + the naturalness-techniques note); auto-selecting `samples_per_round` from
observed variance.
