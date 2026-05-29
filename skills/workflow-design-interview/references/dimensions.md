# Dimensions — the normative coverage checklist

The 12 cross-cutting dimensions every blueprint must account for. The
`dimensions` map in the structured core (see `blueprint-schema.md`) has exactly one
entry per dimension below, in this order. Each entry is either:

- `specified` — the design has a concrete, written answer for this dimension
  (captured in the relevant `steps` / `subagents` / `budgets` / `guardrails` /
  `rubrics` / `outcomes` fields, with the prose Rationale explaining the why); or
- `{n/a: "<rationale>"}` — the dimension genuinely does not apply, **with a
  non-empty rationale** saying why. A bare `n/a` with no reason is a gap.

Use this file during Stage 5 (the dimension sweep) of the interview. Walk every
dimension; for each, decide `specified` or `n/a`-with-rationale. The grounding for
this checklist is spec §10 (failure modes, retry/idempotency, HITL, the artifact
pattern, observability, guardrails, budgets, termination, rollback, tool selection,
and evaluation rigor).

> A "cop-out `n/a`" — marking a dimension `n/a` to dodge the work rather than
> because it truly does not apply — is exactly what the v0.2 LLM review layer is
> meant to catch (spec §9). The deterministic gate only checks that a rationale is
> present; you are on your honor that it is a real one.

---

## 1. observability

**Definition.** How a run is made visible: logging, tracing, metrics, and what gets
recorded so a human can see what happened and debug a bad run after the fact.

**`specified` requires.** A statement of what is logged/traced (per step or per
run), where it goes, and what is observable enough to diagnose a failure — e.g.
structured logs per step, a trace id threaded through, key metrics (counts,
latencies, scores) emitted.

**Legitimately `n/a` when.** Almost never for anything that runs unattended;
arguably `n/a` only for a throwaway one-shot with no operational lifetime. Even
trivial jobs usually log "ran / did not run," so prefer `specified`.

## 2. cost_latency_budgets

**Definition.** The cost and time envelope the workflow must run within — token
spend, wall-clock latency, tool-call counts.

**`specified` requires.** Concrete budget figures in `budgets`
(`max_turns`, `max_tool_calls`, `latency_note`, `cost_note`) and, for agentic steps,
an awareness of model/effort cost. Multi-agent designs must justify their token
multiplier here.

**Legitimately `n/a` when.** The job is trivially cheap and fast with no model
invocation (e.g. a sub-second pure-code script), so no budget needs setting — state
that explicitly as the rationale.

## 3. guardrails_permissions

**Definition.** Least-privilege access scoping, injection defense, and the limits on
what each step/agent is allowed to touch.

**`specified` requires.** Entries in `guardrails` covering: least-privilege
credentials/tool allowlists, treatment of untrusted input (prompt-injection
defense), and access scoping. Side-effecting steps must name the scope of their
permissions.

**Legitimately `n/a` when.** Effectively never for anything touching external
systems or untrusted input. Only a fully sandboxed, read-only, no-untrusted-input
computation could justify `n/a` — and even then, prefer `specified: read-only`.

## 4. context_management

**Definition.** How conversation/context is kept within window limits and how state
is summarized or compacted across steps and agents.

**`specified` requires.** A statement of how context is bounded — what each agentic
step is given, what is summarized or dropped between steps, how subagent outputs are
compacted before fan-in.

**Legitimately `n/a` when.** There is no LLM and no conversation context to manage —
a pure-code workflow. State "no LLM / no context" as the rationale.

## 5. human_in_the_loop

**Definition.** Where a human approves, is notified, or intervenes — the
risk-tiered `approval_gate` on steps (`none` / `notify` / `explicit`).

**`specified` requires.** For each consequential step, an `approval_gate` value and,
where `explicit`, what triggers the gate (e.g. low confidence, irreversible action).
At minimum, a statement of which actions need human sign-off and which run
autonomously.

**Legitimately `n/a` when.** The workflow is fully automated and low-risk, with no
irreversible or high-impact action — a wrong result is self-correcting or harmless.
State the risk assessment as the rationale.

## 6. state_artifact_passing

**Definition.** How data moves between steps and agents — in-context handoff vs.
written artifacts (files, blobs) that downstream steps read. The "artifact pattern."

