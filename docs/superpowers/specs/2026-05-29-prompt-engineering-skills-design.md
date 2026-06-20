# Design: Prompt-Engineering Skills (`prompt-engineering-author` + `prompt-engineering-improve`)

**Date:** 2026-05-29
**Status:** Approved design — **revised twice on 2026-05-29**: first after the critical review
(determinism, token-efficiency, seam-correctness, composition), then after adversarial verification
caught an execution-model error (in-process Python cannot dispatch subagents). Ready for
implementation planning.
**Plugin:** `je-dev-skills`

> **Revision note.** Three locked decisions drive this revision: (1) the two skills are renamed to
> the group-verb convention `prompt-engineering-author` / `prompt-engineering-improve`; (2) execution
> is **in-Claude-Code, no direct API calls on the interactive path** — the prompt-under-test runs by
> **subagent dispatch driven by the skill**, with a keyed client retained only as a headless/CI
> fallback; (3) the runtime/orchestration gap (turning a design + prompts into a *running* agent) is
> owned by the new **`agent-build-*`** group. The execution substrate, the framework paths, and the
> composition invariant are defined in the companion **architecture spec**
> ([`2026-05-29-agent-build-and-execution-spec.md`](./2026-05-29-agent-build-and-execution-spec.md));
> this spec **consumes** it and does not redefine it.

## 1. Purpose

Add a **prompt-engineering lifecycle** to the plugin: two skills that help a user write an excellent
prompt and then improve it through measured, evaluation-driven iteration. They sit *on top of* the
existing `prompt-evals-*` lifecycle (the measurement substrate) rather than reimplementing any of it.

- **`prompt-engineering-author`** — author a strong single-shot prompt from a task description, or
  refactor an existing prompt against best practices. Standalone, eval-free.
- **`prompt-engineering-improve`** — drive an iterate → measure → diagnose → rewrite loop that uses
  the existing eval framework to make a prompt measurably better, with explicit stopping rules.
  Every numeric decision in the loop is computed by a **deterministic helper script** (§6).

This realizes the user's two-part framing — "write an excellent prompt" and "orchestrate end-to-end
improvement through evals" — while making explicit three pieces: (a) the success target lives in
`prompt-evals-create-dataset`, (b) the loop's intelligence is the diagnosis→technique mapping, and
(c) the loop needs explicit, deterministically-evaluated stopping criteria.

**Where this sits in the plugin (scope boundary).** This group **authors** and **measurably improves**
prompts. It does **not** stand up the running agent — that is the `agent-build-*` group's job
(architecture spec). The single lifecycle:

```
workflow-design-*  →  prompt-engineering-author  →  agent-build-*  →  prompt-evals-*  →  prompt-engineering-improve
   (design)              (author prompts)            (build + run)       (measure)            (improve, looped)
   (interactive path: in Claude Code on session auth, no API key · headless/CI: keyed fallback)
```

## 2. Locked decisions

| Decision | Choice | Why |
|---|---|---|
| Structure | **Two skills**, reuse `prompt-evals-*` | Matches the repo's composable-skill pattern; narrow `description`s trigger accurately; each skill stays small; no duplicate eval engine. |
| Naming | **`prompt-engineering-author` / `prompt-engineering-improve`** (group-verb) | Restores the repo convention; removes the `prompt-*` prefix collision with `prompt-evals-*`. |
| Author ↔ improve interface | **Shared references, follow procedure**: `prompt-engineering-improve` reads the technique references **and a shared rewrite-procedure reference** by `${CLAUDE_PLUGIN_ROOT}` path and runs the rewrite inline | No runtime skill-invocation dependency. **Both the catalogue and the rewrite procedure have a single physical home with two readers** (§5; cross-skill coupling noted in §7). |
| Execution | **In-Claude-Code, no API key on the interactive path** | The prompt-under-test runs by **subagent dispatch driven by the skill** (architecture spec), not the `anthropic` SDK. A keyed client (`AnthropicClient`) is a **headless/CI fallback only**. The no-key interactive eval path supports **single-shot** prompts (the no-subagent-nesting rule — see §4 and architecture spec §2). |
| Determinism | **All numeric loop logic is a deterministic helper** (`improve_step.py`) with offline tests | The plugin's north star is "deterministic over non-deterministic where possible." Stopping math, deltas, best-version selection, the diagnosis tally, and the `EXTRA_CRITERIA` freeze are closed-form — code, not prose. Mirrors `workflow-design-validate`. |
| Artifact scope | **Single-shot prompts**, structured to extend to agentic later | Coherent ladder; most common case; **and it matches the no-key interactive eval path's single-shot limit**. A deliberate v1 cut, not a substrate limitation — the eval framework is already agentic-capable (Trajectory) on the keyed path; agentic *authoring* + agentic-app eval are the named additive layer (§8). |
| Loop control | **Hybrid (configurable)** | Checkpointed by default; opt into "auto, up to N rounds". |

