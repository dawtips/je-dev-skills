# Workflow Design Meta-Skill — Specification & Design

A reusable, **invocable** specification for a domain-agnostic meta-skill group that
turns an idea into a checked **workflow blueprint** through a staged discovery
interview, then validates that blueprint for completeness. It defines the skill
group, the blueprint artifact, the elicitation flow, the validation contract, the
prescribed folder layout, and the v0.1 cut line with a v0.2 roadmap.

> **How to use this spec.** This is the design document brainstormed on 2026-05-29.
> The implementation plan is derived from it via the writing-plans skill. Everything
> here is the reference the implementation consults. Source grounding is in §10.

---

## 1. Purpose

The skill group answers one question: **"What's the simplest workflow that solves
this, and is its design complete enough to build?"** — for any workflow,
automation, agent, or pipeline, regardless of domain.

It is a **discovery interview → workflow blueprint** lifecycle. The human supplies
an idea; the meta-skill elicits the design rigorously, captures it as a structured
artifact, and gates that artifact on completeness before anyone writes code.

The decisive design principle, drawn from every Anthropic source in §10:
**start simple and only add complexity (subagents, loops) when justified.** Use
deterministic code for anything that must be reliable, repeatable, or auditable;
reserve agentic reasoning for genuinely open-ended steps. Every subagent gets a
four-part contract; every loop gets an explicit termination condition.

**Scope.** The blueprint is **implementation-agnostic** at its core (steps,
contracts, rubrics, dimensions any team or tool could implement) with an *optional*
Claude-Code rendering layer planned on top (§9). It is a **design artifact**, not a
runtime — this group does not execute workflows.

---

## 2. The lifecycle & skill group

A new skill group `workflow-design-*` in the `je-dev-skills` plugin, mirroring the
shape of the `prompt-evals-*` lifecycle.

```
   idea
    |
    v
+--------------------------+        +---------------------------+
| workflow-design-interview|  -->   | workflow-design-validate  |  --> (repeat)
| staged elicitation       |        | deterministic completeness|
| -> blueprint.md          |        | gate + gap report         |
+--------------------------+        +---------------------------+
                                              |
                                              v
                          ./workflows/<name>.blueprint.md  (validated)
```

**v0.1 ships two skills:**

| Skill | Invoke | What it does |
|-------|--------|--------------|
| `workflow-design-interview` | `/je-dev-skills:workflow-design-interview` | Staged discovery interview; emits a blueprint (Markdown + structured YAML) to the target project. |
| `workflow-design-validate` | `/je-dev-skills:workflow-design-validate` | Runs a deterministic validator/coverage-scorer over a blueprint; reports gaps, linter-style. |

The lifecycle is **interview → validate (repeat until green)**. The scaffold,
LLM-review, and visual layers are **v0.2** (§9).

---

## 3. Repo layout

```
skills/
  workflow-design-interview/
    SKILL.md
    references/                # progressive disclosure, loaded per interview stage
      blueprint-schema.md      # the YAML schema + one annotated example
      dimensions.md            # normative coverage checklist (starting list ∪ Section 7)
      question-bank.md         # per-stage elicitation prompts
      patterns.md              # Building-Effective-Agents catalog + when to escalate
      model-selection.md       # Claude model + effort guidelines (routing, effort-scaling)
      rubric-templates.md      # rubric shapes: categorical scales, level defs, gates
      citations.md             # dated source URLs; volatile Claude-Code details live here
    assets/
      blueprint-template.md    # the artifact skeleton the interview fills
  workflow-design-validate/
    SKILL.md
    scripts/
      validate_blueprint.py    # deterministic; matches the repo's Python idiom
      requirements.txt         # PyYAML (see §5)
      tests/                   # stdlib unittest over good/bad fixtures, offline
docs/
  WORKFLOW_DESIGN_SPEC.md      # this document
```

Plus updates to `README.md` (new group row + lifecycle note) and `plugin.json`
(description + keywords).

**Progressive disclosure.** Each `SKILL.md` body stays under ~500 lines and acts as
a table of contents. Reference files load only when the relevant interview stage is
reached. Volatile Claude-Code specifics (exact subagent frontmatter field names, the
Task→Agent tool rename, model IDs) are cited from `references/citations.md` with
dates — never hardcoded into the schema or skill prose.

