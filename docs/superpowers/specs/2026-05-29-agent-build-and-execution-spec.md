# Design: In-Claude-Code Execution + the `agent-build-*` Orchestrator + Plugin Composition

**Date:** 2026-05-29
**Status:** Approved design (companion to the prompt-engineering revision) — **revised 2026-05-29**
after adversarial verification corrected the execution model (in-process Python cannot dispatch
subagents; the keyless path is skill-orchestrated, not an `LLMClient` swap). Ready for implementation
planning.
**Plugin:** `je-dev-skills`

> **Why this spec exists.** The critical review surfaced items that are **plugin-wide**, not specific
> to `prompt-engineering-*`. Two decisions resolved them: (1) the plugin builds agent applications
> that run **inside Claude Code with no API key on the interactive path**; (2) the missing "design →
> running agent" arrow is owned by a **new `agent-build-*` group** that subsumes the deferred
> `workflow-design-scaffold`. This spec defines the **execution substrate** all skills share, the
> **orchestrator group**, and the **unified plugin composition**. The prompt-engineering spec
> ([`2026-05-29-prompt-engineering-skills-design.md`](./2026-05-29-prompt-engineering-skills-design.md))
> consumes the substrate defined here.

---

## 1. Purpose & the gap it closes

The plugin's goal is to **help build high-quality agent applications, efficiently, with deterministic
code over non-deterministic where possible, loadable as a Claude Code plugin.** Before this spec it
covered **design** (`workflow-design-*`, explicitly "a design artifact, not a runtime"), **authoring +
improvement** (`prompt-engineering-*`), and **measurement** (`prompt-evals-*`). Nothing turned a
validated design + authored prompts into a **running agent** (review finding `no-scaffold-running-agent`);
`workflow-design-scaffold` was deferred to v0.2. This spec brings it forward as the **`agent-build-*`**
group, closing the arrow:

```
workflow-design-*  →  prompt-engineering-author  →  agent-build-*  →  prompt-evals-*  →  prompt-engineering-improve
   (design)              (author prompts)            (build + run)       (measure)            (improve, looped)
   (interactive path: in Claude Code on session auth, no API key · headless/CI: keyed fallback)
```

The execution banner above is **deliberately qualified** — the "no API key" property holds for the
interactive subagent-dispatch path only; headless/CI runs require a key (§2.1). Every diagram and
README sentence in both specs carries this qualifier.

---

## 2. The execution substrate — "no direct API calls", precisely scoped

### 2.1 The honest boundary (doc-grounded)

"No API key" is **true for the interactive Claude-Code-driven path** and **not achievable for
standalone programmatic loops**:

| Mechanism | Auth | Use here |
|---|---|---|
| **Subagent dispatch** via the Agent/Task tool, **driven by the interactive Claude Code session** | **Session auth — NO `ANTHROPIC_API_KEY`** | **Canonical path.** The orchestrating Claude dispatches subagents to execute steps, run the (single-shot) prompt-under-test, and grade. |
| **Claude Agent SDK `query()`** (Python/TS) | **Requires `ANTHROPIC_API_KEY`** (does *not* inherit CC session auth) | **Headless/CI fallback only.** |
| **Headless `claude -p`** | Requires `ANTHROPIC_API_KEY` (or `apiKeyHelper`) | Fallback for scripted/CI runs. |