## 3. Architecture & composition

```
prompt-engineering-author ─────────►  a prompt (eval-free, single-shot)
  mode A: generate (task desc → prompt)
  mode B: improve  (existing prompt → refactored prompt)
        │
        │ (optional: take the authored prompt into a measured loop)
        ▼
prompt-engineering-improve ────────►  a measurably-better prompt + trace
  preconditions: ./evals exists + a frozen dataset exists
  loop (hybrid control; numeric decisions via improve_step.py):
     prompt-evals-run  ──►  scored report (output.json)
        │   [no-key: skill dispatches execute+grade subagents per case → deterministic glue aggregates]
        ▼
     diagnose weaknesses (deterministic tally + model names the theme)
        │
        ▼
     follow shared rewrite-procedure (+ techniques/anti-patterns refs) + the diagnosis → prompt vN+1
        │   → copy into <name>.current.md → re-measure on the SAME frozen dataset
        ▼
     delta + best + continue/stop verdict (improve_step.py)
```

**Boundaries:**
- `prompt-engineering-author` is **standalone and eval-free**; needs only a task description (mode A)
  or an existing prompt (mode B). **Never touches `./evals`**. `allowed-tools: Read, Write, Edit, Glob`.
- `prompt-engineering-improve` **orchestrates, never reimplements** the eval engine. It calls
  `prompt-evals-run` to measure and rewrites by **following the shared rewrite-procedure reference
  against the shared technique references** (read by `${CLAUDE_PLUGIN_ROOT}` path) — not a runtime
  skill call. New machinery it owns: the **deterministic `improve_step.py`** and the
  diagnosis→technique mapping. It also owns wiring `run_prompt` for the keyed path and the
  prompt-prep glue for both paths (§4).
- **`prompt-evals-run` vs. `prompt-engineering-improve` boundary.** `prompt-evals-run`'s "Diagnose and
  iterate" step is re-scoped to a **single-pass** diagnosis ("here's what's wrong; fix and re-run,
  **or invoke `prompt-engineering-improve` to automate the loop**"). The multi-round loop, stopping
  rules, and versioning belong to `prompt-engineering-improve`. The criteria-vs-prompt guard and
  mandatory-criterion-first rule live in **one shared `references/diagnosis.md`** that both skills
  cite. **Note (cross-group edit):** `prompt-evals-run/SKILL.md` is *also* edited by the architecture
  spec (its run procedure becomes the subagent-dispatch path). Both edits land in one coherent
  SKILL.md; the architecture spec owns the run-procedure rewrite and this spec owns the §4-diagnosis
  re-scope — see the architecture spec's DoD for the merge.
- `prompt-engineering-improve` **does not define success criteria or build datasets** — that is
  `prompt-evals-create-dataset`. Missing `./evals`/dataset → stop and route the user there.

## 4. The file seam — prompt text · deterministic glue · two execution paths

There are three layers; only the first is the prompt, and execution has **two paths**.

**Layer 1 — the prompt is text → a text file.** The active prompt is always at a stable path,
`evals/prompts_under_test/<name>.current.md`, with each round's candidate at `<name>.vN.md`. It is
what `prompt-engineering-author` emits and what a human reviews; it diffs cleanly across rounds; it is
editable without touching code.

**Layer 2 — deterministic prompt-prep glue (both paths).** A small helper renders the active prompt
with a case's `prompt_inputs` and checks placeholders. It lives in the **vendored `evals/` layer** —
in `evals/run_eval.py` (the per-project, editable copy) or a small module beside it under `evals/` —
so the keyed Path B's in-process `run_evaluation` can import it; **never** in `evals/evaluator/`
(frozen by the composition invariant) and **never** under `skills/` (not importable from `evals/`).
It uses the framework's existing `render()`:
- `render()` (`evals/evaluator/templates.py`) is **reused as-is**: `{placeholder}` substitution,
  `{{ }}` escaping of literal braces, **raises `KeyError` on a missing placeholder** (the hard
  backstop). It **ignores extra values** by design.