**`specified` requires.** A statement of how each step's `outputs` reach the next
step's `inputs`: passed in context, or written as an artifact and read back. For
orchestrator-workers, how worker results are collected and handed to synthesis.

**Legitimately `n/a` when.** There is genuinely no handoff — a single self-contained
step with no inter-step data flow. State "no handoff" as the rationale.

## 7. failure_handling

**Definition.** What can go wrong at each step and how the workflow responds —
enumerated `failure_modes` plus the response (fail, skip, escalate, degrade).

**`specified` requires.** Non-empty `failure_modes` on the steps that can fail, and a
stated response for each class (hard fail, log-and-skip, escalate to human, graceful
degradation). The `postconditions` should hold even on partial failure.

**Legitimately `n/a` when.** Essentially never — every step that touches the world
can fail. Only a step that genuinely cannot fail (rare) is `n/a`.

## 8. retry_idempotency

**Definition.** For side-effecting steps, the retry policy and the idempotency key
that makes a retry safe (no duplicate effect).

**`specified` requires.** Every step with `side_effecting: true` has a `retry` with a
`policy` and an `idempotency_key`. The gate enforces the idempotency key on
side-effecting steps; this dimension records the overall retry strategy.

**Legitimately `n/a` when.** No step has external side effects — the whole workflow
is read-only (e.g. research/synthesis that only produces an artifact). State
"read-only, no side effect to retry" as the rationale.

## 9. rollback_compensation

**Definition.** For reversible/undoable actions, the compensating action that undoes
a partial or wrong effect (saga-style compensation).

**`specified` requires.** Every step with `reversible: true` has a `rollback`
describing the compensating action. The gate enforces `rollback` on reversible
steps; this dimension records the overall compensation strategy.

**Legitimately `n/a` when.** No step mutates external state, or the side effects are
not meaningfully reversible and are instead deduped (e.g. an idempotent post). State
why there is nothing to roll back.

## 10. termination_conditions

**Definition.** The explicit done-condition or budget for every loop and every
agentic step — what stops it, so nothing runs unbounded.

**`specified` requires.** Every `agentic` step (and every loop) has a non-empty
`termination` (the gate enforces this on agentic steps): a done condition, a budget,
or a max-iterations bound.

**Legitimately `n/a` when.** Only a purely linear, single-pass deterministic
workflow with no loops and no agentic steps — every step terminates trivially after
one pass. State that as the rationale.

## 11. tool_selection

**Definition.** Which tools/sources each agentic step or subagent may use, chosen as
a least-privilege allowlist — and why those and not others.

**`specified` requires.** For each agentic step/subagent, a `tools` allowlist
(non-empty for subagents, per the contract) and a rationale for the selection. The
allowlist should be the minimum needed for the objective.

**Legitimately `n/a` when.** No agentic tool selection happens — a pure-code job
whose integrations are fixed at design time, not chosen at runtime by a model. State
"no runtime tool selection" as the rationale.

## 12. evaluation_success

**Definition.** How success is measured: the `rubrics` (categorical scales with
per-level definitions and gates) and the `outcomes` (Given-When-Then end-states).

**`specified` requires.** Defined `outcomes` (Given-When-Then) and, for any
generative/agentic output, `rubrics` with a categorical `scale`, per-level `levels`,
a `gate`, `reference_based?`, and `judge`. This is the handoff surface into the
`prompt-evals-*` lifecycle.

**Legitimately `n/a` when.** Never fully — every workflow needs observable
`outcomes`. `rubrics` may be empty when there is nothing generative to grade (a
deterministic job whose correctness is the code's correctness), but `outcomes` should
still be specified. If marking this `n/a`, justify that success is fully captured by
postconditions/outcomes alone.

---

## The completeness rule

> **A blueprint is complete only when every one of the 12 dimensions above is either
> `specified` or `{n/a: "<non-empty rationale>"}`.**

This is the single rule the `workflow-design-validate` gate enforces for coverage:
it emits `N/12 dimensions accounted for` and fails on any dimension that is missing,
blank, or `n/a` without a rationale. Completeness is **not** "everything filled in" —
it is "every dimension consciously addressed," and a justified `n/a` counts as
addressed. The point is that no dimension is silently forgotten.
