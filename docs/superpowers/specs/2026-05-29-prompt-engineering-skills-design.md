# Design: Prompt-Engineering Skills (`prompt-author` + `prompt-improve`)

**Date:** 2026-05-29
**Status:** Approved design (review-seam cleanup folded in) — ready for implementation planning
**Plugin:** `je-dev-skills`

## 1. Purpose

Add a **prompt-engineering lifecycle** to the plugin: two skills that help a user
write an excellent prompt and then improve it through measured, evaluation-driven
iteration. They sit *on top of* the existing `prompt-evals-*` lifecycle (the
measurement substrate) rather than reimplementing any of it.

- **`prompt-author`** — author a strong single-shot prompt from a task description,
  or refactor an existing prompt against best practices. Standalone, eval-free.
- **`prompt-improve`** — drive an iterate → measure → diagnose → rewrite loop that
  uses the existing eval framework to make a prompt measurably better, with explicit
  stopping rules.

This realizes the user's two-part framing — "write an excellent prompt" and
"orchestrate end-to-end improvement through evals" — while making explicit three
pieces that were implicit in that framing: (a) the success target lives in the
existing `prompt-evals-create-dataset` skill, (b) the loop's intelligence is the
diagnosis→technique mapping, and (c) the loop needs explicit stopping criteria.

## 2. Locked decisions (from brainstorming + design review)

| Decision | Choice | Why |
|---|---|---|
| Structure | **Two skills**, reuse `prompt-evals-*` | Matches the repo's composable-skill pattern; narrow `description`s trigger accurately; each skill stays small; no duplicate eval engine. |
| Author ↔ improve interface | **Shared references, follow procedure**: `prompt-improve` reads `prompt-author`'s technique references by `${CLAUDE_PLUGIN_ROOT}` path and runs the Mode B rewrite procedure inline | No dependency on runtime skill-invocation semantics. The catalogue has a **single physical home** (`prompt-author/references/`) with **two readers**. |
| Artifact scope | **Single-shot prompts**, structured to extend to agentic later | Coherent technique ladder; most common case; maps to the eval framework's base layer. Agentic = an additive future layer. |
| `prompt-author` modes | **Both**: generate (task → prompt) and improve-existing (prompt → refactor) | Shared catalogue makes mode B a small delta; covers the two most common eval-free requests; mode B is what the loop follows. |
| Loop control | **Hybrid (configurable)** | Checkpointed by default (human controls cost/direction); opt into "auto, up to N rounds" that streams deltas and stops early on threshold/regression. |

## 3. Architecture & composition

```
prompt-author        ──────────────►  a prompt (eval-free, single-shot)
  mode A: generate (task desc → prompt)
  mode B: improve  (existing prompt → refactored prompt)
        │
        │ (optional: take the authored prompt into a measured loop)
        ▼
prompt-improve       ──────────────►  a measurably-better prompt + trace
  preconditions: ./evals exists + a frozen dataset exists
  loop (hybrid control):
     prompt-evals-run  ──►  scored report (output.json)
        │                       ▲
        ▼                       │ re-measure on the SAME frozen dataset
     diagnose weaknesses        │
        │                       │
        ▼                       │
     follow prompt-author       │   (Mode B rewrite, using the SHARED
     Mode B (shared refs)  ─────┘    technique references + the diagnosis)
```

**Boundaries:**
- `prompt-author` is **standalone and eval-free** — needs only a task description
  (mode A) or an existing prompt (mode B). No `./evals`, no dataset, no API loop, and
  it **never touches `./evals`**. Ships value on its own.
- `prompt-improve` **orchestrates, never reimplements**. It calls `prompt-evals-run`
  to measure and performs each rewrite by **following `prompt-author`'s Mode B
  procedure against the shared technique references** (read by `${CLAUDE_PLUGIN_ROOT}`
  path) — not via a runtime skill call. The only new machinery it owns is diagnose →
  select technique → decide continue/stop. It also owns wiring the thin `run_prompt`
  loader into `./evals` (see §4).
- `prompt-improve` **does not define success criteria or build datasets** — that is
  `prompt-evals-create-dataset`'s job. Missing `./evals`/dataset → stop and route the
  user there (the precondition pattern `prompt-evals-run` already uses).

## 4. The file seam — prompt text vs. harness glue

There are two layers; only one is the prompt.

1. **The prompt itself (the engineered artifact) is text → a text file.** The
   currently-active prompt is always at a stable path,
   `evals/prompts_under_test/<name>.current.md`, with each round's candidate kept as
   `evals/prompts_under_test/<name>.vN.md`. It is what `prompt-author` emits and what
   a human reviews; it diffs cleanly across rounds (the readable record of which
   technique each round added); it is editable without touching code.