- The helper adds what `render()` does not: a pre-flight `check_placeholders(template, prompt_inputs)
  -> {declared, unused, missing}` that **fails on a missing placeholder** (before `render()`'s
  backstop, producing a structured report), **warns on unused inputs**, and **reports the detected
  placeholders** so the human can reconcile them against `create-dataset`'s hand-edited
  `PROMPT_INPUTS_SPEC` (there is **no** automatic sync consumer; closed-key-set agreement is enforced
  separately at generation time by `schemas.validate_test_case`). `check_placeholders` is
  intentionally redundant with `render()`'s `KeyError` so the warn/report path runs first. Ships with
  offline tests (§9).

**Layer 3 — execution has two paths (architecture spec defines the substrate):**

1. **No-key path (canonical, interactive).** `prompt-evals-run` (the skill, in an interactive Claude
   Code session) drives measurement itself: for each case it renders the prompt (Layer 2), then **the
   orchestrating Claude dispatches an execute-subagent** (runs the single-shot prompt) and a
   **grade-subagent** (emits the verdict JSON) via the Agent/Task tool — **session auth, no API key**.
   A **deterministic aggregation helper (no model calls)** — `evals/aggregate.py`, defined by the
   architecture spec — collects the verdict JSONs and writes
   `evals/runs/<run_label>/{output.json,output.html}` via the framework's report writers
   (`from evals.evaluator.report import summarize, write_json, write_html`). There is **no `run_prompt`
   model call and no `run_evaluation` loop** on this path — a
   synchronous Python function cannot dispatch a subagent, so the skill (not code) drives it. Limited
   to **single-shot** prompts (a multi-subagent app would require nesting, which the runtime forbids —
   architecture spec §2/§3).
2. **Keyed fallback path (headless/CI).** The existing `evals/run_eval.py evaluate` →
   `PromptEvaluator.run_evaluation` in-process loop with `AnthropicClient` for executor **and** judge.
   Here `run_prompt(prompt_inputs) -> str` is the executor seam (loads `<name>.current.md`, runs
   Layer-2 glue, calls the keyed model). Requires `ANTHROPIC_API_KEY`; supports agentic `Trajectory`;
   structured grading via the SDK's `output_config` (real, `client.py`). Selected by
   `EXECUTION_MODE=anthropic_api` (config owned by the architecture spec).

**`run_prompt` migration on first use (review fix 5a, corrected).** The bundled `run_prompt`
(`run_eval.py:35-54`) does **not** merely inline a prompt string — it instantiates
`AnthropicClient(EXECUTOR_MODEL)` and calls `messages.create(..., max_tokens=600)` directly. So
migration is path-aware:
- The **prompt text** is always extracted into `<name>.current.md` (the durable artifact).
- **Call-logic knobs** divide: system text / extra user content **map** onto subagent dispatch; raw
  `messages.create`, `max_tokens`, and tool wiring **do not** (subagent frontmatter has no such
  knobs — architecture spec §2). The shipped template's `messages.create(max_tokens=600)` is **exactly
  the case that cannot be preserved on the no-key path**: migration either rewrites it to the
  executor's supported options or **routes that prompt to the keyed fallback path** (where `run_prompt`
  keeps its custom call logic verbatim).
- Either way, **show the diff and get explicit confirmation** before the first eval (acceptance
  criterion §9).

The bundled `run_eval.py` and `prompt-evals-run/SKILL.md` are updated to demonstrate the file-backed
`<name>.current.md` + `render()` + check-placeholders pattern as the **default**.

**Versioning & active selection.** `run_prompt`/the no-key skill always uses `<name>.current.md`. Each
round writes its candidate `<name>.vN.md`, then copies the chosen candidate into `<name>.current.md`
*before* measuring. `improve_step.py` names the best-scoring version (§6).

## 5. `prompt-engineering-author` (Part 1)

**Purpose:** turn a task (or existing prompt) into a well-built single-shot prompt. Standalone,
eval-free, fast. Never touches `./evals`.

**Progressive disclosure.** The SKILL.md body is a table of contents; each `references/` file loads
**only when its step is reached** — never all up front (the `workflow-design-interview` discipline).

