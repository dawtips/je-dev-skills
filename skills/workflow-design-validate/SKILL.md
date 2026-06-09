---
name: workflow-design-validate
description: This skill should be used when the user asks to "validate a workflow blueprint", "check a blueprint", "is my workflow design complete", "lint a workflow blueprint", or right after workflow-design-interview produces one. It runs a deterministic completeness check over ./workflows/<name>.blueprint.md and reports the gaps to fix.
argument-hint: "[path to the blueprint; defaults to ./workflows/*.blueprint.md]"
allowed-tools: Bash, Read, Edit, Glob
version: 0.1.0
---

# Workflow Design: Validate

Run a deterministic completeness check over a workflow blueprint and drive the
fixes until it passes. The check is structural: it parses the single fenced
`yaml` block from `<name>.blueprint.md` and verifies it against the schema in
`docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §4.1 — dimension coverage, per-step contracts,
the subagent four-part contract, rubric gates, and Given-When-Then outcomes.

## Precondition

A blueprint file must exist. Blueprints are written by
`workflow-design-interview` to `./workflows/<name>.blueprint.md`.

- If the user passed a path, use it.
- Otherwise, find candidates with Glob: `./workflows/*.blueprint.md`.
- If no blueprint exists anywhere, stop and point the user at
  **`workflow-design-interview`** to produce one first — there is nothing to
  validate yet.

## Procedure

1. **Install deps once.** The validator needs PyYAML. Install it (idempotent):

   ```bash
   pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-validate/scripts/requirements.txt
   ```

2. **Run the validator** against the blueprint path:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-validate/scripts/validate_blueprint.py <path>
   ```

   Exit codes: `0` = PASS, `1` = gaps found, `2` = file unreadable or the
   blueprint has anything other than exactly one fenced `yaml` block.

3. **Read the report.** The output is a coverage score
   (`Coverage: N/12 dimensions accounted for`) followed by a list of gaps. Each
   gap is `path: message`, where `path` points into the YAML
   (e.g. `steps[0].rationale`, `subagents[0].boundaries`,
   `dimensions.observability`, `rubrics[0].gate`, `outcomes[0].then`).

4. **Fix each gap** by editing the `yaml` block inside the blueprint file with
   the Edit tool. Do not touch the prose or frontmatter unless the gap is there.
   Common fixes:
   - A dimension gap: set it to `specified` (and add the detail in prose), or
     `{n/a: <non-empty rationale>}` when the dimension genuinely does not apply.
   - A step gap: add the missing `rationale`, fix `kind`
     (`deterministic`|`agentic`), add `termination` for agentic steps, add
     `retry.idempotency_key` for `side_effecting: true` steps, or add `rollback`
     for `reversible: true` steps.
   - A subagent gap: complete the contract
     (`objective`, `output_format`, `tools` as a non-empty allowlist,
     `boundaries`, `model`, `effort`); remove subagents if no agentic step
     justifies them.
   - A rubric gap: add `scale`, define `levels`, set a `gate` threshold.
   - An outcome gap: make each outcome a full Given-When-Then triple.

5. **Re-run** step 2. Repeat fix → re-run until the validator prints `PASS` and
   exits `0`.

## Definition of done

The validator exits `0` and prints `Coverage: 12/12 dimensions accounted for`
followed by `PASS`. All 12 dimensions are accounted for (each `specified` or a
justified `{n/a: <rationale>}`) and no structural gaps remain.

## Notes

- **Structural only.** This check runs offline with no API key. It confirms the
  blueprint is *complete and well-formed* — it does not judge whether the design
  is *good*. A clean PASS means every required field is present and accounted
  for, not that the chosen patterns, models, or rubrics are the right ones.
- **Semantic review is planned for v0.2.** An LLM-driven quality review layer
  (does the rationale hold up? are the guardrails sufficient? is the
  decomposition sound?) is out of scope for v0.1 — see
  `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §9.
