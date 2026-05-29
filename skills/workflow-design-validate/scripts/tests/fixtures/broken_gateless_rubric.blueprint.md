---
name: full
version: 0.1.0
status: draft
created: 2026-05-29
---
# Full blueprint

```yaml
preconditions: ["a question and competitor list"]
inputs:
  - {key: question, description: "what to answer", format: "string"}
dependencies: ["web search"]
outputs: ["cited brief"]
postconditions: ["every claim cited"]
steps:
  - id: research
    kind: agentic
    rationale: "open-ended; needs judgment"
    pattern: parallelize
    side_effecting: false
    reversible: false
    termination: "all workers return or 2 dry rounds"
subagents:
  - id: researcher
    objective: "research one competitor"
    output_format: "JSON {competitor, findings[], sources[]}"
    tools: [web_search, web_fetch]
    boundaries: "only the assigned competitor; do not synthesize"
    model: sonnet
    effort: medium
dimensions:
  observability: specified
  cost_latency_budgets: specified
  guardrails_permissions: specified
  context_management: specified
  human_in_the_loop: specified
  state_artifact_passing: specified
  failure_handling: specified
  retry_idempotency: specified
  rollback_compensation: {n/a: "read-only research"}
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: specified
rubrics:
  - name: completeness
    scale: 1-5
    levels: {1: "missing competitors", 3: "shallow", 5: "deep, all covered"}
    reference_based: false
    judge: llm
outcomes:
  - {given: "a question + 4 competitors", when: "the workflow runs", then: "a cited brief covering all 4"}
budgets: {max_turns: 30, max_tool_calls: 60, latency_note: "<5m", cost_note: "~15x a chat"}
guardrails: ["subagents read-only"]
```