2. **The harness glue (`run_prompt` in `evals/run_eval.py`) is a few lines of code.**
   The framework invokes the prompt-under-test as a Python callable
   `run_function(prompt_inputs) -> str`, so an adapter must exist in code. It always
   loads the **stable active path**, renders the placeholders safely, calls the model,
   returns the text:

   ```python
   from evals.evaluator.templates import render   # framework's {placeholder} renderer

   def run_prompt(prompt_inputs: dict) -> str:
       template = Path("evals/prompts_under_test/<name>.current.md").read_text()
       prompt = render(template, **prompt_inputs)   # brace-safe; {{ }} escapes literals
       return call_model(prompt)                    # the model call
   ```

   **Brace safety (review item 3):** prompts are full of literal `{}` (JSON, schemas),
   so naive `str.format()` is forbidden. Use the framework's existing `render()`
   (`{placeholder}` with `{{ }}` escaping of literal braces) — or `string.Template`
   (`$var`, which sidesteps brace collisions entirely; preferable for JSON-heavy
   prompts). The chosen mechanism is an implementation detail, but it **must**:
   - fail if a declared placeholder is missing from `prompt_inputs`;
   - warn if `prompt_inputs` carries fields the template never uses;
   - record the detected placeholders as prompt metadata (so `create-dataset`'s
     `prompt_inputs_spec` and the template stay in sync).

**Versioning & active selection (review item 1):** `run_prompt` always loads
`<name>.current.md`. Each improvement round writes its candidate as the next
`<name>.vN.md`, then copies the chosen candidate into `<name>.current.md` *before*
running evals. The final report records every version evaluated and identifies the
best-scoring one.

**Consequence:** `run_prompt` is written **once** (thin loader; rarely changes). What
changes each round is the **text file**. `prompt-author` emits the text file and its
declared placeholders and **never touches `./evals`**; wiring the thin loader into
`./evals` is `prompt-improve`'s responsibility; `prompt-improve` versions and diffs the
text files and never rewrites code mid-loop.

## 5. `prompt-author` (Part 1)

**Purpose:** turn a task (or an existing prompt) into a well-built single-shot prompt
applying best practices. Standalone, eval-free, fast. Never touches `./evals`.

**Modes (one shared technique catalogue):**
- **Mode A — generate:** task description (+ optional input variables / output
  expectations) → a new prompt.
- **Mode B — improve:** an existing prompt (+ optional known issues, or a failure
  diagnosis supplied by `prompt-improve`) → a refactored prompt plus a short changelog
  of which techniques it applied and why.

**Technique catalogue** — `references/techniques.md`, an **escalation ladder**
(cheapest/highest-leverage first):

1. Be clear and direct (lead with the action; state task + key constraints)
2. Output guidelines + process steps (length, format, tone; ordered steps for complex tasks)
3. Examples (one-/multishot; `<example>` tags; diverse; corner cases)
4. XML structure (descriptive tags; separate instructions from data)
5. Role framing (see note below)
6. Adaptive thinking + reasoning scaffolding (for genuine multi-step reasoning tasks; "CoT" is the classic name)
7. Chaining (linked subtasks — the boundary of single-shot; flagged as such)
8. Long-context tips (docs first, query last, quote-first)

**v1 "role" means in-text role framing (review item 4).** Because v1 targets a single
text prompt, rung 5 is *role framing inside the prompt text*, not a separate API
`system` message. (A frontmatter `system:` / `user_template:` split that the loader
maps to real system/user messages is noted as a future option in §8, not v1.)

**Picks rungs; does not max out.** Greenfield authoring applies the high-leverage
baseline (1–2 plus light structure) and adds examples/role/CoT only when the task
warrants. Stacking all eight rungs is the over-engineering anti-pattern.

**`references/anti-patterns.md`:** say what to do (not what not to do); no
shouting/over-prompting (`CRITICAL: YOU MUST…`); keep examples consistent with edited
instructions; concrete ranges over "be concise"; don't ask the LLM to do what code
should; resolve conflicting/ambiguous rules; prefer adaptive thinking / private
reasoning over forcing *exposed* chain-of-thought.

**Best-practice-only / model-aware by construction:** no assistant prefill; no manual
`budget_tokens`; prefer adaptive thinking + `effort`; soften imperatives. (Same
principles as the prefill→structured-outputs fix already applied to the eval
framework.)

**Output:** the prompt as a text file (per §4) plus its declared `{placeholder}`
variables. Standalone use writes/prints the prompt to a path the user chooses and does
not modify `./evals`. `allowed-tools: Read, Write, Edit, Glob`.

## 6. `prompt-improve` (Part 2 — the loop)

**Preconditions** (same pattern as `prompt-evals-run`): `./evals` exists and a frozen
dataset exists. If not, stop and route to `prompt-evals-setup` /
`prompt-evals-create-dataset`. Owns no eval engine. On first use it wires the thin
`run_prompt` loader (§4) to load `<name>.current.md`.