---

## 4. The blueprint artifact

One Markdown file per workflow at `./workflows/<name>.blueprint.md` in the target
project (path configurable). Design artifacts live versioned alongside the code they
will drive. The file has three layers:

1. **YAML frontmatter** — metadata: `name`, `version`, `status` (`draft` |
   `validated`), `created`.
2. **Prose sections** — Purpose, Stakeholders & context, Rationale (the
   "explain-the-why"), optional DAG/diagram. Human-read; not machine-checked.
3. **One fenced `yaml` block** — the **validated structured core**, the single
   source of truth the validator loads.

### 4.1 Structured core schema

The structured core covers the user's starting list **∪** the research's Section-7
cross-cutting dimensions. The validator (§5) parses *this block only*.

```yaml
preconditions: [...]            # Hoare-style: what must hold before the workflow runs
inputs:                         # the closed set the workflow consumes
  - {key, description, format}  # each with units/format
dependencies: [...]             # external systems, data, services relied upon
outputs: [...]
postconditions: [...]           # what is guaranteed after successful completion
steps:
  - id: <slug>
    kind: deterministic | agentic
    rationale: "why this classification"     # REQUIRED — enforces simplicity-first
    pattern: chain|route|parallelize|orchestrate|evaluate|none
    side_effecting: true|false               # declares external side effects → drives the retry check
    reversible: true|false                   # declares the step can be undone → drives the rollback check
    inputs: [...]
    outputs: [...]
    failure_modes: [...]
    retry: {policy, idempotency_key}         # REQUIRED if step is side-effecting
    rollback: "compensating action"          # REQUIRED if step is reversible
    approval_gate: none | notify | explicit  # risk-tiered human-in-the-loop
    termination: "done condition / budget"   # REQUIRED if step is a loop or agentic
subagents:                       # only where delegation is genuinely warranted
  - id: <slug>
    objective: "..."             # four-part contract:
    output_format: "..."         #   objective, output format,
    tools: [...]                 #   tools/sources (least-privilege allowlist),
    boundaries: "..."            #   task boundaries
    model: sonnet|opus|haiku|inherit
    effort: low..max
dimensions:                      # coverage map — EVERY dimension accounted for
  observability: specified | {n/a: "rationale"}
  cost_latency_budgets: specified | {n/a: "rationale"}
  guardrails_permissions: specified | {n/a: "rationale"}
  context_management: specified | {n/a: "rationale"}
  human_in_the_loop: specified | {n/a: "rationale"}
  state_artifact_passing: specified | {n/a: "rationale"}
  failure_handling: specified | {n/a: "rationale"}
  retry_idempotency: specified | {n/a: "rationale"}
  rollback_compensation: specified | {n/a: "rationale"}
  termination_conditions: specified | {n/a: "rationale"}
  tool_selection: specified | {n/a: "rationale"}
  evaluation_success: specified | {n/a: "rationale"}
rubrics:
  - name: <slug>
    scale: 1-5                   # categorical integer, NOT unanchored floats
    levels: {1: "...", 3: "...", 5: "..."}   # explicit per-level definitions
    gate: <int>                  # pass threshold
    reference_based: true|false  # is there a known-correct answer to grade against?
    judge: human|llm
outcomes:                        # observable, testable end-states (Given-When-Then)
  - {given: "...", when: "...", then: "..."}
budgets: {max_turns, max_tool_calls, latency_note, cost_note}
guardrails: [...]                # least-privilege, injection defense, access scoping
```

### 4.2 Worked examples

The three examples below span the complexity range. They double as validator test
fixtures (§5) and as the `references/blueprint-schema.md` annotated example.

**Example 1 — Mostly deterministic (simplest sufficient architecture).** A scheduled
job turning a sales CSV into a Slack summary. No LLM judgment → `subagents: []`,
most dimensions `n/a` with rationale, no rubrics (nothing generative to grade).
Demonstrates that **completeness ≠ filling everything in** — every dimension is
*accounted for*, many as justified `n/a`.

