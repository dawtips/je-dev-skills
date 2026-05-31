---
name: prompt-evals-create-dataset
description: This skill should be used when the user asks to "create an eval dataset", "generate test cases", "build a prompt eval dataset", "make eval scenarios", "define a task to evaluate", or wants to produce and freeze a dataset for prompt evaluation. It defines the task, input schema, and mandatory criteria in the project's eval.json, then generates and audits a frozen cases.json using the plugin-resident eval framework.
argument-hint: "[short name for the eval, e.g. planner]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.3.0
---

# Create an eval dataset

Define an evaluation target and generate a **frozen** `cases.json` for it (Stage 1:
generate). A frozen dataset is generated once and evaluated many times — regenerate only
when the task or input schema changes.

The framework design (especially §6–§7 on high- vs low-quality inputs) is at
`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`. The machinery
is plugin-resident at `${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework`.

## Precondition

Require `evals/<name>/eval.json` to exist (from `/je-dev-skills:prompt-evals-setup`). If
absent, stop and tell the user to run setup first. Set up the shared paths:

```bash
PE="${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework"
EVAL="$PWD/evals/planner/eval.json"        # absolute path to this eval's config
CASES="$(cd "$PE" && EVAL="$EVAL" python3 - <<'PY'
import os
from evals.artifacts import load_eval_spec
print(load_eval_spec(os.environ["EVAL"]).cases_file)
PY
)"
```

## Procedure

### 1. Elicit the four inputs (the quality of these decides everything)

Work with the user to pin down:

