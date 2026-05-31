# Prompt-Evals Structured Output Target Support

> **Ticket covered:** T-022 — prompt-evals structured-output target support.
>
> **Relationship to prior prompt-evals specs:** this extends the plugin-resident artifact
> contract from `2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`. It does
> not add a second run path; it keeps the artifact runner as a thin front-end over the
> existing `live_run.run_evaluation` seam.
>
> **Claude docs reviewed before implementation:** Anthropic's structured-output docs
> describe two related features: JSON outputs via `output_config.format` and strict tool
> use via `strict: true`. Their tool docs define forced tool use with
> `tool_choice: {"type": "tool", "name": "<output_sink>"}` and note that `tool_choice: "any"` or a
> named forced tool can be combined with strict tool use to guarantee a tool call whose
> input conforms to the schema.

## 1. Purpose

Prompt evals can already force structured JSON for generator and judge calls through the
framework's `AnthropicClient.complete_json(schema=<json_schema>)`. T-022 adds the same native
structured-output support to the **prompt under test** when that prompt is executed by the
framework.

The contract belongs in the project-owned artifact because it is part of what the target
prompt promises to emit:

```json
{
  "target": {
    "mode": "prompt_file",
    "prompt_file": "prompts/planner.md",
    "output_schema": {
      "type": "object",
      "properties": {
        "items": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["items"],
      "additionalProperties": false
    }
  }
}
```

`target.output_schema` is optional. Existing artifacts that omit it keep current behavior.

## 2. Artifact Contract

`TargetSpec` gains `output_schema: dict | None`. `load_eval_spec()` reads
`target.output_schema` and validates it with a deterministic, dependency-free guard before
the schema reaches any model/tool surface:

- the schema must be a JSON object whose root `type` is `"object"`,
- `properties`, when present, must be an object,
- `required`, when present, must be an array of strings,
- `$ref`, `$defs`, `definitions`, `$recursiveRef`, and `$dynamicRef` are rejected because
  the framework does not resolve references and should not accept recursive contracts,
- `anyOf` and type arrays are rejected for v1 because the Claude docs count union-typed
  parameters against a small complexity limit and because the local validator is intentionally
  a supported-subset checker,
- optional properties are bounded; the Claude docs count optional parameters across strict
  schemas and JSON output schemas, so the local guard rejects schemas above that budget,
- serialized schema size and nesting depth are bounded to avoid accidental request/token
  denial-of-service from project-controlled artifacts.

This is compatibility validation, not a full JSON Schema implementation. The framework
stores and forwards the schema unchanged after it passes those guards.

`scaffold_eval_artifacts()` may accept an optional `output_schema` keyword for tests and
future callers. The default scaffold omits the key so generated artifacts remain minimal
and backward compatible.

## 3. Keyed Execution Path

When `target.output_schema` is present and a prompt-file target is executed by the keyed
Anthropic path, the executor model call must include:

```python
output_config={
    "format": {
        "type": "json_schema",
        "schema": target.output_schema,
    }
}
```

The legacy `run_prompt()` path gets a module-level `OUTPUT_SCHEMA = None` hook for
vendored/evolved projects that still use that mode. Artifact evaluation passes
`spec.target.output_schema` through `artifact_runner.build_run_function()` to the executor
closure used by `run_eval evaluate-artifact` and `evaluate-artifact-variance`.

When no schema is configured, `output_config` is omitted entirely. Command-adapter targets
own their execution process, so the framework stores the schema but does not attempt to
constrain the adapter's subprocess. Projects that need adapter output validation should
keep deterministic assertions in `eval.json` and/or have the adapter enforce its own
contract.

## 4. No-Key Execution Path

Claude Code Task subagents do not expose Anthropic's `output_config.format` knob. For the
canonical no-key path, `prompt-evals-run` must translate `target.output_schema` into a
forced structured-output tool instruction for the execute-subagent:

- define one tool whose input schema is exactly `target.output_schema`,
- set that tool to strict mode (`strict: true` in Claude API terms),
- force that specific tool (`tool_choice: {"type": "tool", "name": "<output-sink>"}` in
  Claude API terms) when the current client exposes such a boundary,
- require the execute-subagent to call that tool exactly once,
- treat the tool arguments JSON as the raw output saved to the output file,
- do not accept prose, markdown fences, or extra text outside the tool call,
- fail closed if the current Task implementation cannot provide a real forced tool
  boundary for the execute-subagent.

The no-key path also performs a deterministic local validation pass before persisting the
captured tool arguments. That validator checks the same bounded root-object schema contract
and validates the captured JSON against the supported subset: object type, required keys,
closed objects via `additionalProperties: false`, primitive property types, arrays, nested
objects, and enums. Zero tool calls, multiple tool calls, malformed JSON, prose in place of
tool arguments, or validation failure means the case must be re-dispatched or marked failed;
the invalid output is not treated as a successful raw output.

If the underlying model/API reports an invalid structured-output condition such as refusal
or `max_tokens`, the framework treats that case as an execution failure rather than feeding
partial output to the judge as if it satisfied the target schema.

If `output_schema` is absent, the execute-subagent path remains raw-text output as today.

## 5. Testing Contract

Offline tests must cover:

- loading and preserving `target.output_schema` in `EvalSpec` / `TargetSpec`,
- rejecting invalid, non-root-object, recursive/reference-bearing, oversized, or too-deep
  `output_schema` values with clear `target.output_schema` errors,
- deterministic no-key output validation against the supported schema subset,
- keyed executor `output_config` forwarding for legacy `run_prompt`,
  `evaluate-artifact`, and `evaluate-artifact-variance`,
- keyed backward compatibility: no `output_config` key when no schema is configured,
- backward compatibility for artifacts that omit `output_schema`,
- no-key skill instructions that mention the forced structured-output tool and
  `target.output_schema`, and fail closed on zero/multiple/malformed tool outputs.
