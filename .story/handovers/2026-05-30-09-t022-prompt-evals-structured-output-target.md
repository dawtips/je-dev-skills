# Session 2026-05-30 - T-022 prompt-evals structured-output target support

## Summary
Shipped T-022: prompt-evals can now run prompts-under-test with optional
`target.output_schema` constraints on both keyed and no-key paths. The durable spec is
`docs/superpowers/specs/2026-05-30-prompt-evals-structured-output-target-spec.md`.
Plan (deleted before merge):
`docs/superpowers/plans/2026-05-30-t022-prompt-evals-structured-output-target.md`.

Before implementation, reviewed the official Claude structured-output docs, strict tool
use docs, and tool-definition/tool-choice docs. The implementation follows that split:
keyed execution uses `output_config.format`, while no-key execution uses a forced strict
output-sink tool plus deterministic local validation.

## What shipped
- `EvalSpec` / `TargetSpec` now carry optional `target.output_schema`, and
  `load_eval_spec()` parses eval JSON strictly so `NaN` / `Infinity` fail closed.
- New `evals/output_schema.py` provides a bounded JSON Schema subset guard, strict JSON
  parsing, output validation, and a CLI validator for no-key captured tool arguments.
- Keyed prompt execution forwards
  `output_config={"format":{"type":"json_schema","schema": ...}}` and validates returned
  structured output before grading/persistence.
- Artifact execution forwards the schema through `build_run_function()` to two-argument
  executors, preserving legacy one-argument executors only when no schema is configured.
- `prompt-evals-run` now documents the no-key forced structured-output tool path:
  exactly one strict output-sink tool call, fail closed on refusal/max_tokens/zero or
  multiple tool calls/malformed JSON, validate to a candidate file, then publish only
  after validation.

## Review and fixes
- Round 1 review found schema validation was too permissive, keyed outputs were not
  revalidated before persistence, legacy `OUTPUT_SCHEMA` bypassed guards, no-key docs
  could persist before validation, executor signature detection repeated per case, and
  variance schema forwarding/edge cases lacked tests. Fixed in `fae9a05`.
- Round 2 review of the fix commit found a remaining non-finite schema constant gap and
  weak token-only no-key candidate-flow coverage. Fixed in `aea6813`.
- Existing lesson L-005 was reinforced: review the fix commit, not just the original
  implementation.

## Verification
Final worktree verification before lifecycle closeout:
- `python3 tools/skill_lint.py --root .` -> `12 skills | 0 errors | 0 warnings`
- `python3 -m unittest discover -s tools/tests -t tools` -> `Ran 14 tests ... OK`
- `(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)` -> `Ran 187 tests ... OK`
- `python3 -m unittest discover -s skills/workflow-design-validate/scripts/tests -t skills/workflow-design-validate/scripts` -> `Ran 29 tests ... OK`
- `python3 -m unittest discover -s skills/workflow-design-advise/scripts/tests -t skills/workflow-design-advise/scripts` -> `Ran 64 tests ... OK`

The prompt-evals suite still prints the existing expected negative-fixture stderr:
`ERROR: no verdict JSON files ...`.

## Follow-up
No blocking follow-up. Optional future hardening: if Claude structured-output schema
support broadens, update `evals/output_schema.py` deliberately with matching tests rather
than silently forwarding unsupported JSON Schema keywords.