Hard runtime constraints every design here respects:
- **Subagents cannot nest** (leaf nodes) — orchestration is **one level**: the top-level session/skill
  dispatches; subagents do not dispatch sub-subagents. (Consistent with `workflow-design`'s
  one-level-nesting rule and the Workflow tool's nesting limit.)
- **Subagent frontmatter has no `output_format`** — structured grading is achieved by instructing the
  subagent to emit JSON and **parsing + validating it in deterministic glue**. The framework provides
  `jsonio.parse_json` (a single bracket-slice repair, then it **raises** — there is **no** retry loop)
  and closed-key-set validation in `schemas.py` (`validate_verdict` / `verdict_schema`). If
  retry-on-invalid-JSON is wanted for subagent output, it must be **added** to the aggregation glue as
  a new behavior — the framework does not already have it.
- **In-process Python cannot dispatch a subagent.** A `complete_json()` / `run_prompt()` function
  running inside `PromptEvaluator.run_evaluation`'s worker pool is *not* the interactive agent and has
  no Agent/Task tool. The keyless path therefore **cannot** be an `LLMClient` swap or a Python loop —
  it must be **skill-orchestrated** (§2.2).
- **Structured output on the keyed path** is provided by the SDK's `output_config` json_schema, which
  the repo already uses (`evaluator/client.py:99-102`). The keyed fallback relies on **that** (real,
  in-repo) — not on any headless `--json-schema`/`--bare` flag, which the research pass did **not**
  confirm and which is therefore recorded in `references/citations.md` as unverified-pending-runtime.

> **Verify-before-build.** These facts are dated 2026-05 and some are version-volatile (the
> 2026-06-15 Agent-SDK/headless billing split; subagent frontmatter fields; any headless structured
> flag). Implementation must re-verify against the live docs and `~/.claude` before relying on a
> field. Volatile specifics live in a dated `references/citations.md`, never hardcoded in skill prose.

### 2.2 The two eval execution paths (the corrected substrate)

The framework abstracts model calls behind the `LLMClient` Protocol (`evaluator/client.py`), but the
keyless property cannot be obtained at that seam (a subagent can't be dispatched from synchronous
Python — §2.1). So there are **two distinct paths**, selected by `config.EXECUTION_MODE`:

**Path A — no-key, skill-orchestrated (canonical, `EXECUTION_MODE=in_claude_code`).** This path does
**not** use `PromptEvaluator.run_evaluation` at all. The **interactive skill** (`prompt-evals-run`,
driven by Claude) runs the loop itself:
1. Read the frozen dataset (deterministic).
2. **For each case:** render the prompt with the case's `prompt_inputs` (deterministic prompt-prep
   glue), then **the orchestrating Claude dispatches an execute-subagent** (runs the single-shot
   prompt-under-test) and a **grade-subagent** (judges the output against the case criteria + global
   `EXTRA_CRITERIA`, emits the verdict JSON). These are Claude turns via the Agent/Task tool — **session
   auth, no key**.
3. Each returned verdict JSON is written to disk.
4. A **new deterministic aggregation helper with NO model calls** — `evals/aggregate.py` (vendored
   **top level**, beside `run_eval.py`; **not** in `evaluator/`), invoked as a **CLI by the skill**
   after the per-case JSONs are written — reads the collected verdict JSONs, validates them
   (`schemas.validate_verdict`), and writes `evals/runs/<run_label>/{output.json,output.html}` via the
   framework's report writers, imported by submodule path
   `from evals.evaluator.report import summarize, write_json, write_html` (they are **not** re-exported
   from `evaluator/__init__.py`). It **accepts a `run_label`** (mirroring `run_evaluation`'s
   dir-naming) so callers get a deterministic `run_dir`.

   Because step 2 is the Claude turn (not Python), there is **no callable `run_in_claude_code()`**;
   the "executor" is the dispatched subagent, and `aggregate.py` is offline glue, not an `LLMClient`.
   This path is **single-shot only**: a multi-subagent prompt-under-test would require the
   execute-subagent to dispatch its own subagents (two levels — forbidden). See §2.4.

**Path B — keyed fallback (headless/CI, `EXECUTION_MODE=anthropic_api`).** The existing
`run_eval.py evaluate` → `PromptEvaluator.run_evaluation` in-process loop with `AnthropicClient` for
executor **and** judge. `run_prompt` is the executor seam; structured grading via SDK `output_config`.
Requires `ANTHROPIC_API_KEY`; supports agentic `Trajectory`; suitable for unattended automation.

