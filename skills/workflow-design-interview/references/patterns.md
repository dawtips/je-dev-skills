# Patterns catalog & escalation rules

The workflow patterns from Anthropic's "Building Effective Agents" (Schluntz &
Zhang, 19 Dec 2024) plus the augmented-LLM building block, and the simplicity-first
rules that govern *when* to escalate from one to the next. Loaded by Stage 4 of the
interview (the determinism pass). Source grounding: `docs/WORKFLOW_DESIGN_SPEC.md`
§10; see `citations.md` for dated URLs and volatile caveats.

The governing principle from every Anthropic source: **start simple; only add
complexity (subagents, loops) when it measurably improves outcomes.** Each pattern
below maps to a `pattern:` value in the blueprint's `steps` schema.

## Table of contents

1. [The building block: augmented LLM](#the-building-block-augmented-llm)
2. [Pattern: prompt chaining](#pattern-prompt-chaining)
3. [Pattern: routing](#pattern-routing)
4. [Pattern: parallelization](#pattern-parallelization)
5. [Pattern: orchestrator-workers](#pattern-orchestrator-workers)
6. [Pattern: evaluator-optimizer](#pattern-evaluator-optimizer)
7. [Pattern quick-reference table](#pattern-quick-reference-table)
8. [Simplicity-first escalation rules](#simplicity-first-escalation-rules)
9. [The four-part subagent contract](#the-four-part-subagent-contract)
10. [One-level-deep nesting constraint](#one-level-deep-nesting-constraint)
11. [The ~15x token-cost caveat](#the-15x-token-cost-caveat)
12. [Every loop needs a termination condition](#every-loop-needs-a-termination-condition)

---

## The building block: augmented LLM

**Definition.** A single LLM call enhanced with retrieval, tools, and/or memory. It
decides which tools to call and what to retrieve, all within one conversation. This
is the atomic unit every pattern is composed from — not itself a multi-step
"pattern."

**When to use.** Whenever one model call with the right context and tools can do the
job. This is the default for any agentic step. Reach for a *pattern* only when one
augmented-LLM call cannot.

**Matching `pattern:` value:** `none` (it is a single agentic step, not an
orchestration). An augmented-LLM call is **not** a subagent — keep `subagents: []`
unless work is genuinely delegated.

---

## Pattern: prompt chaining

**Definition.** Decompose a task into a fixed sequence of steps, each LLM call
processing the output of the previous one, with optional programmatic gates
("checks") between steps.

**When to use.** The task cleanly splits into fixed, ordered subtasks and you are
trading latency for higher accuracy by making each call simpler. The decomposition
is known *ahead of time* (not decided at runtime).

**Matching `pattern:` value:** `chain`.

---

## Pattern: routing

**Definition.** Classify the input, then direct it down one of several specialized,
known paths. Separates concerns so each path can be optimized independently.

**When to use.** There are distinct categories of input that are better handled
separately, and classification can be done accurately (by a model or by rules).
Common for triage, tiered support, and easy-vs-hard model selection.

**Matching `pattern:` value:** `route`.

---

## Pattern: parallelization

**Definition.** Run independent LLM subtasks simultaneously and aggregate. Two
flavors: **sectioning** (split a task into independent pieces run in parallel) and
**voting** (run the same task several times for diverse outputs / majority).

**When to use.** Subtasks are genuinely independent so they can run concurrently for
speed, or you want multiple attempts for confidence. The set of subtasks is fixed and
known up front (contrast with orchestrator-workers, where it is dynamic).

**Matching `pattern:` value:** `parallelize`.

---

## Pattern: orchestrator-workers

**Definition.** A central orchestrator LLM **dynamically** breaks down a task,
delegates subtasks to worker LLMs at runtime, and synthesizes their results. The
subtasks are not predetermined — the orchestrator decides them based on the input.

**When to use.** You cannot predict the subtasks in advance (e.g. how many sources to
research, which files to change). This is the canonical justified-multi-agent case —
breadth-first, independent work where parallelism earns the token cost.

**Matching `pattern:` value:** `orchestrate`.

---

## Pattern: evaluator-optimizer

**Definition.** One LLM generates a response; a second LLM evaluates it against
criteria and returns feedback; the generator revises. Repeats in a loop until the
evaluation passes or a budget is hit.

**When to use.** There are clear evaluation criteria, iterative refinement
measurably helps, and a critic can articulate *why* an output falls short (mirrors a
human editor's revise loop). Requires an explicit termination condition.

**Matching `pattern:` value:** `evaluate`.

---

## Pattern quick-reference table

| Pattern | `pattern:` value | Subtasks decided | Use when |
|---------|------------------|------------------|----------|
| Augmented LLM | `none` | — (single call) | One model call + tools/retrieval suffices |
| Prompt chaining | `chain` | Ahead of time | Fixed ordered subtasks; trade latency for accuracy |
| Routing | `route` | Ahead of time | Distinct input categories, accurate classification |
| Parallelization | `parallelize` | Ahead of time | Independent subtasks (sectioning) or voting |
| Orchestrator-workers | `orchestrate` | At runtime | Subtasks unpredictable; breadth-first delegation |
| Evaluator-optimizer | `evaluate` | — (loop) | Clear criteria + iterative refinement helps |
| Plain code | `none` | — (no model) | A rule/computation with one correct output |

---

## Simplicity-first escalation rules

Climb this ladder only as far as the task forces you. Justify every rung above the
first in the step's `rationale`.

1. **Prefer deterministic code.** Anything that must be reliable, repeatable, or
   auditable, and has a single correct output, is code — mark the step
   `kind: deterministic`. Do not spend a model call where a function will do.
2. **Then a single augmented-LLM call.** If judgment is needed but one model call
   with tools/retrieval can do it, that is the step. `pattern: none`,
   `subagents: []`. **An inline LLM call is not a subagent.**
3. **Then a workflow pattern** (chain / route / parallelize / evaluate) — a fixed,
   known composition of calls, still no delegated agents.
4. **Only then subagents (orchestrate).** Escalate to delegated subagents *only* for
   genuinely **independent, breadth-first** work whose subtasks cannot be predicted
   in advance. This is the most expensive rung (see the ~15× caveat) — the breadth
   must earn the cost. Avoid the "50 subagents for a simple query" over-engineering
   smell.

Rule of thumb: if you cannot write a one-line `rationale` for why a simpler rung is
insufficient, you are over-engineering — drop down a rung.

---

## The four-part subagent contract

Every entry in the blueprint's `subagents` list must carry a complete contract.
A partial contract is an incompletely-specified delegation and the validator rejects
it. The four parts (plus `model`/`effort`):

1. **objective** — the single, bounded goal of this subagent ("research one
   competitor"). One agent, one job.
2. **output_format** — the exact shape it must return ("JSON `{competitor,
   findings[], sources[]}`"), so the orchestrator can consume it deterministically.
3. **tools** — the **least-privilege allowlist** of tools/sources it may use. A
   non-empty list; grant only what the objective needs.
4. **boundaries** — what it must *not* do ("only the assigned competitor; do not
   synthesize across competitors"), keeping workers from overlapping or overreaching.

Plus a recommended `model` and `effort` (see `model-selection.md`).

---

## One-level-deep nesting constraint

Delegation stays **one level deep**: the orchestrator is the *main conversation*, and
subagents are its direct workers. Subagents do **not** spawn their own subagents.
This keeps the call graph debuggable, context isolation comprehensible, and cost
bounded. If a worker seems to need its own workers, the task decomposition is wrong —
flatten it back up to the orchestrator. (Volatile platform specifics — exact agent
frontmatter, the Task→Agent tool rename — are in `citations.md`, not hardcoded here.)

---

## The ~15x token-cost caveat

Anthropic reports that multi-agent systems can use on the order of **~15× the tokens**
of a single-agent chat for the same wall-clock task (an Anthropic-reported figure
from the multi-agent research post, not a hard law — present it as such). Treat this
as the price of admission for the orchestrate rung: only pay it when breadth-first
parallelism genuinely speeds up or improves the outcome. Record the justification in
the step `rationale` and the trade-off in `budgets.cost_note` (e.g. "~15x a single
chat, justified by breadth").

---

## Every loop needs a termination condition

Any loop — an evaluator-optimizer revise loop, an orchestrator's worker rounds, or
any agentic step that iterates — **must** have an explicit stop condition. In the
blueprint this is the step's `termination` field (required for every `agentic` step,
and for any loop). Acceptable terminations: a concrete done-state ("all workers
returned"), a budget ("≤ max_turns"), or a max-iteration count ("2 dry rounds, then
stop"). No open-ended loops — an agent without a stop condition can run away on cost
and never halt. The validator enforces a non-empty `termination` on every agentic
step.
