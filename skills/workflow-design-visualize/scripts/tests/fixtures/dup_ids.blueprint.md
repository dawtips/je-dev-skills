---
name: dup-ids
---
# Dup ids

```yaml
steps:
  - id: step
    kind: deterministic
    rationale: "a"
    pattern: none
  - id: step
    kind: agentic
    rationale: "b"
    pattern: none
    termination: "x"
  - id: "weird [id] & <stuff>"
    kind: deterministic
    rationale: "c"
    pattern: none
subagents: []
```
