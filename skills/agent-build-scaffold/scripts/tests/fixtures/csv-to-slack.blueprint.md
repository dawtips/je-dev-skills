---
name: csv-to-slack
version: 0.1.0
status: validated
created: 2026-05-29
---
# Scheduled CSV-to-Slack summary

```yaml
preconditions: ["a CSV file exists"]
inputs:
  - {key: csv_path, description: "path to CSV", format: "path"}
dependencies: ["local filesystem", "Slack webhook"]
outputs: ["one Slack summary"]
postconditions: ["a Slack message is posted once"]
steps:
  - id: parse-csv
    kind: deterministic
    rationale: "parse rows from a known CSV format"
    pattern: none
    side_effecting: false
    reversible: false
  - id: post-summary
    kind: deterministic
    rationale: "post a prepared summary to Slack"
    pattern: none
    side_effecting: true
    reversible: false
    retry: {policy: "fixed", idempotency_key: "csv_path"}
subagents: []
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
  rollback_compensation: {n/a: "posting has no rollback path"}
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: specified
outcomes:
  - {given: "a CSV", when: "the job runs", then: "one Slack summary"}
budgets: {max_turns: 4, max_tool_calls: 5}
guardrails: ["do not post duplicate messages"]
```