- **`task_description`** — one clear, bounded objective naming the deliverable and its
  scope, solvable in a small output budget. Reject vague/compound tasks ("help with
  health"); push for "Write a compact 1-day meal plan for one athlete".
- **`prompt_inputs_spec`** — the **closed set** of input keys the prompt consumes, mapped
  to descriptions **with units/format** (`"height": "Athlete's height in cm"`). Keys must
  be minimal and orthogonal, mapping 1:1 to what the prompt actually reads.
- **`extra_criteria`** (optional, mandatory gates) — short, concrete structural must-haves
  whose absence means failure ("must include caloric total + macro breakdown"). Keep
  soft/aspirational preferences OUT. This is a **global gate applied at evaluation time**,
  stored in `eval.json` (`extra_criteria`), NOT per-case in the frozen dataset.
- **`num_cases`** — coverage vs cost. 10–50+ for confidence; 1–3 only for a smoke check.

### 2. Encode the task into `eval.json`

Edit `evals/<name>/eval.json` and fill the `generation` block — `task_description`,
`prompt_inputs_spec`, `num_cases` — plus `extra_criteria` and any structural `assertions`.
No per-project Python is edited; the config lives entirely in `eval.json`.

### 3. Generate and freeze `cases.json` - Path A (no API key, default)

Use this path in an interactive Claude Code session. The active session authors the
dataset; no project API key or SDK call is required.

First validate the artifact and generation block from the framework dir:

```bash
(cd "$PE" && EVAL="$EVAL" python3 - <<'PY'
import json
import os
from evals.artifacts import load_eval_spec

spec = load_eval_spec(os.environ["EVAL"])
gen = spec.generation or {}
task = gen.get("task_description")
inputs = gen.get("prompt_inputs_spec")
num_cases = gen.get("num_cases")
if not task:
    raise SystemExit("generation.task_description is required")
if not isinstance(inputs, dict) or not inputs:
    raise SystemExit("generation.prompt_inputs_spec must be a non-empty object")
if not isinstance(num_cases, int) or num_cases < 1:
    raise SystemExit("generation.num_cases must be an integer >= 1")
print(json.dumps({
    "task_description": task,
    "prompt_inputs_spec": inputs,
    "num_cases": num_cases,
    "cases_file": str(spec.cases_file),
}, indent=2))
PY
)
```

Then generate exactly `generation.num_cases` cases in this session and write the
authoritative `$CASES` path resolved from `eval.json`. The frozen dataset must use the
same shape consumed by `prompt-evals-run`, `criteria_audit`, and `aggregate`:

```json
{
  "provenance": {
    "task_description": "<generation.task_description>",
    "prompt_inputs_spec": { "<key>": "<description>" },
    "num_cases": 8,
    "generator_model": "interactive_session",
    "created_at": "<ISO-8601 UTC timestamp>",
    "generation_mode": "in_session_no_key"
  },
  "cases": [
    {
      "task_description": "<same task_description>",
      "scenario": "<concise scenario>",
      "prompt_inputs": { "<key>": "<value for this case>" },
      "solution_criteria": [
        "<measurable case-specific criterion>"
      ]
    }
  ]
}
```

Path A case requirements:

- Write exactly `generation.num_cases` cases.
- Include the Path A provenance block shown above.
- Repeat `generation.task_description` in every case's `task_description`.
- Give every case a non-empty `scenario`.
- Use only and all keys from `generation.prompt_inputs_spec` in every
  `prompt_inputs` object.
- Keep `solution_criteria` to 1-4 concise, measurable, task-scoped checks per case.
- Do not copy `extra_criteria` into individual cases; it remains a global gate in
  `eval.json`.
- Keep scenarios diverse enough to catch different prompt failures, not near-duplicates.

After writing `$CASES`, run the deterministic shape check before the criteria audit:

```bash
(cd "$PE" && EVAL="$EVAL" CASES="$CASES" python3 - <<'PY'
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from evals.artifacts import load_eval_spec

spec = load_eval_spec(os.environ["EVAL"])
gen = spec.generation or {}
expected_task = gen.get("task_description")
expected_inputs_spec = gen.get("prompt_inputs_spec") or {}
expected_keys = set(expected_inputs_spec.keys())
expected_count = gen.get("num_cases")
data = json.loads(Path(os.environ["CASES"]).read_text(encoding="utf-8"))
provenance = data.get("provenance")
if not isinstance(provenance, dict):
    raise SystemExit("cases.json must contain a provenance object")
if provenance.get("task_description") != expected_task:
    raise SystemExit("provenance.task_description must match generation.task_description")
if provenance.get("prompt_inputs_spec") != expected_inputs_spec:
    raise SystemExit("provenance.prompt_inputs_spec must match generation.prompt_inputs_spec")
if provenance.get("num_cases") != expected_count:
    raise SystemExit("provenance.num_cases must match generation.num_cases")
if provenance.get("generator_model") != "interactive_session":
    raise SystemExit('provenance.generator_model must be "interactive_session"')
if provenance.get("generation_mode") != "in_session_no_key":
    raise SystemExit('provenance.generation_mode must be "in_session_no_key"')
created_at = provenance.get("created_at")
if not isinstance(created_at, str) or not created_at.strip():
    raise SystemExit("provenance.created_at must be a non-empty ISO-8601 timestamp")
try:
    parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
except ValueError as exc:
    raise SystemExit("provenance.created_at must be an ISO-8601 timestamp") from exc
if parsed_created_at.tzinfo is None or parsed_created_at.utcoffset() != timedelta(0):
    raise SystemExit("provenance.created_at must be an ISO-8601 UTC timestamp")
cases = data.get("cases")
if not isinstance(cases, list):
    raise SystemExit("cases.json must contain a top-level cases array")
if len(cases) != expected_count:
    raise SystemExit(f"expected {expected_count} cases, found {len(cases)}")
for index, case in enumerate(cases):
    if case.get("task_description") != expected_task:
        raise SystemExit(f"case {index}: task_description must match generation.task_description")
    if not isinstance(case.get("scenario"), str) or not case["scenario"].strip():
        raise SystemExit(f"case {index}: scenario must be a non-empty string")
    prompt_inputs = case.get("prompt_inputs")
    if set((prompt_inputs or {}).keys()) != expected_keys:
        raise SystemExit(f"case {index}: prompt_inputs keys do not match generation spec")
    criteria = case.get("solution_criteria")
    if not isinstance(criteria, list) or not (1 <= len(criteria) <= 4):
        raise SystemExit(f"case {index}: solution_criteria must contain 1-4 items")
    if not all(isinstance(item, str) and item.strip() for item in criteria):
        raise SystemExit(f"case {index}: solution_criteria items must be non-empty strings")
print("dataset shape ok")
PY
)
```

### 4. Generate and freeze `cases.json` - Path B (keyed fallback)

Use this path for headless/CI or unattended generation. It needs the API key and SDK.
Run from the framework dir with the absolute `$EVAL` path:

```bash
pip install -r "$PE/evals/requirements.txt"
export ANTHROPIC_API_KEY=...        # name is in config.py (API_KEY_ENV)
(cd "$PE" && python3 -m evals.run_eval generate-artifact "$EVAL")
```

This writes `evals/<name>/cases.json` with a provenance block (generator model,
timestamp, spec). Generation is one-time and the expensive step. (`generate-artifact`
refuses to run while the `generation` block is unfilled.)

### 5. Audit the frozen dataset (critical)

Run the deterministic audit over the frozen dataset:

```bash
(cd "$PE" && python3 -m evals.criteria_audit "$CASES")
```

Interpret the exit code before continuing:

- **exit `0`** — clean automated audit; still do the quick human spot-check below.
- **exit `1`** — criteria/scenario issues were found. Read the printed findings, then
  hand-edit `cases.json` or regenerate it through the same path. Re-run the audit until
  it exits `0`.
- **exit `2`** — unreadable input or setup error. Fix the path, JSON, or framework import
  problem before continuing.

Do not hand off to `prompt-evals-run` while the audit exits `1` or `2`.

After the command is clean, open `cases.json` and spot-check each case's
`solution_criteria`. Bad criteria silently corrupt every downstream score. Apply the §7
standard:
- **Good:** 1–4 concise, measurable, task-scoped checks ("Includes all topics mentioned").
- **Bad:** long lists or subjective style ("engaging, creative, well-formatted").

Also confirm `scenario` diversity (no near-duplicates) and that `prompt_inputs` holds
exactly the spec keys. Hand-edit or regenerate cases that drift off-scope.

### 6. Hand off

Report the `cases.json` path, case count, and a sample of criteria. Tell the user to run
`/je-dev-skills:prompt-evals-run` to evaluate a prompt against this frozen dataset.

## Definition of done

- `evals/<name>/cases.json` exists with `num_cases` cases and a provenance block. Path A
  provenance contains `generator_model: "interactive_session"` and
  `generation_mode: "in_session_no_key"`; Path B provenance contains the keyed generator
  model.
- `python3 -m evals.criteria_audit <cases.json>` exits `0`.
- Criteria spot-check confirms they are tight, measurable, task-scoped; scenarios diverse.
- `prompt_inputs` keys match `prompt_inputs_spec` exactly (the framework validates this,
  but confirm values are realistic).

## Offline preview (no API key)

To demonstrate the pipeline shape without a live model, run the bundled smoke test from
the framework, which generates a tiny fake dataset:
`(cd "$PE" && python3 -m evals.examples.smoke_test)`. Real project datasets can be
authored without a project API key through Path A in an interactive session; unattended
headless generation uses Path B and requires the API key.
