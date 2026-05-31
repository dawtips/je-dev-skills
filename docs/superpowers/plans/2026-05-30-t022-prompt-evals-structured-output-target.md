# Prompt-Evals Structured Output Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional `target.output_schema` support so prompt-evals can constrain prompts-under-test to structured outputs on keyed and no-key execution paths.

**Architecture:** Store the schema on `TargetSpec` and validate it with a provider-neutral, bounded root-object schema guard. Keyed Anthropic request shaping stays in `run_eval.py`; the artifact runner passes the schema through an explicit executor contract. The run skill documents the no-key forced-tool equivalent and a deterministic validation command because Task subagents do not expose `output_config.format`.

**Tech Stack:** Python `dataclasses`, `unittest`, existing prompt-evals framework modules, Markdown skill docs.

**Claude docs check:** Reviewed Anthropic's structured-output docs before implementation.
Use `output_config={"format":{"type":"json_schema","schema": schema}}` for JSON outputs.
For the no-key tool equivalent, document strict tool use with `strict: true` and forced
tool selection semantics equivalent to `tool_choice: {"type": "tool", "name": "<output_sink>"}`.
Keep local schema guards conservative because the docs describe unsupported schema features,
complexity limits, schema grammar compilation/caching, and invalid-output cases including
refusals and `max_tokens`.

---

### Task 1: Artifact Contract

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/artifacts.py`
- Create: `skills/prompt-evals-setup/framework/evals/output_schema.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_artifacts.py`
- Create: `skills/prompt-evals-setup/framework/evals/tests/test_output_schema.py`

- [ ] **Step 1: Write failing loader tests**

Add tests that write `target.output_schema` into `eval.json`, load it with
`load_eval_spec()`, and assert `spec.target.output_schema` matches exactly. Add rejection
tests whose `ValueError` message names `target.output_schema` and says it must be a JSON
object for non-object and non-root-object schemas.

- [ ] **Step 2: Run red tests**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_artifacts)
```

Expected: failure because `TargetSpec` has no `output_schema`.

- [ ] **Step 3: Implement artifact plumbing**

Create `evals/output_schema.py` with:

```python
MAX_OUTPUT_SCHEMA_BYTES = 16_384
MAX_OUTPUT_SCHEMA_DEPTH = 12

def validate_output_schema(schema: object, *, field: str = "target.output_schema") -> dict:
    if not isinstance(schema, dict):
        raise ValueError(f"{field} must be a JSON object")
    if schema.get("type") != "object":
        raise ValueError(f"{field} must be a JSON object schema with root type 'object'")
    return schema

def validate_output_against_schema(value: object, schema: dict) -> object:
    if not isinstance(value, dict):
        raise ValueError("structured output must be a JSON object")
    return value
```

The schema validator rejects non-object roots, root `type` values other than `"object"`,
missing node `type`, unclosed object schemas, arrays without `items`, non-object
`properties`, non-string `required` entries, unsupported validation keywords,
reference/recursive keywords, and schemas over byte/depth/optional-parameter limits. It
also rejects `anyOf` and type arrays for v1 so the local subset does not trip Claude's
documented union-complexity limit. Add `output_schema: dict | None = None` to `TargetSpec`,
call `validate_output_schema()` in `load_eval_spec()`, and pass the validated schema into
`TargetSpec`.

- [ ] **Step 4: Run green tests**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_artifacts)
```

Expected: pass.

### Task 2: Keyed Executor Forwarding

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/artifact_runner.py`
- Modify: `skills/prompt-evals-setup/framework/evals/run_eval.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_artifact_runner.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_run_eval_cli.py`

- [ ] **Step 1: Write failing executor tests**

Add tests proving `build_run_function()` passes `spec.target.output_schema` through a
single explicit executor contract:

```python
Executor = Callable[[str, dict | None], str]
```

Also add a backward-compat test proving a legacy one-arg executor still works when no
schema is present, and a clear `ValueError` is raised when a schema is present with a
legacy one-arg executor.

- [ ] **Step 2: Write failing keyed API tests**

