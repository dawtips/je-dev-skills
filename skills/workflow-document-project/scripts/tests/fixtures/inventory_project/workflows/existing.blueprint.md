---
name: existing
version: 0.1.0
status: draft
created: 2026-05-30
---
# Existing

```yaml
preconditions: []
inputs: []
dependencies: []
outputs: []
postconditions: []
steps:
  - id: validate
    kind: deterministic
    rationale: "The project contains validator tests."
    pattern: none
    side_effecting: false
    reversible: false
    inputs: []
    outputs: []
    failure_modes: []
    approval_gate: none
subagents: []
dimensions: {}
rubrics: []
outcomes: []
budgets: {max_turns: 1, max_tool_calls: 0, latency_note: "offline", cost_note: "none"}
guardrails: []
```
