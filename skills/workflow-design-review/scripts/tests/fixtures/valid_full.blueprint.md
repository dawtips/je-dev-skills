---
name: review-fixture
version: 0.1.0
status: draft
created: 2026-05-30
---
# Review Fixture

This blueprint intentionally includes prose plus YAML so the reviewer can assess
recorded rationales, not just structure.

```yaml
preconditions: ["source issue is available"]
inputs:
  - {key: issue_id, description: "issue identifier", format: "string"}
dependencies: []
outputs: ["review_report"]
postconditions: ["review_report summarizes risks"]
steps:
  - id: collect_context
    kind: deterministic
    rationale: "reads fixed files and copies known facts without judgment"
    pattern: sequential
    side_effecting: false
    reversible: false
    termination: "all configured files read once"
  - id: assess_design
    kind: agentic
    rationale: "requires qualitative judgment over tradeoffs and risks"
    pattern: evaluator
    side_effecting: false
    reversible: false
    termination: "one scored review is produced"
subagents:
  - id: design_reviewer
    objective: "Assess design quality against the rubric"
    output_format: "Markdown findings with dimension scores"
    tools: ["Read"]
    boundaries: "May read only blueprint and rubric files; must not edit files"
    model: "strong reasoning model"
    effort: "high"
dimensions:
  observability: specified
  cost_latency_budgets: specified
  guardrails_permissions: specified
  context_management: specified
  human_in_the_loop: specified
  state_artifact_passing: specified
  failure_handling: specified
  retry_idempotency: {n/a: "read-only review"}
  rollback_compensation: {n/a: "no writes during review"}
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: specified
rubrics:
  - name: design_quality
    scale: "1-5"
    levels: {1: "unsafe", 3: "usable with concerns", 5: "clear and minimal"}
    gate: 3
outcomes:
  - given: "a structurally valid blueprint"
    when: "semantic review runs"
    then: "the report lists all dimension scores and concrete fixes"
budgets: {max_turns: 1, max_tool_calls: 0, latency_note: "<2m", cost_note: "one judge call"}
guardrails: ["read-only review"]
```
