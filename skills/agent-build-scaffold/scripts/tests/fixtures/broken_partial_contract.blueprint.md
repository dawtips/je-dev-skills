---
name: broken-partial-contract
---
# Subagent missing boundaries

```yaml
preconditions: ["request exists"]
inputs: []
dependencies: []
outputs: ["classification"]
postconditions: []
steps:
  - id: classify
    kind: agentic
    rationale: "requires judgment"
    pattern: route
    side_effecting: false
    reversible: false
    termination: "category chosen"
subagents:
  - id: classifier
    objective: "classify the request"
    output_format: "JSON {category: string}"
    tools: []
    model: haiku
    effort: low
rubrics: []
dimensions:
  observability: specified
  cost_latency_budgets: specified
  guardrails_permissions: specified
  context_management: specified
  human_in_the_loop: specified
  state_artifact_passing: specified
  failure_handling: specified
  retry_idempotency: specified
  rollback_compensation: specified
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: specified
outcomes: []
budgets: {}
guardrails: []
```
