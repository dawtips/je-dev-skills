---
name: prompt-evals-create-dataset
description: This skill should be used when the user asks to "create an eval dataset", "generate test cases", "build a prompt eval dataset", "make eval scenarios", "define a task to evaluate", or wants to produce and freeze a dataset for prompt evaluation. It defines the task, input schema, and mandatory criteria, then generates and audits a frozen dataset using the project's ./evals framework.
argument-hint: "[short name for the dataset, e.g. meal-plan]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.1
---

# Create an eval dataset

Define an evaluation target and generate a **frozen** test dataset for it using the
project's bundled framework (Stage 1: generate). A frozen dataset is generated once
and evaluated many times — regenerate only when the task or input schema changes.

The framework design (especially §6–§7 on high- vs low-quality inputs) is at
`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`.

## Precondition

Require `./evals` to exist. If absent, stop and tell the user to run
`/je-dev-skills:prompt-evals-setup` first.

## Procedure

### 1. Elicit the four inputs (the quality of these decides everything)

Work with the user to pin down:

- **`task_description`** — one clear, bounded objective naming the deliverable and
  its scope, solvable in a small output budget. Reject vague/compound tasks ("help
  with health"); push for "Write a compact 1-day meal plan for one athlete".
- **`prompt_inputs_spec`** — the **closed set** of input keys the prompt consumes,
  mapped to descriptions **with units/format** (`"height": "Athlete's height in cm"`).
  Keys must be minimal and orthogonal, mapping 1:1 to what the prompt actually reads.
- **`extra_criteria`** (optional, mandatory gates) — short, concrete structural
  must-haves whose absence means failure ("must include caloric total + macro
  breakdown"). Keep soft/aspirational preferences OUT of here. Note: this is a
  **global gate applied at evaluation time** (by `prompt-evals-run`), NOT stored
  per-case in the frozen dataset — decide it now, but it lives in `run_eval.py`.
- **`num_cases`** — coverage vs cost. 10–50+ for confidence; 1–3 only for a smoke check.

### 2. Encode the task

Edit the project's `evals/run_eval.py` and set `TASK`, `PROMPT_INPUTS_SPEC`,
`EXTRA_CRITERIA`, `NUM_CASES`, and `DATASET_FILE`. Use a filesystem-safe dataset
filename derived from the chosen name (e.g. name `meal-plan` →
`DATASET_FILE = f"{config.DATASETS_DIR}/meal_plan.json"`); keep `DATASET_FILE`
and the dataset path you reference in `prompt-evals-run` identical.

### 3. Generate and freeze the dataset

Real generation needs the API key and SDK:

```bash
pip install -r evals/requirements.txt
export <API_KEY_ENV>=...        # name is in evals/config.py (default ANTHROPIC_API_KEY)
python3 -m evals.run_eval generate
```

This writes `evals/datasets/<name>.json` with a provenance block (generator model,
timestamp, spec). Generation is one-time and the expensive step.

### 4. Audit the generated criteria (critical)

Run the deterministic audit over the frozen dataset:

```bash
python3 -m evals.criteria_audit evals/datasets/<name>.json
```

Interpret the exit code before continuing:

- **exit `0`** — clean automated audit; still do the quick human spot-check below.
- **exit `1`** — criteria/scenario issues were found. Read the printed findings,
  then hand-edit the dataset or regenerate it. Re-run the audit until it exits `0`.
- **exit `2`** — unreadable input or setup error. Fix the path, JSON, or framework
  import problem before continuing.

Do not hand off to `prompt-evals-run` while the audit exits `1` or `2`.

After the command is clean, open the dataset and spot-check each case's
`solution_criteria`. Bad criteria silently corrupt every downstream score. Apply
the §7 standard:
- **Good:** 1–4 concise, measurable, task-scoped checks ("Includes all topics mentioned").
- **Bad:** long lists or subjective style ("engaging, creative, well-formatted").

Also confirm `scenario` diversity (no near-duplicates) and that `prompt_inputs`
holds exactly the spec keys. Hand-edit or regenerate cases that drift off-scope.

### 5. Hand off

Report the dataset path, case count, and a sample of criteria. Tell the user to run
`/je-dev-skills:prompt-evals-run` to evaluate a prompt against this frozen dataset.

## Definition of done

- `evals/datasets/<name>.json` exists with `num_cases` cases and a provenance block.
- `python3 -m evals.criteria_audit evals/datasets/<name>.json` exits `0`.
- Criteria spot-check confirms they are tight, measurable, task-scoped; scenarios are diverse.
- `prompt_inputs` keys match `prompt_inputs_spec` exactly (the framework validates
  this, but confirm values are realistic).

## Offline preview (no API key)

To demonstrate the pipeline shape without a key, run the bundled smoke test, which
generates a tiny fake dataset: `python3 -m evals.examples.smoke_test` (then delete
`evals/datasets/smoke.json`). Real datasets require the API key in step 3.