Add tests for a small helper in `run_eval.py` that calls `messages.create`. Assert that
`OUTPUT_SCHEMA` reaches legacy `run_prompt()` and that artifact executor helpers forward
`spec.target.output_schema` as
`output_config={"format":{"type":"json_schema","schema": <schema>}}`.
Add backward-compat tests proving `output_config` is omitted entirely when `OUTPUT_SCHEMA`
or `target.output_schema` is `None`.

- [ ] **Step 3: Run red tests**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_artifact_runner evals.tests.test_run_eval_cli)
```

Expected: failures because executors do not accept schemas and `run_eval.py` sends no
`output_config`.

- [ ] **Step 4: Implement executor forwarding**

In `artifact_runner.py`, call executors as `(prompt, output_schema)` and keep a small
compatibility branch for legacy one-arg executors only when `output_schema is None`. If a
schema is present and the executor rejects the two-arg call, raise a clear `ValueError`
that names `target.output_schema` and the two-argument executor contract. In `run_eval.py`,
add `OUTPUT_SCHEMA = None`, a reusable Anthropic message helper that builds Anthropic
`output_config`, and use it in `run_prompt`, `evaluate-artifact`, and
`evaluate-artifact-variance`.

- [ ] **Step 5: Run green tests**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_artifact_runner evals.tests.test_run_eval_cli)
```

Expected: pass.

### Task 3: No-Key Skill Documentation

**Files:**
- Modify: `skills/prompt-evals-run/SKILL.md`
- Modify: `tools/tests/test_prompt_evals_setup_skill.py`

- [ ] **Step 1: Add no-key structured-output instructions**

In Path A's execute-subagent step, add the conditional behavior for
`target.output_schema`: define a forced tool using that schema, require exactly one tool
call, and persist the tool arguments JSON as the raw output. Tie the prose to Claude's
documented API semantics: the output-sink tool is strict (`strict: true`) and selected with
forced-tool behavior equivalent to `tool_choice: {"type": "tool", "name": "<output_sink>"}`. State
the security boundary: the execute-subagent should have only the output-sink tool available,
with no workspace/network/subagent tools, and the run must fail closed if real forced-tool
behavior is unavailable in the current client.

Before persisting, run deterministic validation with the framework helper. The documented
flow must fail closed for zero tool calls, multiple tool calls, prose/markdown instead of
tool arguments, malformed JSON, validation failure, refusal, or `max_tokens` truncation.

- [ ] **Step 2: Add keyed path note**

In Path B, state that `evaluate-artifact` passes `target.output_schema` to Anthropic
structured outputs when present.

- [ ] **Step 3: Verify docs tokens**

Add tests that read `skills/prompt-evals-run/SKILL.md` and assert it contains these exact
behavioral markers:

```bash
target.output_schema
forced structured-output tool
strict: true
tool_choice
output-sink tool
fail closed
zero tool calls
multiple tool calls
malformed JSON
max_tokens
output_config
```

Run:

```bash
python3 -m unittest tools.tests.test_prompt_evals_setup_skill
```

Expected: pass.

### Task 4: Full Verification and Lifecycle

**Files:**
- Modify: `.story/tickets/T-022.json`
- Create: `.story/handovers/<date>-t022-structured-output.md`
- Delete before merge: `docs/superpowers/plans/2026-05-30-t022-prompt-evals-structured-output-target.md`

- [ ] **Step 1: Run prompt-evals suite**

Run:

```bash
(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)
```

Expected: all tests pass.

- [ ] **Step 2: Run repo-required offline verification**

Run the commands from `AGENTS.md`:

```bash
python3 tools/skill_lint.py --root .
python3 -m unittest discover -s tools/tests -t tools
(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)
python3 -m unittest discover -s skills/workflow-design-validate/scripts/tests -t skills/workflow-design-validate/scripts
python3 -m unittest discover -s skills/workflow-design-advise/scripts/tests -t skills/workflow-design-advise/scripts
```

Expected: all pass.

- [ ] **Step 3: Run two independent implementation reviews**

Run two independent review rounds on the final implementation diff. The pre-implementation
plan review does not count toward these two rounds. Address blocking findings, then review
the fix commit if any review changes code.

- [ ] **Step 4: Close Story loop**

Mark T-022 complete, create a handover naming this deleted plan file, delete the plan with
`git rm`, commit, merge locally to `main`, rerun verification on merged `main`, remove the
worktree, and delete branch `t022-structured-output`.
