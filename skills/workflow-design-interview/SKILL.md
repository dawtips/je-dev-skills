---
name: workflow-design-interview
description: This skill should be used when the user wants to "design a workflow", "scope an automation, agent, or pipeline before building", "turn an idea into a workflow blueprint", "plan an agentic workflow", or needs a structured discovery interview before implementation. It runs a staged elicitation and writes a checked ./workflows/<name>.blueprint.md.
argument-hint: "[short name for the workflow, e.g. order-refund]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Design a workflow (discovery interview)

Run a staged discovery interview that turns an idea into a checked
**workflow blueprint** at `./workflows/<name>.blueprint.md`. The interview fills the
structured core defined in
`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §4.1 one topic at a time, then
hands off to `workflow-design-validate`.

The guiding principle is **simplicity-first**: find the simplest workflow that solves
the problem. Use deterministic code for anything that must be reliable, repeatable, or
auditable; reserve agentic reasoning for genuinely open-ended steps. Justify every
escalation to a subagent or loop.

## How to run this skill

This SKILL.md is a **table of contents** over the 7 stages below. Work the stages in
order. **Progressive disclosure:** load each stage's `references/` file only when you
reach that stage — do not preload them all. The detailed wording of every question
lives in `references/question-bank.md` (one section per stage); the stages below name
*which* questions to ask and which fields they fill, not the full prompts.

Take the argument as the workflow's short `<name>` (e.g. `order-refund`). If none was
given, ask for one before Stage 7. Keep an in-progress draft of the structured core as
you go; you assemble and write the file in Stage 7.

All reference paths are under
`${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-interview/references/` and the template
under `.../assets/`.

## Style

- **Open questions first, then closed confirmations.** Each stage in
  `question-bank.md` is split into open elicitation followed by closed
  confirmations — surface the design with open questions, then lock each decision
  with a yes/no confirmation before moving on.
- **Explain-the-why over all-caps.** Give the reasoning behind a recommendation
  (e.g. why a step should stay deterministic) rather than issuing bare MUST/NEVER
  directives.
- **Cite volatile details with dates.** Anything that drifts — Claude model IDs, the
  Task→Agent tool rename, the "max parallel subagents" community lore — comes from
  `references/citations.md` (its "Volatile values" section), cited with an "as of"
  date. Never hardcode these into your prose.

---

## Stage 1 — Frame

**Ask:** stakeholders, goal, and problem. Apply the **5 Whys** to reach the root need
and surface implicit "default requirements."

**Load:** `references/question-bank.md` (Stage 1 — Frame).

**Fills:** the **Purpose** and **Stakeholders & context** prose sections, plus the
workflow-level `preconditions` (what must hold before the workflow runs).

---

## Stage 2 — Scope (MoSCoW)

**Ask:** sort every candidate capability into **Must / Should / Could / Won't**. This
establishes the cut line and keeps the blueprint bounded.

**Load:** `references/question-bank.md` (Stage 2 — Scope).

**Fills:** the **Rationale** prose section — specifically what is in scope now and what
was deliberately left out ("Won't"). The Must/Should set seeds the `steps` list built
in Stage 3.

---

## Stage 3 — Functional decomposition

**Ask:** the closed set of `inputs` (each with units/format), the external
`dependencies`, the `outputs`, the `postconditions` (what is guaranteed after success),
and the ordered `steps` list. Lock the input set, then pin down each input's format.

**Load:** `references/question-bank.md` (Stage 3 — Functional decomposition).

**Fills:** `inputs`, `dependencies`, `outputs`, `postconditions`, and the skeleton of
`steps` (ids only at this stage; classification comes next).

---

## Stage 4 — Determinism pass

This is the heart of the skill. For each step:

1. **Classify** it `deterministic` vs `agentic` **with a written `rationale`** — the
   `rationale` field is required on every step and is what enforces simplicity-first.
2. **Select the `pattern`** (`chain` | `route` | `parallelize` | `orchestrate` |
   `evaluate` | `none`) from the Building-Effective-Agents catalog.
3. **Set `side_effecting` and `reversible`** so the validator can demand `retry` and
   `rollback` where they are needed, and set `termination` on every agentic step.
4. **Design subagents only where genuinely warranted** — each with the full four-part
   contract (`objective`, `output_format`, `tools` as a least-privilege allowlist,
   `boundaries`) plus a `model` and `effort`.
5. **Recommend a Claude `model` + `effort`** per agentic step / subagent, with a
   rationale, guided by desired output, task complexity, and cost/token minimization.

**Simplicity-first rule (state it to the user):** recommend the **simplest sufficient
architecture** and **justify every escalation**. Prefer deterministic code for anything
that must be reliable, repeatable, or auditable. An inline augmented-LLM call is **not**
a delegated subagent. Only escalate to subagents for genuinely independent,
breadth-first work, citing the ~15x multi-agent token cost (Anthropic-reported; see
`citations.md`). Honor the **one-level-deep nesting** constraint (the orchestrator is
the main conversation). Every loop and every agentic step needs an explicit
`termination` condition.

**Load:** `references/patterns.md` (pattern catalog + escalation rules) **and**
`references/model-selection.md` (routing: easy → Haiku, harder → Sonnet/Opus;
effort-scaling). Claude models only for now; concrete model IDs come from
`references/citations.md`.

**Fills:** each step's `kind`, `rationale`, `pattern`, `side_effecting`, `reversible`,
`termination`, and per-step `retry` / `rollback` where flagged; the whole `subagents`
list with its four-part contracts, `model`, and `effort`.

---

## Stage 5 — Dimension sweep

**Ask:** walk **every** cross-cutting dimension and capture each one. Each dimension
must end up either `specified` or `{n/a: "<rationale>"}` — a blank or bare TODO is a
gap. The 12 dimensions (schema order): observability, cost_latency_budgets,
guardrails_permissions, context_management, human_in_the_loop, state_artifact_passing,
failure_handling, retry_idempotency, rollback_compensation, termination_conditions,
tool_selection, evaluation_success.

**Load:** `references/dimensions.md` — the normative checklist with, per dimension, a
definition, what "specified" requires, and when `n/a` is legitimate.

**Fills:** the entire `dimensions` map. **Requirement:** every one of the 12 dimensions
must be specified or carry a non-empty `{n/a: rationale}` before you proceed — this is
exactly what the validator's coverage score checks.

---

## Stage 6 — Success criteria

**Ask:** the `rubrics` (categorical integer `scale`, explicit per-level `levels`
definitions, a pass/fail `gate`, `reference_based?`, and `judge: human|llm`) and the
`outcomes` as **Given-When-Then** end-states. Rubrics are empty if nothing generative
is graded.

**Load:** `references/rubric-templates.md` — reusable rubric shapes and 2–3 filled
templates (correctness, completeness, citation fidelity). These match the shape
`prompt-evals-create-dataset` consumes (a future handoff).

**Fills:** `rubrics` and `outcomes`, plus `budgets` and `guardrails` if not already
captured in earlier stages.

---

## Stage 7 — Assemble & hand off

1. **Write the blueprint.** Start from
   `${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-interview/assets/blueprint-template.md`,
   fill in the frontmatter (`name`, `version`, `status: draft`, `created`), the three
   prose sections (Purpose / Stakeholders & context / Rationale), and the **single
   fenced `yaml` block** with every top-level key and all 12 dimensions. Write it to
   `./workflows/<name>.blueprint.md` in the target project (create `./workflows/` if it
   does not exist). Keep **exactly one** `yaml` fence — it is the source of truth the
   validator parses.

2. **Run the saturation check.** Ask "is anything new still emerging?" (see
   `references/question-bank.md`, Stage 7). When new questions stop producing new design
   content, the interview is saturated and done.

3. **Hand off to `workflow-design-validate`.** Direct the user to run it on the new
   file (`/je-dev-skills:workflow-design-validate`). Iterate
   interview → validate until it reports "12/12 dimensions accounted for" and exits 0;
   then flip `status:` to `validated`.

**Load:** `references/question-bank.md` (Stage 7 — Assemble & hand off) and the
template in `assets/`.

**Fills:** writes the complete `./workflows/<name>.blueprint.md`.

---

## Definition of done

A blueprint file is written at `./workflows/<name>.blueprint.md` that **passes
`workflow-design-validate`** — exit code 0 with all 12 dimensions accounted for. Until
the validator is green, the interview is not complete: fix each reported gap in the
`yaml` block and re-run.
