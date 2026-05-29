---
name: minimal
version: 0.1.0
status: draft
created: 2026-05-29
---
# Minimal blueprint

Prose for humans.

```yaml
preconditions: ["input file exists"]
inputs:
  - {key: path, description: "input path", format: "string"}
dependencies: []
outputs: ["summary"]
postconditions: ["summary written once"]
steps:
  - id: transform
    kind: deterministic
    rationale: "pure data transform; must be exact"
    pattern: none
    side_effecting: false
    reversible: false
    termination: "single pass"
subagents: []
dimensions:
  observability:
  cost_latency_budgets: {n/a: "trivial job"}
  guardrails_permissions: specified
  context_management: {n/a: "no LLM"}
  human_in_the_loop: {n/a: "low-risk"}
  state_artifact_passing: {n/a: "no handoff"}
  failure_handling: specified
  retry_idempotency: {n/a: "read-only"}
  rollback_compensation: {n/a: "read-only"}
  termination_conditions: specified
  tool_selection: {n/a: "no tools"}
  evaluation_success: specified
rubrics: []
outcomes:
  - {given: "a valid input", when: "the job runs", then: "one summary produced"}
budgets: {max_turns: 0, max_tool_calls: 0, latency_note: "<10s", cost_note: "~$0"}
guardrails: ["read-only input"]
```