### 2.3 The bounded framework change

The framework **core algorithms are untouched**: `evaluator/{evaluator,generate,grade,run,schemas,
jsonio,templates,report,client}.py` and `prompts/` do not change. The substrate is added **outside**
that core:
- **NEW** `evals/aggregate.py` (vendored top level) — the deterministic no-model aggregation helper
  for Path A.
- **CHANGED** `evals/config.py` — add `EXECUTION_MODE` (`in_claude_code` default | `anthropic_api`
  fallback) + the subagent model/effort knobs Path A dispatch uses. **`config.py` edits are owned by
  this spec** (the prompt-engineering loop puts its loop-params in `run_eval.py` to avoid colliding
  here).
- **CHANGED** `evals/run_eval.py` (per-project, editable) — file-backed `<name>.current.md` +
  `render()` + the `check_placeholders` prompt-prep glue as default; **`main()` becomes mode-aware**:
  under `EXECUTION_MODE=in_claude_code` (the default) the `evaluate` command does **not** call
  `run_evaluation` — measurement on Path A is driven by the `prompt-evals-run` skill (subagent
  dispatch) and the report is assembled by `aggregate.py`, so `evaluate` prints that guidance and
  exits non-zero; the keyed in-process `run_evaluation` runs **only** under
  `EXECUTION_MODE=anthropic_api`, with `run_label` threaded through. (`check_placeholders` lives here,
  in vendored `evals/`-level glue — **never** in `evaluator/` or under `skills/`.)
- **CHANGED** `prompt-evals-run/SKILL.md` — its run procedure becomes Path A (skill dispatches
  execute+grade subagents → `aggregate.py`), with Path B documented as the keyed fallback. (This file
  is **also** edited by the prompt-engineering spec, which re-scopes its §4 diagnosis to single-pass +
  cites the shared `diagnosis.md`. The two edits merge into one coherent SKILL.md; **this spec owns the
  run-procedure rewrite**, the prompt-engineering spec owns the diagnosis re-scope.)

All new code lands in the shipped template at
`skills/prompt-evals-setup/framework/evals/` and is copied to a user's `./evals` by
`prompt-evals-setup`. **`prompt-evals-setup`'s vendoring must ship `aggregate.py` and the updated
`config.py`/`run_eval.py`**, and re-running setup must add them to existing `./evals` copies (a
non-clobbering update note for the setup skill).

### 2.4 Evaluating agentic (multi-subagent) applications

