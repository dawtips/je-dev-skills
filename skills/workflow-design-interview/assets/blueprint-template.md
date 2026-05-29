<!--
  Blueprint skeleton — fill this in during the workflow-design-interview.

  This template is INTENTIONALLY INCOMPLETE: as-is it FAILS workflow-design-validate
  (placeholders are not real values; every dimension is still unaccounted for). That
  failure is expected. The interview replaces every <placeholder>, decides each
  dimension as `specified` or `{n/a: "<rationale>"}`, and re-runs the validator until
  it reports "12/12 dimensions accounted for" and exits 0.

  Keep EXACTLY ONE fenced ```yaml block in the finished file — it is the single
  source of truth the validator parses. Put any illustrative YAML in the prose using
  a different fence (e.g. ```text).
-->
---
name: <slug>          # short name; matches the file name <name>.blueprint.md
version: 0.1.0
status: draft         # draft | validated
created: <YYYY-MM-DD>
---
# <Workflow title>

## Purpose

<What this workflow is for, in plain language. The root need behind it (5 Whys).>

## Stakeholders & context

<Who needs it, who is affected, where and how often it runs, what it touches.>

## Rationale

<Explain-the-why: why this shape, why each escalation to an agentic step or a
subagent was justified (cite the simplicity-first reasoning), and what was
deliberately left out of scope (MoSCoW "Won't").>

```yaml
preconditions: []               # what must hold before the workflow runs
inputs:                         # the closed set the workflow consumes
  - {key: <slug>, description: "<what it is>", format: "<units/format>"}
dependencies: []                # external systems, data, services relied upon
outputs: []
postconditions: []              # what is guaranteed after successful completion
steps:
  - id: <slug>
    kind: deterministic | agentic
    rationale: "<why this classification — REQUIRED for every step>"
    pattern: chain|route|parallelize|orchestrate|evaluate|none
    side_effecting: true|false  # true → this step needs retry.idempotency_key below
    reversible: true|false      # true → this step needs rollback below
    inputs: []
    outputs: []
    failure_modes: []
    retry: {policy: "<...>", idempotency_key: "<...>"}   # REQUIRED if side_effecting: true
    rollback: "<compensating action>"                    # REQUIRED if reversible: true
    approval_gate: none | notify | explicit
    termination: "<done condition / budget>"             # REQUIRED if kind is agentic
subagents: []                   # only where delegation is genuinely warranted; if present,
                                # at least one step must be kind: agentic. Each entry needs
                                # the full four-part contract:
  # - id: <slug>
  #   objective: "<the one task this worker owns>"
  #   output_format: "<exact return shape>"
  #   tools: [<non-empty least-privilege allowlist>]
  #   boundaries: "<what it must NOT do>"
  #   model: sonnet|opus|haiku|inherit
  #   effort: low..max
dimensions:                     # EVERY dimension: replace each TODO with `specified`
                                # or {n/a: "<rationale>"} — a bare TODO is a gap.
  observability: TODO
  cost_latency_budgets: TODO
  guardrails_permissions: TODO
  context_management: TODO
  human_in_the_loop: TODO
  state_artifact_passing: TODO
  failure_handling: TODO
  retry_idempotency: TODO
  rollback_compensation: TODO
  termination_conditions: TODO
  tool_selection: TODO
  evaluation_success: TODO
rubrics: []                     # empty is fine if nothing generative is graded
  # - name: <slug>
  #   scale: 1-5                # categorical integer, NOT floats
  #   levels: {1: "<...>", 3: "<...>", 5: "<...>"}
  #   gate: <int>
  #   reference_based: true|false
  #   judge: human|llm
outcomes:                       # observable Given-When-Then end-states
  - {given: "<...>", when: "<...>", then: "<...>"}
budgets: {max_turns: <int>, max_tool_calls: <int>, latency_note: "<...>", cost_note: "<...>"}
guardrails: []                  # least-privilege, injection defense, access scoping
```