**Modes (one shared technique catalogue):**
- **Mode A — generate:** task description (+ optional input variables / output expectations) → a new prompt.
- **Mode B — improve:** an existing prompt (+ optional issues, or a diagnosis from
  `prompt-engineering-improve`) → a refactored prompt plus a short changelog of techniques applied.

**Technique catalogue** — `references/techniques.md`, an **escalation ladder** (cheapest/
highest-leverage first): (1) clear & direct; (2) output guidelines + process steps; (3) **guardrails:
name the failure modes** (named failure-mode prohibitions, enforced output-structure labels, named
pattern lists, and a **guarded** quality self-check — judgment bars only, deterministic checks stay in
code/evals); (4) examples (one-/multishot, `<example>` tags, diverse, corner cases); (5) XML structure
(separate instructions from data); (6) role framing (**in-text** for v1); (7) adaptive thinking /
reasoning scaffolding; (8) chaining (the boundary of single-shot — flagged); (9) long-context tips
(docs first, query last).

**Shared rewrite procedure (the seam, not just the catalogue).** The application constraints that
shape a rewrite — "**pick the minimum rungs to fix the diagnosed weakness; do not max out**," obey
the anti-patterns, prefer adaptive thinking, soften imperatives, emit prompt + changelog — live in
**`references/rewrite-procedure.md`**. Both `prompt-engineering-author` Mode B **and**
`prompt-engineering-improve`'s rewrite step read this file by `${CLAUDE_PLUGIN_ROOT}` path, so the
procedure (not only the catalogue) has a single home with two readers.