**One round:**
```
baseline:  prompt-evals-run → output.json (avg score, pass rate, per-case verdicts)
diagnose:  aggregate the judge's weaknesses across cases → dominant failure theme(s)
   ├─ criteria problem? (see guard below) → STOP, route to create-dataset
select:    map theme → next ladder rung (priority below)
rewrite:   follow prompt-author Mode B (shared refs) + the diagnosis → prompt vN+1
           → copy candidate into <name>.current.md
re-eval:   prompt-evals-run on the SAME frozen dataset → new output.json
delta:     e.g. 6.2 → 7.8 (+1.6); weaknesses resolved / remaining
```

**Diagnosis → technique mapping** (`references/diagnosis.md`):

| Dominant failure theme | Next rung to escalate to |
|---|---|
| Mandatory-criterion failures (score capped ≤ 3) | Fix that gate **first** — explicit instruction/structure for the must-have |
| Missing required content | Process steps; examples showing the requirement |
| Format / structure drift, inconsistency across cases | XML structure + multishot examples |
| Shallow or wrong reasoning on hard cases | Adaptive thinking / reasoning scaffolding |
| Tone / style off | Role framing + output guidelines + examples |
| Conflicting / ambiguous instructions | Resolve the conflict (anti-pattern), don't add more |

**Diagnosis priority + tie-break (review item 7).** When several themes co-occur,
address them in this order:

1. Mandatory-criterion failures
2. Failures recurring across ≥ 30% of cases
3. Largest score-impacting weakness
4. Format / structure failures
5. Tone / style refinements

Ties resolve to the earliest item in this order unless the user overrides.

**Criteria-vs-prompt guard (review item 8).** Before escalating a technique, decide
whether the weakness is a *prompt* problem or a *criteria/dataset* problem.

- **Route to `create-dataset`** when: the judge complains about content not represented
  in the task inputs; the rubric demands a style/format never stated in the success
  criteria; the score rationale conflicts with the rubric; or the expected answer
  depends on hidden domain knowledge absent from the inputs.
- **Investigate (could be prompt non-determinism, not just bad criteria)** when:
  failures are inconsistent across semantically similar cases.
- **Do NOT route — it's a prompt problem** when: the prompt omitted required
  instructions; the model ignored a clearly-stated output format; or the model failed
  recurring reasoning steps.

**Hybrid control:** checkpointed by default — pause each round with diagnosis +
proposed technique + delta + remaining weaknesses; ask continue/stop/adjust. User can
opt into "auto, up to N rounds": streams each round's delta, stops early on threshold
or regression, then returns to checkpointed.

**Loop parameters (defaults; all tunable).**

| Parameter | Default | Meaning |
|---|---|---|
| `pass_threshold` | **`config.PASS_THRESHOLD` (currently 7)** — reused, not redefined | Avg-score bar for "good enough" |
| `pass_rate_target` | 0.80 | Fraction of cases ≥ threshold to target |
| `max_rounds` (N) | 3 | Hard cap on improvement rounds |
| `epsilon` (ε) | 0.25 | Minimum per-round avg-score gain that counts as progress |
| `diminishing_return_rounds` (K) | 2 | Consecutive sub-ε rounds before stopping |
| `regression_tolerance` | 0.0 | A round scoring below the current best is a regression |

**Stopping criteria.** Stop when **any** rule fires; if several fire, report all and
keep the **best-scoring** version:

- **Threshold met** — avg ≥ `pass_threshold` (or `pass_rate_target` reached).
- **Diminishing returns** — per-round delta < `ε` for `K` consecutive rounds.
- **Regression guard** — a round scoring below the current best is discarded; revert
  to the best version, then try a different rung or stop. Always keep/report the
  **best**, never the last if it's worse.
- **Budget cap** — `max_rounds` reached.

**Run trace & versioning (review item 5).** The framework already writes timestamped,
non-overwriting eval outputs to `evals/runs/<timestamp>/{output.json,output.html}` — the
loop does **not** duplicate those. It adds an auditable improvement trace that
**references** them:

```
evals/improve/<name>/<timestamp>/
  round-00-baseline/  { diagnosis.md, delta.json, run_dir → ../../runs/<ts> }
  round-01/           { prompt.v2.md (or version id), diagnosis.md, technique,
                        delta.json, decision, run_dir → ../../runs/<ts> }
  round-02/           ...
  final-report.md     (round-by-round trace, winning version, held-out result)
  final-report.json
```

**Overfitting / held-out (review item 9).** A built-in train/held-out split is
**deferred** (it would require framework changes; see §8). v1 uses the lightweight
guard: improve against the working dataset, then run a **final validation against a
separate held-out dataset** the user generates via `create-dataset`.

