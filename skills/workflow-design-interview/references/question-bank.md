# Question bank

Per-stage elicitation prompts for `workflow-design-interview`. The interview runs
the 7 stages from `docs/WORKFLOW_DESIGN_SPEC.md` §6. For each stage this file lists
**open questions** (ask first, to elicit) then **closed confirmations** (ask after,
to lock the answer into the blueprint). Style: open questions then closed
confirmations; explain-the-why over all-caps; cite volatile Claude details from
`citations.md`.

Each stage names the blueprint fields it fills so the interviewer knows when the
stage is complete.

## Table of contents

1. [Stage 1 — Frame (5 Whys)](#stage-1--frame-5-whys)
2. [Stage 2 — Scope (MoSCoW)](#stage-2--scope-moscow)
3. [Stage 3 — Functional decomposition (closed input set)](#stage-3--functional-decomposition-closed-input-set)
4. [Stage 4 — Determinism pass (classification)](#stage-4--determinism-pass-classification)
5. [Stage 5 — Dimension sweep (per-dimension prompts)](#stage-5--dimension-sweep-per-dimension-prompts)
6. [Stage 6 — Success criteria (rubrics + outcomes)](#stage-6--success-criteria-rubrics--outcomes)
7. [Stage 7 — Assemble & hand off (saturation check)](#stage-7--assemble--hand-off-saturation-check)

---

## Stage 1 — Frame (5 Whys)

**Goal:** reach the *root* need, surface implicit "default requirements," and name
the stakeholders. Fills the Purpose / Stakeholders & context prose and
`preconditions`.

### Open questions

- In one sentence, what idea or problem do you want this workflow to solve?
- Who asked for this, and who is affected when it runs (operators, end-users,
  downstream systems, auditors)?
- Who consumes the output, and what decision or action does it drive?
- What happens today without this workflow? What is painful or manual about it?
- What must already be true in the world for this workflow to even start
  (data that exists, access that is granted, an event that fires)?

### 5 Whys (ask iteratively until the answer stops changing)

Take the stated goal and drill down. Ask "why" up to five times, each time on the
previous answer, to separate the *symptom* from the *root* need:

1. Why do you want `<the stated idea>`?
2. Why does `<that answer>` matter?
3. Why is `<that>` important — what breaks if it is missing?
4. Why is *that* the real cost — to whom, and how often?
5. Why is solving it with a *workflow* the right move (vs. a one-off, a policy
   change, or doing nothing)?

While drilling, listen for **implicit default requirements** the user assumes but
has not said — e.g. "obviously it must not double-charge anyone," "it has to run
unattended overnight," "the summary must be auditable." Name each one out loud and
capture it; these become `preconditions`, `guardrails`, or `postconditions` later.

### Closed confirmations

- "So the *root* need is `<restated root need>`, not just `<the surface symptom>` —
  correct?"
- "The primary stakeholder is `<X>`; the output consumer is `<Y>`. Yes?"
- "Before this workflow runs we can assume: `<precondition list>`. Anything else
  that must hold first?"
- "These unspoken defaults also apply: `<implicit requirements>`. Confirm?"

---

## Stage 2 — Scope (MoSCoW)

**Goal:** draw the cut line so the blueprint stays bounded. Establishes what v0.1 of
the *workflow* covers. Fills the prose scope note and informs which `steps`,
`outputs`, and `dimensions` are in play.

### Open questions

- If we shipped only one capability and nothing else, which one makes this worth
  building?
- What is explicitly out of scope — things people might assume are included but you
  do not want now?
- Are there cases you are happy to fail loudly on (rather than handle) in this
  version?

### MoSCoW sort (place every candidate capability in exactly one bucket)

For each capability the user names, ask which bucket it belongs in:

- **Must** — without it the workflow has no value; non-negotiable for this version.
- **Should** — important and painful to omit, but the workflow still delivers value
  without it; can ship in a fast-follow.
- **Could** — nice to have; include only if it is nearly free.
- **Won't (this time)** — explicitly deferred. Write these down so they are *decided*,
  not forgotten — they are the clearest scope signal.

Prompt: "Is `<capability>` a Must, Should, Could, or Won't for this version?"

### Closed confirmations

- "Must-haves: `<list>`. Anything on the Should list that is secretly a Must?"
- "Won't-do-this-time: `<list>`. We will not design for these — agreed?"
- "This gives us a cut line of `<one-line scope statement>`. Locked?"

---

## Stage 3 — Functional decomposition (closed input set)

**Goal:** define the closed set of inputs (with units/format), the external
dependencies, the outputs, the postconditions, and the ordered list of steps. Fills
`inputs`, `dependencies`, `outputs`, `postconditions`, and the skeleton of `steps`.

### Open questions

- What does the workflow consume to do its job — every piece of data, file, event,
  or parameter?
- For each input, what is its **type, unit, and format**? (e.g. "amount" → "USD
  decimal, 2dp"; "since" → "ISO-8601 date"; "report" → "PDF, ≤10MB").
- What external systems, services, datasets, or APIs does it depend on?
- What does it produce, and in what shape? Who or what receives each output?
- What must be *guaranteed true* after a successful run (postconditions)?
- Walk me through the happy path end to end — what are the discrete steps, in order?

### Closed input-set elicitation (lock the set, then the formats)

The input set is **closed**: list every key, then confirm nothing is missing and
nothing is extraneous. For each input confirm a description **with units/format**:

- "Inputs are exactly: `<key list>`. Is the set complete? Anything I should remove?"
- "`<key>` = `<description>`, format `<unit/format>`. Right?" (repeat per key)
- "Dependencies we rely on: `<list>`. Any hidden ones (auth provider, a cron, a
  queue)?"
- "Outputs are exactly: `<list>`, each in format `<format>`. Confirm?"
- "After a successful run these postconditions hold: `<list>`. Complete?"
- "The ordered steps are: `<id list>`. Did I miss a step, or merge two that should
  be separate?"

Capture each step as an `id` + a one-line purpose now; classification comes in
Stage 4.

---

## Stage 4 — Determinism pass (classification)

**Goal — the heart of the skill.** For every step, decide **deterministic vs.
agentic** with a written rationale, pick the matching `pattern`, and — only where
genuinely warranted — design subagents with the four-part contract and a Claude
`model` + `effort`. Enforces **simplicity-first**. Fills each step's `kind`,
`rationale`, `pattern`, `side_effecting`, `reversible`, `termination`, and the
`subagents` list.

> Load `patterns.md` (pattern catalog + escalation rules) and `model-selection.md`
> (model + effort heuristics) for this stage. Claude models only for now; concrete
> model IDs live in `citations.md`.

### Determinism-classification questions (per step)

- Does this step have a single correct output computable by rules/code, or does it
  need open-ended judgment over ambiguous input?
- Could you write a unit test that asserts the *exact* expected output? If yes, it is
  almost certainly **deterministic** — prefer code.
- What is the failure mode if it is wrong — and would a human reviewing it say "the
  code has a bug" (deterministic) or "the model used poor judgment" (agentic)?
- Is the variability in the input *bounded* (finite cases → code/routing) or
  *unbounded* (free text, novel situations → agentic)?
- If agentic: what makes it irreducibly a judgment call rather than a lookup table or
  a regex?

### Pattern selection (map the step to a `pattern:` value)

Ask, then set the matching value from `patterns.md`:

- Is this a fixed sequence of subtasks where each feeds the next? → `chain`
- Does it classify the input and send it down one of several known paths? → `route`
- Can independent subtasks run at the same time (sectioning or voting)? → `parallelize`
- Does a coordinator dynamically decide and spawn the subtasks at runtime? → `orchestrate`
- Does a generator produce, then a checker score-and-feedback in a loop? → `evaluate`
- Is it a plain LLM call with tools/retrieval, no delegation? → `none` (augmented LLM)
- Is it ordinary code with no model at all? → `none`

### Simplicity-first escalation (justify every jump up the ladder)

- "Can deterministic code do this reliably? If yes, we use code and mark it
  `deterministic`." (Default to the bottom of the ladder.)
- "An inline LLM call inside a step is **not** a subagent. Do we actually need a
  *separate* delegated agent here, or just a model call in the step?"
- "If we add a subagent: what makes this work genuinely *independent* and
  *breadth-first*? Multi-agent runs cost roughly ~15× the tokens of a single chat
  (Anthropic-reported), so we only escalate when that breadth earns the cost."
- "Every loop and every agentic step needs a stop condition. What ends this one — a
  done-state, a budget, or a max-iteration count?"

### Model + effort (per agentic step / subagent — see `model-selection.md`)

- "What does the output need to be — structured/exact, or open synthesis?"
- "How hard is the reasoning — lookup, comparison, or deep multi-step?"
- "Given that, I recommend `model: <haiku|sonnet|opus>` at `effort: <low..max>`
  because `<rationale>`. Easy → Haiku, harder → Sonnet/Opus; effort scales with depth."

### Closed confirmations

- "Step `<id>` is `<deterministic|agentic>` because `<rationale>`, pattern `<value>`.
  Confirm?" (repeat per step)
- "`<id>` is side-effecting=`<bool>`, reversible=`<bool>`. Right?"
- "We are adding `<N>` subagent(s): `<list>` — each justified by `<reason>`. Or can we
  do this with fewer / none?"
- "Nesting stays one level deep: the orchestrator is the main conversation, subagents
  do not spawn their own subagents. Agreed?"

---

## Stage 5 — Dimension sweep (per-dimension prompts)

**Goal:** account for *every* cross-cutting dimension. Each is captured as
`specified` or explicitly `{n/a: "<rationale>"}` — never left blank. Fills the
`dimensions` map, plus `budgets` and `guardrails`.

> Load `dimensions.md` for the normative definition of each dimension (what
> "specified" requires and when `n/a` is legitimate). Walk the 12 in schema order.

For each dimension, ask the open question; if the user says it does not apply, ask
the closed `n/a` confirmation to capture a *rationale*, not a blank.

### Per-dimension prompts (12, in schema order)

1. **observability** — "How will we know what the workflow did and whether it
   worked — logs, traces, metrics, a run record? What gets recorded per step?"
2. **cost_latency_budgets** — "What is the acceptable latency and cost per run? Any
   hard ceiling we must not exceed?"
3. **guardrails_permissions** — "What is this allowed to touch, and what must it
   never touch? Least-privilege scopes, injection defense on untrusted input?"
4. **context_management** — "For LLM steps, what context goes in, and how do we keep
   it within the window — summarization, retrieval, artifacts on disk?"
5. **human_in_the_loop** — "Where does a human approve, review, or get notified?
   Which steps are risk-tiered to `notify` vs `explicit` approval?"
6. **state_artifact_passing** — "How does state move between steps — inline values,
   files, a shared store? What is the handoff format?"
7. **failure_handling** — "For each step, what can go wrong, and what happens when it
   does — fail fast, skip, escalate, degrade gracefully?"
8. **retry_idempotency** — "Which steps are safe to retry? For side-effecting ones,
   what is the idempotency key that prevents double-execution?"
9. **rollback_compensation** — "If a reversible step succeeds but a later one fails,
   what compensating action undoes it (saga-style)?"
10. **termination_conditions** — "What stops every loop and agentic step — a
    done-state, a budget, a max-iteration count? No open-ended loops."
11. **tool_selection** — "Which tools/APIs does each agentic step get, and why that
    minimal set? (Least-privilege allowlist.)"
12. **evaluation_success** — "How do we judge a run succeeded — which outputs are
    checked, against what? (Feeds Stage 6 rubrics/outcomes.)"

### Closed confirmations (per dimension)

- "**Specified:** `<dimension>` = `<the answer captured>`. Correct?"
- "**N/A:** `<dimension>` does not apply because `<rationale>`. Capture as
  `{n/a: '<rationale>'}`?" (A cop-out like "n/a: not needed" is not acceptable —
  push for a real reason.)

End-of-stage gate: "Every one of the 12 dimensions is now `specified` or
`{n/a: rationale}`. Confirmed — none left blank?"

---

## Stage 6 — Success criteria (rubrics + outcomes)

**Goal:** define how success is judged. Fills `rubrics` (categorical integer scale,
per-level definitions, pass/fail gate, reference-based?, judge) and `outcomes`
(Given-When-Then end-states).

> Load `rubric-templates.md` for reusable rubric shapes and filled examples.

### Rubric prompts (open)

- What does a *great* output look like vs. a merely acceptable vs. a failing one?
- What quality dimensions matter — correctness, completeness, citation fidelity,
  tone, safety? Name each you want to grade.
- Is there a known-correct answer to grade against (reference-based), or are we
  judging open quality (reference-free)?
- Who is the judge — a human reviewer, or an LLM-as-judge?
- Where is the pass/fail line — what score is "good enough to ship"?

### Rubric closed confirmations (per rubric)

- "Rubric `<name>`: integer scale `<e.g. 1-5>` (not floats), with levels
  `<1: ..., 3: ..., 5: ...>`. Confirm the level definitions discriminate?"
- "Pass gate = `<int>`; reference_based = `<true|false>`; judge = `<human|llm>`.
  Right?"

### Outcome prompts (open, Given-When-Then)

- Give me a concrete end-to-end scenario: given some starting state, when the
  workflow runs, what observable end-state proves it worked?
- What is the most important *failure* scenario to assert — given a bad input, when
  it runs, then what should happen (reject, escalate, no side effect)?

### Outcome closed confirmations (per outcome)

- "Outcome: **given** `<state>`, **when** `<the workflow runs>`, **then** `<observable
  result>`. All three present and testable?"

---

## Stage 7 — Assemble & hand off (saturation check)

**Goal:** write `./workflows/<name>.blueprint.md` from `assets/blueprint-template.md`,
run the saturation check, and direct the user to `workflow-design-validate`.

### Assembly

- "I will write the blueprint to `./workflows/<name>.blueprint.md`. Is `<name>` the
  right slug?"
- Fill the frontmatter, the prose (Purpose / Stakeholders & context / Rationale), and
  the single fenced `yaml` block with every top-level key and all 12 dimensions.

### Saturation check (signals the interview is done)

Ask the saturation question; if it surfaces something new, loop back to the relevant
stage rather than writing prematurely:

- "Is any **new** requirement, risk, step, or edge case still emerging as we review —
  or have we stopped finding new things?"
- "Reading the blueprint back: does anything feel missing, hand-wavy, or contradicted
  by another part?"
- "Are there steps whose outputs do not feed any downstream input, or inputs nothing
  produces?"

When the answer is "nothing new is emerging," the interview has reached **saturation**
— write the file.

### Hand off

- "Blueprint written to `./workflows/<name>.blueprint.md` (status: `draft`)."
- "Next: run `/je-dev-skills:workflow-design-validate` to check completeness. Fix any
  reported gaps, re-run until it passes, then set `status: validated`."