When the artifact under test is itself a scaffolded **multi-subagent app** (agent-build output fed to
prompt-evals — the lifecycle arrow), the no-nesting rule blocks Path A from wrapping it in an
execute-subagent. Two supported options, stated so neither over-promises:
1. **Top-level orchestration:** the eval harness runs the agent app as the **top-level** orchestration
   for that case (the skill *is* the agent's entry point) and grades via a **sibling** subagent —
   never nesting the app inside an execute-subagent.
2. **Keyed/headless (Path B):** agentic-app evaluation runs through the Agent SDK / keyed path.

**v1 scope:** the **no-key interactive path supports single-shot prompts only** — matching the
prompt-engineering group's single-shot v1 cut. Multi-subagent-app evaluation is a keyed/headless
capability (or the top-level-orchestration variant) and is **not** claimed for the no-key path.

### 2.5 Determinism within the substrate

Everything that is computation stays code: prompt loading + brace-safe `render()`, placeholder sync
(`check_placeholders`), JSON validation of subagent output (`schemas.validate_verdict`), aggregation
(`summarize`), report writing (`report.py`). Only the generative work — executing the
prompt-under-test, grading rationale — is a (subagent-dispatched, no-key) model call. The plugin's
north star applied to the harness itself.

---

## 3. The `agent-build-*` group (Option A — subsumes scaffold)

A new skill group that turns a **validated blueprint** (`workflow-design-validate` output) + **authored
prompts** (`prompt-engineering-author` output) into a **running, Claude-Code-native agent application**
and drives it. It realizes the deferred `workflow-design-scaffold` plus a runtime entry point.

### 3.1 Two skills (lifecycle: scaffold → run)

| Skill | Invoke | What it does |
|---|---|---|
| `agent-build-scaffold` | `/je-dev-skills:agent-build-scaffold` | Render a validated blueprint + authored prompts into Claude-Code-native artifacts: subagents, hooks, scripts, an orchestration entry point. Deterministic generation where possible. |
| `agent-build-run` | `/je-dev-skills:agent-build-run` | Drive the scaffolded application **in-session** (dispatch steps in order; deterministic steps as scripts/hooks, agentic steps as subagents), honoring gates, loops, termination. **Ships in this cut** (so the "build + run" lifecycle label is honest). |

### 3.2 Blueprint element → Claude-Code construct (the rendering map)

| Blueprint element | Rendered to | Determinism |
|---|---|---|
| **deterministic step** | a plain **script** (Bash/Python) the orchestrator calls | deterministic |
| **agentic step** | a **subagent** (`.claude/agents/<name>.md`) carrying the full four-part contract (next row) + a non-contract `model` in frontmatter | non-deterministic, contained |
| **subagent four-part contract** = **objective · output-spec · tools · boundaries** (canonical: `WORKFLOW_DESIGN_SPEC.md` §4, what `workflow-design-validate` gates on) | `tools` → frontmatter `tools`; **objective**, **output-spec** (the contract's `output_format` field — rendered as a **body section**, *never* a frontmatter key, since subagent frontmatter has no `output_format`), and **boundaries** → body sections. `model`/`effort` are separate **non-contract** fields → frontmatter `model` | — |
| **rubric gate / guardrail** | a **hook** (`PreToolUse`/`Stop`/`SubagentStop`) enforced by an exit-code script | deterministic |
| **loop + termination** | orchestrator control flow with the **explicit termination** condition as a deterministic check | deterministic control, agentic body |
| **side_effecting / reversible** | step wrapped with idempotency-key / rollback handling in the script | deterministic |
| **authored prompt** (`<name>.current.md`) | the prompt text a step's subagent runs | — |
| **orchestration entry point** | a **slash command / skill** (interactive, session auth, no key) that dispatches the steps **one level deep** | deterministic sequencing |

**Why a slash command / skill is the entry point:** it keeps the runtime **inside Claude Code on
session auth (no key)**, dispatching subagents one level deep. A headless wrapper is a **non-goal for
v1** (§6) — not presented as a "thin wrapper", because it is unconfirmed whether Agent SDK `query()`
loads project `.claude/agents/*.md` + hooks with the same semantics.

### 3.3 Determinism & simplicity-first (inherited)

`agent-build-scaffold` enforces what `workflow-design` already encodes: **deterministic code for
anything reliable/repeatable/auditable; subagents only for genuinely open-ended steps; every subagent
gets the four-part contract; every loop an explicit termination.** It must **warn (not silently
expand)** when a blueprint uses a subagent where a deterministic script would do.

### 3.4 Volatility containment

Scaffolding touches the most version-volatile Claude-Code surface (subagent frontmatter fields, model
aliases, effort levels, hook event names) — why `workflow-design` deferred it. Mitigate as
`workflow-design` does: a dated `references/citations.md` for all volatile specifics; the
blueprint→artifact mapping stays declarative; a `verify-against-runtime` step before emitting files.

### 3.5 Relationship to existing SDK tooling

The plugin already references `agent-sdk-dev` / `new-sdk-app`. `agent-build-*` targets the
**in-Claude-Code, no-key** runtime (subagents/skills/hooks). A keyed Agent-SDK entry point is a v1
**non-goal/open question** (§6), not a deliverable — it does not duplicate the SDK app scaffolder.

---

## 4. Plugin composition & wiring (the unified story)

### 4.1 One journey (fixes `plugin-wiring-three-group-story`)

The plugin is **one lifecycle**, not separate islands:

> **Build high-quality agent applications inside Claude Code, end to end:** **design** the workflow
> into a validated blueprint (`workflow-design-*`), **author** the prompts (`prompt-engineering-author`),
> **build & run** the agent as Claude-Code-native artifacts — no API key on the interactive path
> (`agent-build-*`), **measure** it (`prompt-evals-*`), and **improve** it through an eval-driven loop
> (`prompt-engineering-improve`). Headless/CI execution uses a keyed fallback (`ANTHROPIC_API_KEY`).

### 4.2 README & `plugin.json` changes

- `README.md`: **replace both existing per-group lifecycle blurbs** (the prompt-evals and
  workflow-design sentences) with the single unified design→author→build→measure→improve narrative
  above + a lifecycle diagram; add an `agent-build-*` group row. Do **not** merely append a row and
  leave two islands. Include a short **cost note**: headless/CI runs draw on the Agent-SDK/headless
  credit (the 2026-06-15 billing split — verify wording at build time).
- `.claude-plugin/plugin.json`: rewrite `description` to the one-journey sentence; update `keywords`.
  Since `agent-build-run` **ships in this cut**, **keep `orchestration`** as a keyword, precisely
  scoped to the in-CC runtime (it previously over-promised a runtime that did not exist — review
  `no-scaffold-running-agent`).
- `docs/WORKFLOW_DESIGN_SPEC.md` §9: **relocate** the `workflow-design-scaffold` roadmap entry — it is
  superseded by `agent-build-*` here. Add a one-line pointer so the two specs don't both claim
  scaffolding.

### 4.3 Group naming & convention

All groups follow group-verb: `workflow-design-*`, `prompt-engineering-*`, `agent-build-*`,
`prompt-evals-*`.

---

## 5. Definition of done

**Files expected (new/changed)** — framework lives at `skills/prompt-evals-setup/framework/evals/`,
copied to `./evals` by `prompt-evals-setup`:
```
skills/prompt-evals-setup/framework/evals/aggregate.py    (NEW: deterministic no-model aggregation for Path A; accepts run_label)
skills/prompt-evals-setup/framework/evals/config.py       (CHANGED: EXECUTION_MODE + subagent model/effort knobs)
skills/prompt-evals-setup/framework/evals/run_eval.py     (CHANGED: file-backed .current.md + render() + check_placeholders; run_label through main())
skills/prompt-evals-setup/framework/evals/evaluator/*.py  (UNCHANGED core; client.py keeps AnthropicClient as keyed fallback)
skills/prompt-evals-setup/SKILL.md                        (CHANGED: vendoring ships aggregate.py; re-setup adds new files non-clobbering)
skills/prompt-evals-run/SKILL.md                          (CHANGED: run procedure → Path A subagent dispatch; keyed fallback documented.
                                                            Merged with the prompt-engineering spec's §4 single-pass-diagnosis edit.)
skills/agent-build-scaffold/SKILL.md
skills/agent-build-scaffold/references/  (blueprint→artifact mapping, citations.md, patterns)
skills/agent-build-scaffold/scripts/     (deterministic renderers + offline unittest tests)
skills/agent-build-run/SKILL.md
README.md                                (CHANGED: unified lifecycle replaces both island blurbs + agent-build row + cost note)
.claude-plugin/plugin.json               (CHANGED: one-journey description + keywords incl. scoped 'orchestration')
docs/WORKFLOW_DESIGN_SPEC.md             (CHANGED: relocate scaffold roadmap entry → agent-build-*)
```

**Acceptance criteria** (split offline vs. interactive, per the runtime reality):
- **Offline (unit-testable, repo standard):** given fixture verdict JSONs, `aggregate.py` produces the
  correct `output.json`/`output.html` via `summarize()`/`report.py` **with no API key and no model
  call**; `agent-build-scaffold`'s deterministic renderers pass offline `unittest` fixtures; the
  scaffold **warns** when a blueprint uses a subagent where a script would do (no silent expansion).
- **Interactive (manual integration check, explicitly not unit-testable):** in an interactive session
  with **no `ANTHROPIC_API_KEY`**, `prompt-evals-run` dispatches execute+grade subagents per case and
  `aggregate.py` produces a report; given a validated blueprint + authored prompt,
  `agent-build-scaffold` emits subagent/hook/script files + an entry-point command and `agent-build-run`
  drives them.
- **Keyed fallback:** with `EXECUTION_MODE=anthropic_api` and a key, `run_evaluation` still works
  (headless/CI), supporting agentic `Trajectory`.

**Composition invariant (plugin-wide, named files):** the framework **core** —
`evaluator/{evaluator,generate,grade,run,schemas,jsonio,templates,report,client}.py` and `prompts/` —
is **unchanged**. The substrate is added **outside** the core: new `aggregate.py`, changed
`config.py`/`run_eval.py`, changed SKILLs. No skill calls the `anthropic` SDK on the interactive path.

---

## 6. Non-goals (v1) & open questions

**Non-goals:**
- A keyed **Agent-SDK entry-point wrapper** around the CC-native layer — it is unconfirmed that
  `query()` loads project `.claude/agents/*.md` + hooks with the same semantics, so v1 does **not**
  ship it or present it as a "thin wrapper." (Open question 7 below.)
- Multi-level subagent nesting (runtime forbids it; orchestration stays one level).
- Evaluating multi-subagent apps on the **no-key** path (single-shot only there — §2.4).
- Retry-on-invalid-JSON in the framework (it has none; add to `aggregate.py` glue only if needed).
- Auto-tuning models/effort per step (the blueprint/scaffold recommends; the human approves).

**Open questions (re-verify against the live runtime before building — from the research pass):**
1. Does a subagent spawned from a skill **inherit the parent session's permission mode**, or must each
   declare its own `tools`/permissions?
2. Does a skill-dispatched subagent's context include the **working directory/repo**, or is it isolated?
3. Do **hooks** (`PreToolUse`/`SubagentStop`) fire for subagents dispatched within a skill, or only at
   the parent session level?
4. Can a skill pass **inline agent definitions** (`--agents`) to a dispatched subagent, or must they be
   on-disk in `.claude/agents/`?
5. Confirm the **2026-06-15 Agent-SDK/headless billing split** wording for the README cost note.
6. For Path A: confirm **per-case subagent dispatch** throughput/latency for `~2N` dispatches per
   round vs. the keyed path, and document the trade-off so users pick a mode knowingly.
7. Does Agent SDK `query()` load project `.claude/agents/*.md` + hooks (would a keyed headless wrapper
   get the same subagent/hook semantics)?
8. Is there a confirmed headless structured-output flag (`--json-schema`/`--bare`)? Until confirmed,
   the keyed structured path relies on the SDK `output_config` (real), not a headless flag.

---

## 7. Source grounding

Architecture grounded in a dated research pass (2026-05-29) over the official Claude Code / Agent SDK
docs (subagents, Agent SDK overview + structured outputs, headless mode) and the repo's `LLMClient`
seam + `evaluator/` code. The load-bearing "no API key" claim was adversarially checked and returned
**partial** — true for interactive subagent dispatch, false for the Agent SDK / headless paths — which
is why §2.1 draws the boundary explicitly and the diagrams/README carry the qualifier rather than
claiming a blanket "no API calls anywhere." A second verification pass corrected the execution model:
in-process Python cannot dispatch subagents, so the keyless path is skill-orchestrated (§2.2), not an
`LLMClient` swap. Volatile specifics are dated and must be re-verified at implementation time.