- The held-out set is **never** used for diagnosis, rewrite decisions, or version
  selection — leakage protection. It runs **once**, after the winner is selected.
- If no held-out dataset exists, produce the best working-dataset prompt and mark final
  validation **skipped** (not failed).

**Output:** versioned prompt files (`evals/prompts_under_test/<name>.vN.md` +
`<name>.current.md`), the improvement trace above, and a final report — the
round-by-round trace (technique applied, score delta, weaknesses resolved), the winning
version, and the held-out validation result (or "skipped").

**Frontmatter:** `name: prompt-improve`; third-person `description` covering *what*
(run an eval-driven loop that diagnoses a prompt's failures, applies the
next-best-technique, and re-measures until a stopping rule) and *when* (user wants to
optimize/iterate a prompt against an existing eval dataset); `argument-hint`;
`allowed-tools: Bash, Read, Write, Edit, Glob` (Bash invokes the eval runs).

## 7. Skill conventions & plugin wiring

- Follow the existing skills' conventions: third-person `description` (what + when),
  `argument-hint`, `version`, `${CLAUDE_PLUGIN_ROOT}` references, **Precondition** and
  **Definition of done** sections, an **Offline** note where relevant.
- Wire both new skills into the plugin `README.md` table and `.claude-plugin/plugin.json`
  (description + keywords), exactly as `prompt-evals-*` and `workflow-design-*` are.
- Names `prompt-author` / `prompt-improve` are the working choice; adjustable.

## 8. Non-goals (YAGNI) & future enhancements

**Out of scope for v1:**

- Agentic prompts (system prompts, tool descriptions, trajectory/process grading) —
  the design is structured to add this as an additive layer later.
- A built-in train/held-out dataset split in the framework (use the second-dataset
  approach in §6 instead).
- A real `system`/`user` message split via prompt frontmatter (v1 "role" is in-text
  framing — §5).
- Any new eval engine — reuse `prompt-evals-*` wholesale.
- Automatic success-criteria definition — that is `prompt-evals-create-dataset`.
- Judge panels / multi-sample grading (the framework notes single-judge variance; not
  this work's concern).

**Future enhancements:**

- Agentic technique catalogue + trajectory-aware diagnosis (the additive layer).
- Built-in held-out split in the eval framework.
- Frontmatter `system:` / `user_template:` prompt format with a loader that maps to
  real system/user messages.

## 9. Definition of done (for implementation)

**Files expected:**
```
skills/prompt-author/SKILL.md
skills/prompt-author/references/techniques.md
skills/prompt-author/references/anti-patterns.md
skills/prompt-improve/SKILL.md
skills/prompt-improve/references/diagnosis.md
README.md                       (updated: new lifecycle table)
.claude-plugin/plugin.json       (updated: description + keywords)
```

**Behavioral acceptance criteria** (manual / scenario checks — these skills are prose
procedures, not unit-testable code like the framework):

- Given a task description, `prompt-author` writes a valid prompt file with declared placeholders.
- Given an existing prompt + an issue list, `prompt-author` writes a refactored prompt plus a changelog.
- Given missing `./evals`, `prompt-improve` stops and routes to setup/create-dataset.
- Given an eval report with mandatory-criterion failures, `prompt-improve` selects the gate-fix path first.
- Given a regressing round, `prompt-improve` keeps the prior best version.
- Given multiple prompt versions, `run_prompt` evaluates `<name>.current.md` (the intended active version).
- `prompt-author` never modifies anything under `./evals`.

**Composition invariant:** the eval framework (`evals/evaluator/`, `evals/prompts/`) is
**unchanged** by this work — these skills compose it only.

## 10. Implementation clarifications (quick reference)

Consolidated seam decisions for the implementer (each is detailed in the section noted):

- **Active version (§4):** `run_prompt` loads `<name>.current.md`; rounds write `<name>.vN.md` then copy the chosen candidate into `.current.md` before eval; the report names the best version.
- **Rendering (§4):** brace-safe renderer (framework `render()` or `string.Template`), never `str.format()`; validate missing placeholders, warn on unused inputs, record placeholder metadata.
- **Skill reuse (§2/§3):** `prompt-improve` does **not** call `prompt-author` as a runtime function; it follows the Mode B procedure against the shared references read by `${CLAUDE_PLUGIN_ROOT}` path.
- **Run trace (§6):** per-round trace under `evals/improve/<name>/<timestamp>/` that *references* the framework's existing timestamped `evals/runs/` outputs; never duplicates or overwrites `output.json`.
- **Held-out (§6):** never used for diagnosis/selection; run once after the winner is chosen; "skipped, not failed" when absent.
- **Boundary (§5/§6):** `prompt-author` never touches `./evals`; `prompt-improve` owns thin-loader wiring.
