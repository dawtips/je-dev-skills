---
name: refund-triage
version: 0.1.0
status: validated
created: 2026-05-29
---
# Refund triage workflow

```yaml
preconditions: ["an inbound refund request with order id"]
inputs:
  - {key: order_id, description: "the order to refund", format: "string"}
  - {key: reason, description: "customer-stated reason", format: "string"}
dependencies: ["orders API"]
outputs: ["a refund decision + audit record"]
postconditions: ["every approved refund has an idempotency key"]
steps:
  - id: classify-reason
    kind: agentic
    rationale: "free-text reason needs open-ended judgment to categorize"
    pattern: route
    side_effecting: false
    reversible: false
    termination: "a single category is chosen"
  - id: fetch-order
    kind: deterministic
    rationale: "a plain API read; no judgment"
    pattern: none
    side_effecting: false
    reversible: false
  - id: issue-refund
    kind: deterministic
    rationale: "a deterministic API write guarded by an idempotency key"
    pattern: none
    side_effecting: true
    reversible: true
    retry: {policy: "exponential", idempotency_key: "order_id"}
    rollback: "void the refund via the orders API"
subagents:
  - id: reason-classifier
    objective: "classify the customer's refund reason into one category"
    output_format: "JSON {category: string, confidence: number}"
    tools: [Read]
    boundaries: "classify only; never issue a refund or fetch external data"
    model: haiku
    effort: low
rubrics:
  - name: classification-accuracy
    scale: 1-5
    levels: {1: "wrong category", 3: "plausible", 5: "exactly right"}
    gate: 4
    reference_based: true
    judge: llm
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
  - {given: "a refund request", when: "the workflow runs", then: "a categorized, audited decision"}
budgets: {max_turns: 10, max_tool_calls: 20, latency_note: "<1m", cost_note: "~3x a chat"}
guardrails: ["classifier is read-only", "refund write is idempotent"]
```