**Example 2 — Single agentic step (routing).** Triage an inbound support email and
route it. One LLM classification step (`kind: agentic`, `pattern: route`) plus a
deterministic enqueue. Crucially `subagents: []` — an inline augmented-LLM call is
**not** a delegated subagent. Includes an `explicit` approval gate on low confidence,
injection defense on untrusted body text, and a `routing_accuracy` rubric graded
against a labeled set — which feeds directly into the `prompt-evals-*` lifecycle.

**Example 3 — Orchestrator-workers (justified multi-agent).** A competitive-research
brief — the case where breadth-first parallelism earns the ~15× token cost. A `plan`
(orchestrate) step, a parallel `research-each` step backed by a read-only
`competitor-researcher` subagent with the full four-part contract, a `synthesize`
(chain) step, and a deterministic `verify-citations` step. Captures the artifact
pattern (`state_artifact_passing`), the one-level-nesting constraint (orchestrator is
the main conversation), and an explicit token-cost justification in `budgets`.

The full YAML for all three lives in `references/blueprint-schema.md` and is copied
verbatim into the validator's test fixtures.

---

## 5. `workflow-design-validate` — the deterministic gate

A thin skill wrapping a deterministic Python script,
`scripts/validate_blueprint.py`, matching the repo's Python idiom and the principle
"code for anything that must be reliable and repeatable."

**Procedure:** take a blueprint path → extract the single fenced `yaml` block →
parse it → check structural completeness against the §4.1 schema → emit a pass/fail
plus a gap report keyed by path (e.g. `steps[2].rationale: missing`). Exit code 0 =
green; non-zero = gaps listed.

**Checks:**

- Every dimension in the §4.1 `dimensions` map is present as `specified` or
  `{n/a: "<non-empty rationale>"}` → produces a **coverage score**
  (e.g. `12/12 dimensions accounted for`).
- Each `step` has a `kind` *and* a non-empty `rationale`.
- Every entry in `subagents` has the **full four-part contract** (objective,
  output_format, tools, boundaries all non-empty) plus a non-empty `model` and
  `effort`, and a workflow containing any `subagents` has at least one `agentic`
  step to justify them.
- Any step with `side_effecting: true` has `retry.idempotency_key`; any step with
  `reversible: true` has `rollback`; any `agentic` step has a non-empty `termination`.
- Each `rubric` has a categorical `scale`, per-level `levels` definitions, and a
  `gate`.
- Each `outcome` has all three of `given` / `when` / `then`.

**Dependency decision (resolved):** the script uses **PyYAML** — a small, ubiquitous
dependency declared in the validate skill's `requirements.txt` — for ergonomic
parsing of the fenced block. (The rejected alternative was constraining the block to
JSON-compatible YAML and parsing with stdlib `json` to stay zero-dependency; PyYAML
was chosen for author ergonomics, accepting one dependency.)

**Tests:** stdlib `unittest` over fixtures, matching the eval framework's offline
ethos — Examples 1–3 (§4.2) pass; deliberately broken blueprints (missing rationale,
half a subagent contract, a gate-less rubric, an unaccounted dimension) each fail
with the *right* gap and a non-zero exit. Runs fully offline, no API key.

**Skill flow:** run script → read gap report → fix blueprint → re-run until green →
report coverage score. **Definition of done = exit 0 and all dimensions accounted
for.**

The validator's output contract is designed to leave room for the v0.2 LLM
design-review layer (§9) to run as an additional, optional pass.

---

## 6. `workflow-design-interview` — the elicitation flow

A staged discovery interview that fills the §4.1 structured core one topic at a
time, using progressive disclosure (each stage loads only its `references/` file).
Modeled on rigorous BA / solution-architect elicitation.

**Stages (the SKILL.md body, ≤500 lines, acting as a table of contents):**

1. **Frame** — stakeholders, goal, problem. Apply "5 Whys" to reach the *root* need
   and surface implicit "default requirements." → Purpose/Stakeholders prose +
   `preconditions`.
2. **Scope (MoSCoW)** — Must / Should / Could / Won't. Establishes the cut line;
   keeps the blueprint bounded.
3. **Functional decomposition** — `inputs` (closed set, with units/format),
   `dependencies`, `outputs`, `postconditions`, and the `steps` list.
