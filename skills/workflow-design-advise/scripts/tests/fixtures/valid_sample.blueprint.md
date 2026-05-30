---
name: advise-sample
version: 0.1.0
status: validated
created: 2026-05-30
---
# Advise sample

A minimal blueprint exercising every advisor path: an orchestrate step, a
parallelize step, a route step, a deterministic step (skipped), and one
over-provisioned subagent.

```yaml
steps:
  - id: plan
    kind: agentic
    pattern: orchestrate
    rationale: "plan the brief and decide how many workers"
  - id: research-each
    kind: agentic
    pattern: parallelize
    rationale: "fan out one worker per item"
  - id: classify
    kind: agentic
    pattern: route
    rationale: "route each item into a fixed bucket"
  - id: verify
    kind: deterministic
    pattern: none
    rationale: "exact set-membership check; no model"
subagents:
  - id: item-researcher
    objective: "research one assigned item and return structured findings"
    output_format: "JSON {item, findings}"
    tools: [web_search, web_fetch]
    boundaries: "research only the single assigned item"
    model: opus
    effort: low
```
