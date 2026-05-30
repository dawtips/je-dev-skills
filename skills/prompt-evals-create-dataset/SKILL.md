---
name: prompt-evals-create-dataset
description: This skill should be used when the user asks to "create an eval dataset", "generate test cases", "build a prompt eval dataset", "make eval scenarios", "define a task to evaluate", or wants to produce and freeze a dataset for prompt evaluation. It defines the task, input schema, and mandatory criteria in the project's eval.json, then generates and audits a frozen cases.json using the plugin-resident eval framework.
argument-hint: "[short name for the eval, e.g. planner]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.2.0
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
CASES="$PWD/evals/planner/cases.json"
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

### 3. Generate and freeze `cases.json`

Real generation needs the API key and SDK. Run from the framework dir with the absolute
`$EVAL` path:

```bash
pip install -r "$PE/evals/requirements.txt"
export ANTHROPIC_API_KEY=...        # name is in config.py (API_KEY_ENV)
(cd "$PE" && python3 -m evals.run_eval generate-artifact "$EVAL")
```

This writes `evals/<name>/cases.json` with a provenance block (generator model,
timestamp, spec). Generation is one-time and the expensive step. (`generate-artifact`
refuses to run while the `generation` block is unfilled.)

### 4. Audit the generated criteria (critical)

Run the deterministic audit over the frozen dataset:

```bash
(cd "$PE" && python3 -m evals.criteria_audit "$CASES")
```

Interpret the exit code before continuing:

- **exit `0`** — clean automated audit; still do the quick human spot-check below.
- **exit `1`** — criteria/scenario issues were found. Read the printed findings, then
  hand-edit `cases.json` or regenerate it. Re-run the audit until it exits `0`.
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

### 5. Hand off

Report the `cases.json` path, case count, and a sample of criteria. Tell the user to run
`/je-dev-skills:prompt-evals-run` to evaluate a prompt against this frozen dataset.

## Definition of done

- `evals/<name>/cases.json` exists with `num_cases` cases and a provenance block.
- `python3 -m evals.criteria_audit <cases.json>` exits `0`.
- Criteria spot-check confirms they are tight, measurable, task-scoped; scenarios diverse.
- `prompt_inputs` keys match `prompt_inputs_spec` exactly (the framework validates this,
  but confirm values are realistic).

## Offline preview (no API key)

To demonstrate the pipeline shape without a key, run the bundled smoke test from the
framework, which generates a tiny fake dataset:
`(cd "$PE" && python3 -m evals.examples.smoke_test)`. Real datasets require the API key in
step 3.
