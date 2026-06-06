---
name: multi
version: 0.1.0
status: validated
created: 2026-05-31
---
# Multi

```yaml
steps:
  - id: validate_inputs
    kind: deterministic
    rationale: "schema checks"
    pattern: none
    side_effecting: false
    reversible: false
  - id: plan
    kind: agentic
    rationale: "open-ended"
    pattern: none
    termination: "first valid response"
  - id: fan_out
    kind: agentic
    rationale: "independent items"
    pattern: parallelize
    termination: "all done or timeout"
  - id: emit
    kind: deterministic
    rationale: "write file"
    pattern: none
    side_effecting: true
    reversible: true
    retry: {policy: "overwrite", idempotency_key: "run_id"}
    rollback: "delete file"
    approval_gate: explicit
subagents:
  - id: worker
    objective: "do one item"
    output_format: "JSON"
    tools: [web_search, web_fetch]
    boundaries: "one item only"
    model: haiku
    effort: low
```
