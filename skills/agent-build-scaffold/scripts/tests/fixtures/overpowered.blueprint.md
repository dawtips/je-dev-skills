---
name: overpowered
---
# A subagent doing a script's job

```yaml
preconditions: ["input text exists"]
inputs:
  - {key: input_path, description: "input file", format: "path"}
dependencies: []
outputs: ["normalized JSON"]
postconditions: []
steps:
  - id: extract-fields
    kind: agentic
    rationale: "extract and format fields from a fixed template"
    pattern: none
    side_effecting: false
    reversible: false
    termination: "fields extracted"
subagents:
  - id: field-extractor
    objective: "extract fields from a fixed template"
    output_format: "JSON"
    tools: [Read]
    boundaries: "read only"
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
outcomes:
  - {given: "a fixed template", when: "the workflow runs", then: "JSON is emitted"}
budgets: {}
guardrails: []
```