**`references/anti-patterns.md`:** prefer positive instructions, but the test is **specificity, not
polarity** — a *named* failure-mode prohibition ("do not invent unstated facts") is concrete and
belongs (Rung 3); only *vague* negatives ("be accurate", "avoid bias") are the anti-pattern. No
over-prompting (`CRITICAL: YOU MUST…`); keep
examples consistent with edited instructions; concrete ranges over "be concise"; **don't ask the LLM
to do what code should** (the plugin's north-star thesis, shared with `workflow-design`); resolve
conflicting rules; prefer private reasoning over forced *exposed* chain-of-thought. Best-practice-only
/ model-aware by construction: no assistant prefill; no manual `budget_tokens`; prefer adaptive
thinking + `effort`.

**Output:** the prompt as a text file (Layer 1) + its declared `{placeholder}` variables. Standalone
use writes/prints to a path the user chooses and does not modify `./evals`.
`allowed-tools: Read, Write, Edit, Glob`.

## 6. `prompt-engineering-improve` (Part 2 — the loop)

**Preconditions** (same as `prompt-evals-run`): `./evals` exists and a frozen dataset exists. Else
stop and route to `prompt-evals-setup` / `prompt-evals-create-dataset`. Owns no eval engine. On first
use it migrates `run_prompt`/wires the prompt-prep glue (§4).

**Progressive disclosure.** Load each reference only at its step: `diagnosis.md` at the diagnose step;
`rewrite-procedure.md` + `techniques.md` + `anti-patterns.md` at the rewrite step. Never all four up
front.

**Determinism: `scripts/improve_step.py` (the headline change).** Mirroring
`workflow-design-validate/scripts/validate_blueprint.py`, the loop ships a **deterministic CLI** with
**offline `unittest` fixtures**. It ingests the round's `evals/runs/<label>/output.json` + a small
loop-state file and **emits**:
- per-round **delta** and the running **best** version id (`argmax`);
- the **stopping verdict** (`continue | stop:<rule>`, nonzero-exit convention) over threshold /
  pass-rate / diminishing-returns(K) / regression-band / max-rounds;
- the **diagnosis tally** — count of cases failing a mandatory criterion (judge score ≤ 3, per
  `grading.md`) and %-of-cases per weakness theme — list comprehensions over the verdict JSON;
- the **`EXTRA_CRITERIA` freeze guard** — a hash of `EXTRA_CRITERIA` snapshotted at loop start,
  asserted unchanged for the held-out run and stamped into `final-report.json` (deterministic
  enforcement of the freeze, not a prose reminder);
- the assembled `delta.json` and final-report payload (deterministic serialization).

The SKILL.md prose **calls this script and acts on its verdict; it never does the float math, the
argmax, the tally, the freeze check, or the serialization itself.** What stays with the model:
**naming the dominant failure theme** and **the rewrite**. The theme→rung mapping and the
priority/tie-break ladder are a **table the script applies once the theme is named**.

**One round:**
```
baseline:  prompt-evals-run → output.json   [no-key: skill dispatches execute+grade subagents; glue aggregates]
diagnose:  improve_step.py tallies weaknesses/mandatory-fails  →  model names the dominant theme(s)
   ├─ criteria problem? (guard below) → STOP, route to create-dataset
select:    map theme → next ladder rung (improve_step.py applies the priority table)
rewrite:   follow rewrite-procedure.md + diagnosis → prompt vN+1 → copy into <name>.current.md
re-eval:   prompt-evals-run on the SAME frozen dataset → new output.json
delta:     improve_step.py → delta + best + continue/stop verdict
```

**Token cost & cheap inner loop.** On a single-shot prompt one full evaluation costs **2N** model
calls (N execute + N grade). A loop is **baseline + N rewrite re-evals + 1 held-out = (N+2) full
evaluations**, i.e. ≈ `(N+2) × 2N` calls at default `max_rounds = N = 3`. (For agentic prompts on the
keyed path the execute side is unbounded per case, so 2N is a single-shot figure.) To cut recurring
cost, mid-loop **diagnosis** may run against a **deterministically sampled K-case subset** that a
helper writes from the frozen dataset and passes as `dataset_file` — **not** `datasets/smoke.json`
(that is a 3-case offline fixture for the framework's own tests, not a sample of the user's data). The
**full frozen dataset** is run at every decision point (delta/stop verdict, version selection,
checkpoint).

**Diagnosis → technique mapping** (`references/diagnosis.md` — shared with `prompt-evals-run`):

| Dominant failure theme | Next rung to escalate to |
|---|---|
| Mandatory-criterion failures (score capped ≤ 3) | Fix that gate **first** |
| Fabricated / unsupported content the model **added** | Guardrails: named prohibitions + enforced source labels (Rung 3) |
| Missing required content | Process steps; examples showing the requirement |
| Format / structure drift, inconsistency | XML structure + multishot examples |
| Shallow / wrong reasoning on hard cases | Adaptive thinking / reasoning scaffolding |
| Tone / style off (incl. filler / boilerplate) | Role framing + output guidelines; filler → a named prohibition (Rung 3) |
| Conflicting / ambiguous instructions | Resolve the conflict (anti-pattern), don't add more |

The `fabrication` tally is **precision-tuned**: `improve_step.py` flags only unambiguous added-content
verbs (fabricate/invent/hallucinate/made-up-`<noun>`); ambiguous "unsupported…" / "not in the input"
phrasing is left to the model + the criteria-vs-prompt guard, since the same words describe a dataset
problem (the opposite routing).

**Diagnosis priority + tie-break** (applied by `improve_step.py`): (1) mandatory-criterion failures;
(2) fabricated/unsupported added content (usually itself a mandatory fail; erodes trust fastest);
(3) failures across ≥ 30% of cases; (4) largest score-impacting weakness; (5) format/structure;
(6) tone/style. Ties → earliest item unless the user overrides.

**Criteria-vs-prompt guard.** Route to `create-dataset` when the judge complains about content not in
the inputs, the rubric demands an unstated style/format, the rationale conflicts with the rubric, or
the answer needs hidden domain knowledge. Investigate (possible prompt non-determinism) when failures
are inconsistent across similar cases. Do **not** route when the prompt omitted instructions, ignored
a stated format, or failed recurring reasoning steps.

**Hybrid control.** Checkpointed by default — pause each round with diagnosis + technique + delta +
remaining weaknesses; ask continue/stop/adjust. Opt into "auto, up to N rounds": stream each delta,
stop early on threshold/regression, then return to checkpointed. **Auto mode is no-key only while
driven by an interactive Claude Code session** (subagent dispatch); a genuinely unattended/CI
auto-loop runs through the keyed `AnthropicClient` fallback and requires `ANTHROPIC_API_KEY`. In auto
mode the deterministic `improve_step.py` verdict gates each iteration (the human is not eyeballing the
arithmetic — exactly why it must be code).

**Loop parameters — one declared home (review fix 5c).** The five new params live as a **constants
block at the top of the per-project `run_eval.py`** (the existing edit surface for `TASK`/`SPEC`/
`EXTRA_CRITERIA`); `pass_threshold` is the one intentional reference back to `config.PASS_THRESHOLD`.
(They do **not** go in `config.py`, which the architecture spec edits for `EXECUTION_MODE` — keeping
the two specs' config edits from colliding.) `improve_step.py` reads them and **stamps the resolved
values into each `delta.json` + the final report**.

| Parameter | Default | Meaning |
|---|---|---|
| `pass_threshold` | **`config.PASS_THRESHOLD` (7)** — referenced, not redefined | Avg-score bar |
| `pass_rate_target` | 0.80 | Fraction of cases ≥ threshold to target |
| `max_rounds` (N) | 3 | Hard cap on improvement rounds |
| `epsilon` (ε) | 0.25 | Min per-round avg-score gain that counts as progress |
| `diminishing_return_rounds` (K) | 2 | Consecutive sub-ε rounds before stopping |
| `regression_band` | **0.5** (not 0.0) | A round is a regression only if it scores **> band below** the best |

**Judge-noise robustness.** `GRADING_TEMPERATURE = 0.0` is *ignored* by the Opus judge (sampling
params removed), so re-grading is **not bit-identical**. `regression_tolerance = 0.0` ("any drop =
regression") would misfire on noise and waste rounds; v1 uses `regression_band = 0.5`, applied
deterministically by `improve_step.py`. A re-measure-on-tie (average K re-grades) is a deferred option
(§8) to keep cost bounded.

**Stopping criteria** (all evaluated by `improve_step.py`; if several fire, report all and keep the
**best**): threshold met (avg ≥ `pass_threshold` or `pass_rate_target` reached); diminishing returns
(delta < ε for K consecutive rounds); regression (a round > `regression_band` below best is discarded,
revert to best); budget cap (`max_rounds`).

**Run trace & versioning (review fix 5d, corrected).** `run_evaluation` **already** accepts a
`run_label` (`evaluator.py:83`), uses it to name the run dir, and **returns** `run_dir`
(`evaluator.py:125`) — so newest-dir globbing is unnecessary. The only gap is that `run_eval.py`'s
`main()` doesn't thread `run_label` through; the fix is to add that arg (and/or capture the returned
`run_dir`). On the **no-key path**, the deterministic aggregation helper writes to
`evals/runs/<run_label>/` with the same `report.py` writers. The loop passes
`run_label = improve-<name>-round-NN` so each round → its run dir is deterministic. The trace
**references** those runs; it never duplicates `output.json`:

```
evals/improve/<name>/<timestamp>/
  round-00-baseline/  { diagnosis.md, delta.json, run_dir → ../../runs/improve-<name>-round-00 }
  round-01/           { prompt.v2.md (or id), diagnosis.md, technique, delta.json, decision, run_dir → … }
  round-02/           ...
  final-report.md     (round-by-round trace, winning version, held-out result)
  final-report.json   (resolved loop params + held_out_run_count + EXTRA_CRITERIA hash)
```

**Overfitting / held-out (review fix 5e).** A built-in split is **deferred**. v1: improve against the
working dataset, then run a **final validation against a separate held-out dataset**, hardened:
- Never used for diagnosis/rewrite/selection. Runs **once**; `final-report.json` records
  `held_out_run_count` and **must keep it ≤ 1**; any post-held-out tuning forfeits the claim and
  requires a freshly generated held-out set.
- **Independence:** the held-out set must cover scenarios **distinct** from the working set (different
  idea seed; spot-check non-overlap via `create-dataset`'s audit) — not a near-duplicate.
- **`EXTRA_CRITERIA` is frozen** before any held-out run (it is a single global gate at
  `run_eval.py:26`); the freeze is **enforced deterministically** by `improve_step.py`'s hash guard
  (above), not by prose.
- Absent held-out set → produce the best working-dataset prompt and mark final validation **skipped**
  (not failed).

**Output:** versioned prompt files (`<name>.vN.md` + `<name>.current.md`), the trace above, and a
final report (round-by-round trace, winning version, held-out result or "skipped").

**Frontmatter:** `name: prompt-engineering-improve`; third-person `description` (what + when);
`argument-hint`; `allowed-tools: Bash, Read, Write, Edit, Glob` (Bash runs `improve_step.py` + evals).

## 7. Skill conventions & plugin wiring

- Follow existing conventions: third-person `description` (what + when), `argument-hint`, `version`,
  `${CLAUDE_PLUGIN_ROOT}` references, **Precondition** / **Definition of done** sections, an
  **Offline** note where relevant, and **progressive disclosure**.
- **Cross-skill reference coupling (flag).** `rewrite-procedure.md` (under `prompt-engineering-author`)
  is read by `prompt-engineering-improve`; `diagnosis.md` (under `prompt-engineering-improve`) is read
  by `prompt-evals-run`. These are read by `${CLAUDE_PLUGIN_ROOT}` path and are **part of the group
  contract** — a consumer skill has a hard path dependency on a producer skill's `references/` dir, so
  these files cannot move/rename without updating all readers. Documented so independent versioning
  doesn't silently break a reader.
- Wire both skills into `README.md` + `.claude-plugin/plugin.json` as part of the **unified lifecycle
  story** the architecture spec defines (§4 there), not as a separate island.

## 8. Non-goals (YAGNI) & future enhancements

**Out of scope for v1:**
- Agentic prompts (system prompts, tool descriptions, trajectory/process grading) and **evaluating
  multi-subagent apps on the no-key interactive path** (the no-nesting rule limits it to single-shot;
  agentic-app eval is keyed/headless — architecture spec §2/§3). A deliberate cut; the eval substrate
  is already agentic-capable on the keyed path.
- A built-in train/held-out split in the framework (use §6's second-dataset approach).
- A real `system`/`user` message split via prompt frontmatter (v1 "role" is in-text — §5).
- Any new eval engine — reuse `prompt-evals-*` wholesale.
- Automatic success-criteria definition — that is `prompt-evals-create-dataset`.
- Judge panels / multi-sample grading (single-judge variance noted; `regression_band` mitigates).
- **Standing up the running agent** — owned by `agent-build-*` (architecture spec).

**Future enhancements:** agentic technique catalogue + trajectory-aware diagnosis; built-in held-out
split; frontmatter `system:`/`user_template:` format; re-measure-on-tie smoothing.

> **Reconciliation addendum (2026-05-29, after the `claude-plugins-official` review).** Two
> alignments with Anthropic's `skill-creator`: (1) once the eval framework ships the planned
> **multi-run variance + baseline/previous-run delta** helpers (`PROMPT_EVAL_FRAMEWORK_SPEC.md` §13,
> "v0.2 hardening"), `improve_step.py` should **consume** them — the measured per-case stddev
> calibrates `regression_band` (replacing the hardcoded 0.5 in §6) and the delta helper replaces
> `improve_step.py`'s home-grown delta/argmax. (2) The deferred built-in train/held-out split should
> follow `skill-creator/scripts/run_loop.py`'s **overfitting-aware selection** — 60/40 split, sample
> each case for a reliable rate, and **select the best version by held-out score, not training
> score**. Methodology-transferable (it optimizes triggering, not output quality), not a code
> drop-in.

## 9. Definition of done (for implementation)

**Files expected** (framework lives at `skills/prompt-evals-setup/framework/evals/`, copied to
`./evals` by `prompt-evals-setup`):
```
skills/prompt-engineering-author/SKILL.md
skills/prompt-engineering-author/references/techniques.md
skills/prompt-engineering-author/references/anti-patterns.md
skills/prompt-engineering-author/references/rewrite-procedure.md      (shared: author Mode B + improve)
skills/prompt-engineering-improve/SKILL.md
skills/prompt-engineering-improve/references/diagnosis.md             (shared: cited by prompt-evals-run too)
skills/prompt-engineering-improve/scripts/improve_step.py             (deterministic loop logic + EXTRA_CRITERIA hash)
skills/prompt-engineering-improve/scripts/tests/                      (offline unittest fixtures)
README.md                       (updated as part of the unified lifecycle — see architecture spec §4)
.claude-plugin/plugin.json       (updated — see architecture spec §4)
skills/prompt-evals-run/SKILL.md (updated: §4 re-scoped to single-pass + cites diagnosis.md; the run
                                  procedure rewrite is owned by the architecture spec — one merged file)
skills/prompt-evals-setup/framework/evals/run_eval.py
                                  (updated: file-backed .current.md + render() + check_placeholders default;
                                   run_label threaded through main(); loop-param constants block)
```
The new deterministic prompt-prep + aggregation glue lives in the **vendored `evals/` top level**
(beside `run_eval.py`), never in `evals/evaluator/`; the architecture spec defines the aggregation
helper and ensures `prompt-evals-setup`'s vendoring ships it.

**`improve_step.py` is unit-tested code** (this drops the prior "prose procedures, not unit-testable"
framing for `prompt-engineering-improve`). Offline `unittest` fixtures, no API key, matching
`workflow-design-validate`: given fixture `output.json`s it produces the right delta, best-version id,
`continue|stop:<rule>` verdict, diagnosis tally, and `EXTRA_CRITERIA`-freeze assertion; regressing/
noisy fixtures exercise `regression_band`.

**Behavioral acceptance criteria:**
- `prompt-engineering-author` writes a valid prompt file with declared placeholders from a task description.
- Given a prompt + issue list, `prompt-engineering-author` writes a refactored prompt + changelog.
- Given missing `./evals`, `prompt-engineering-improve` stops and routes to setup/create-dataset.
- Given mandatory-criterion failures, `prompt-engineering-improve` selects the gate-fix path first.
- Given a round > `regression_band` below best, it keeps the prior best version.
- Given multiple versions, measurement uses `<name>.current.md`.
- Given an existing custom `run_prompt`, migration extracts the text to `<name>.current.md` and either
  maps the call logic to subagent options or routes it to the keyed fallback, confirming the diff first.
- Given `prompt_inputs` with a field the template never references, the glue **emits an unused-input warning**.
- `prompt-engineering-author` never modifies anything under `./evals`.
- Held-out validation runs **at most once** (recorded); absent → "skipped, not failed".

**Composition invariant (named files).** This group leaves the framework **core** unchanged:
`evals/evaluator/{evaluator,generate,grade,run,schemas,jsonio,templates,report,client}.py` and
`evals/prompts/` are not modified by *this* group (it composes them). The deterministic prompt-prep +
aggregation glue is **added at the vendored `evals/` top level**, not inside `evals/evaluator/`. The
in-CC execution substrate (config `EXECUTION_MODE`, the aggregation helper, the `prompt-evals-run`
run-procedure rewrite) is **added by the architecture spec**, which this group consumes.
`run_eval.py` (per-project, editable) is updated as listed.

## 10. Implementation clarifications (quick reference)

- **Execution (§4):** two paths — no-key interactive (skill dispatches execute+grade subagents per case → deterministic glue aggregates; single-shot only) and keyed headless fallback (`run_evaluation` + `AnthropicClient`). Substrate defined in the architecture spec.
- **`run_prompt` (§4):** the executor seam on the **keyed** path only; the no-key path replaces it with skill-driven subagent dispatch.
- **Rendering / placeholders (§4):** `render()` reused for substitution + KeyError backstop; `check_placeholders` (warn-on-unused + placeholder report for manual reconciliation, no auto-sync consumer) in vendored `evals/`-level glue (`run_eval.py` or a module beside it), **never** in `evaluator/` or under `skills/`.
- **Migration (§4):** extract prompt text to `.current.md`; map system/user content to subagent options, route `max_tokens`/raw `messages.create`/tools to the keyed fallback; confirm the diff.
- **Determinism (§6):** `improve_step.py` owns delta/best/stop/tally/freeze-hash/serialization with offline tests; the model only names the theme and rewrites.
- **Loop params (§6):** one home — a `run_eval.py` constants block; `pass_threshold` references `config.PASS_THRESHOLD`; resolved values stamped into the trace. `config.py` edits are owned by the architecture spec (`EXECUTION_MODE`).
- **Run trace (§6):** `run_label` already exists in `run_evaluation` + `run_dir` already returned; thread it through `main()` and write the no-key path's report to `runs/<run_label>/`.
- **Stopping (§6):** `regression_band` 0.5 (not 0.0) for judge-noise robustness; enforced by `improve_step.py`.
- **Held-out (§6):** never used for diagnosis/selection; `held_out_run_count ≤ 1`; independent dataset; `EXTRA_CRITERIA` freeze enforced deterministically; "skipped, not failed" when absent.
- **Skill reuse (§2/§3):** `prompt-engineering-improve` follows the shared `rewrite-procedure.md` + `techniques.md` + `anti-patterns.md` by `${CLAUDE_PLUGIN_ROOT}` path; cross-skill reference coupling is documented (§7).
- **Boundary (§3):** `prompt-engineering-author` never touches `./evals`; `prompt-evals-run/SKILL.md` is edited by both this group (§4 diagnosis re-scope) and the architecture spec (run-procedure rewrite) into one merged file.