4. **Determinism pass** — *the heart of the skill.* For each step: classify
   deterministic vs. agentic **with a written rationale**, select the
   Building-Effective-Agents `pattern`, and — only where genuinely warranted —
   design subagents with the four-part contract. Enforces **simplicity-first**:
   recommend the simplest sufficient architecture and *justify every escalation* to
   a subagent or loop (citing the ~15× multi-agent token cost); honor the
   one-level-nesting constraint. For each agentic step / subagent, recommend a
   Claude `model` and `effort` level **with a rationale**, guided by desired output,
   task complexity, and cost/token minimization (easy → Haiku, harder →
   Sonnet/Opus; effort scales with task depth). Loads `references/patterns.md` and
   `references/model-selection.md`. Claude models only for now; model IDs live in
   `references/citations.md` so they update as the lineup changes.
5. **Dimension sweep** — walk every Section-7 dimension (failure handling,
   retry/idempotency, human-in-the-loop gates, state/artifact passing, context
   management, observability, guardrails/permissions, budgets, termination,
   rollback, tool selection, evaluation). Each is captured *or* explicitly marked
   `n/a` with rationale. Loads `references/dimensions.md`.
6. **Success criteria** — `rubrics` (categorical integer scale, per-level
   definitions, pass/fail gate, reference-based?, judge=human/llm) and `outcomes` as
   Given-When-Then end-states. Loads `references/rubric-templates.md`.
7. **Assemble & hand off** — write `./workflows/<name>.blueprint.md` from
   `assets/blueprint-template.md`, then direct the user to `workflow-design-validate`.
   A **saturation check** ("anything new emerging?") signals the interview is done.

**Style guardrails (from §10):** open questions then closed confirmations;
"explain-the-why" over all-caps MUST/NEVER; volatile Claude-Code specifics cited from
`references/citations.md` with dates, never hardcoded.

**Description field** (discovery-critical): third person, gerund-named, with trigger
phrases such as *"design a new workflow / automation / agent / pipeline," "scope a
solution before building," "turn an idea into a workflow blueprint."* Written
slightly "pushy" per skill-authoring guidance, since Claude tends to under-trigger.

---

## 7. Requirement → blueprint mapping

Each elicited requirement maps onto blueprint elements:

| Elicited | Blueprint element |
|----------|-------------------|
| Preconditions / postconditions | Hoare-style contracts per step + workflow-level `preconditions`/`postconditions` |
| Functional requirements | `steps` / `subagents` |
| Non-functional requirements ("ilities") | `budgets`, `guardrails`, `dimensions` |
| Acceptance criteria (Given-When-Then) | `outcomes` + `rubrics` |
| Ordering / parallelism | `steps` DAG with `pattern` + `approval_gate` |

---

## 8. Testing & evaluation

- **Validator:** stdlib `unittest` fixtures (§5) — Examples 1–3 pass; broken
  blueprints fail with the right gap. Offline, no API key.
- **Interview skill:** dogfooded — run a representative discovery session end-to-end,
  produce a blueprint, confirm it validates green. ("Start with evaluation.")
- **Integration with `prompt-evals-*`:** a blueprint's `rubrics`/`outcomes` are the
  same shape `prompt-evals-create-dataset` consumes. Flagged as a future handoff, not
  built in v0.1.

---

## 9. v0.2+ roadmap (non-goals for v0.1)

- `workflow-design-review` is specified in
  [WORKFLOW_DESIGN_REVIEW_SPEC.md](WORKFLOW_DESIGN_REVIEW_SPEC.md) and implemented
  as the v0.2 advisory semantic review skill. It runs after deterministic
  validation and writes a scored `.review.md` report next to the blueprint.
- **`workflow-design-scaffold` - superseded by `agent-build-*`.** Rendering a
  validated blueprint into the Claude-Code layer (subagents, hooks, scripts, and
  an entry-point command) is now owned by the `agent-build-*` group. See
  [2026-05-29-agent-build-and-execution-spec.md](2026-05-29-agent-build-and-execution-spec.md)
  §3.
- **Automated model-selection advisor — shipped as `workflow-design-advise` (T-015).**
  The *guideline* form ships in v0.1 (§6, stage 4: the interview recommends a Claude
  `model` + `effort` per agentic step / subagent, with rationale, from
  `references/model-selection.md`). The *automated* form is now built: a deterministic
  scorer (`skills/workflow-design-advise/scripts/advise_model.py`) that reads the
  validated blueprint, scores each agentic step (advisory) and subagent (writeable)
  against the routing + effort-scaling tables, and flags over/under-provisioned
  `subagents[].model`/`effort`. Built as a deliberate override of the §2.4 "maybe-never"
  gate (see `2026-05-30-workflow-design-advanced-tooling-spec.md` §2.6); Claude models
  only; recommends tiers, not pinned IDs.
- **Visual viewer (v0.3+)** — render a blueprint visually: the step **flow** (a DAG showing
  ordering, parallel sections, approval gates, and deterministic-vs-agentic coloring)
  plus **drill-down** into each step's and subagent's details. Two tiers, cheapest
  first:
  - *Tier 1 — Mermaid (shipped as `workflow-design-visualize`, T-016):* deterministically
    generates a Mermaid flowchart from the same fenced `yaml` block and emits a sibling
    `<name>.diagram.md` (flowchart in steps-list order + drill-down tables). Renders for
    free in GitHub / VSCode / Markdown previews, zero runtime. See
    `2026-05-30-workflow-design-advanced-tooling-spec.md` §3.6.
  - *Tier 2 — browser viewer (gate opened 2026-06-08; T-026):* a self-contained,
    interactive `<name>.viewer.html` with clickable nodes → step / subagent detail
    panels, a 12-dimension panel, and filters. Read-only navigation in Phase A;
    in-browser editing and execution-driving are deferred, gated phases. Contract:
    [2026-06-08-workflow-design-interactive-viewer-spec.md](2026-06-08-workflow-design-interactive-viewer-spec.md).

All of these are purely additive and read from (or fill) the schema locked in §4 —
v0.1 is unchanged by them.

**Other non-goals:** no execution engine (the blueprint is a design artifact, not a
runtime); no automatic handoff into `prompt-evals-*`.

---

## 10. Source grounding

The design is anchored on primary Anthropic sources first; third-party material is
secondary corroboration. Volatile platform details are cited with dates and isolated
in `references/citations.md`.

- **Agent Skills authoring** (SKILL.md frontmatter, progressive disclosure,
  scripts-vs-instructions, discovery-optimized descriptions) — Anthropic Agent Skills
  overview + best practices.
- **Subagent orchestration** (`.claude/agents/` markdown, the Agent/Task tool,
  one-level-deep delegation, context isolation, the four-part subagent contract,
  effort-scaling heuristics) — Claude Code sub-agents doc + the multi-agent research
  system post.
- **Workflow patterns** (prompt chaining, routing, parallelization,
  orchestrator-workers, evaluator-optimizer, augmented LLM; "start simple") —
  "Building Effective Agents" (Schluntz & Zhang, Dec 19 2024).
- **Requirements elicitation** (functional/non-functional, MoSCoW, INVEST,
  Given-When-Then, definition of done, saturation) — classical requirements
  engineering.
- **Evaluation rigor** (LLM-as-judge with explicit rubrics, categorical integer
  scales, calibration, judge biases) and **workflow formalisms** (Hoare-logic
  pre/postconditions, design-by-contract, DAGs/state machines, Temporal-style retry /
  idempotency / saga compensation) — for the contract, dimension, and rubric
  vocabulary.

**Caveats carried into the build:** cite doc versions/dates and avoid hardcoding
values likely to change (the Task→Agent rename, model IDs); treat the "max parallel
subagents" figure as community lore, not official; some Anthropic eval figures
(90.2% improvement, ~15× tokens) are internal benchmarks, present them as
Anthropic-reported.

---

## 11. v0.1 definition of done

- `workflow-design-interview` + `workflow-design-validate` skills exist with
  discovery-optimized descriptions.
- `references/` complete: blueprint schema + annotated example, normative dimensions
  checklist, per-stage question bank, BEA pattern catalog, model-selection
  guidelines, rubric templates, dated citations.
- `validate_blueprint.py` + offline tests green.
- `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` (this document) written and committed.
- `README.md` + `plugin.json` updated for the new group.
