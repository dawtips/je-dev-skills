---
name: prompt-evals-run
description: This skill should be used when the user asks to "run a prompt eval", "evaluate my prompt", "grade prompt outputs", "score my agent", "run the evals", "check my prompt against the dataset", or wants to execute and interpret an LLM-graded evaluation. It wires the prompt/agent under test, runs the project's ./evals pipeline against a frozen dataset, and interprets the report.
argument-hint: "[dataset name to evaluate against, e.g. meal-plan]"
allowed-tools: Bash, Read, Write, Edit, Glob, Task
version: 0.2.0
---

# Run a prompt eval

Execute the system under test against a frozen dataset and grade every output with
the LLM judge (run + grade), then interpret the scored report. Re-run this against
the **same** dataset for each prompt revision to compare versions apples-to-apples.

There are **two execution paths**, selected by `EXECUTION_MODE` in `evals/config.py`:

- **Path A — no API key (canonical, `EXECUTION_MODE=in_claude_code`, the default).**
  This skill, driven by the interactive Claude Code session, dispatches subagents to
  run and grade each case (session auth, **no `ANTHROPIC_API_KEY`**), then a
  deterministic helper (`evals/aggregate.py`) assembles the report. **Single-shot
  prompts only** — a subagent cannot dispatch its own subagents (no nesting).
- **Path B — keyed fallback (`EXECUTION_MODE=anthropic_api`).** The in-process
  `run_eval.py evaluate` loop with the Anthropic SDK for executor and judge.
  Requires the API key; supports agentic `Trajectory`; for headless/CI runs.

Framework design: `${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`.

## Preconditions

- `./evals` exists (else run `/je-dev-skills:prompt-evals-setup`).
- A frozen dataset exists in `evals/datasets/` (else run `/je-dev-skills:prompt-evals-create-dataset`).
- The active prompt is a file at `evals/prompts_under_test/<name>.current.md`
  (the `prompt-engineering-author` output, or hand-written). Its `{placeholder}`
  tokens must match the dataset's `prompt_inputs` keys.

## Procedure — Path A (no API key, default)

### 1. Confirm the mode and locate the inputs

```bash
python3 -c "from evals import config; print(config.EXECUTION_MODE)"   # expect: in_claude_code
ls evals/prompts_under_test/*.current.md
ls evals/datasets/*.json
```

Pick the dataset (the skill argument names it). Choose a `run_label` —
by convention `improve-<name>-round-NN` when called inside the improve loop, else a
short slug. Create a fresh per-case verdict directory:

```bash
RUN_LABEL="<label>"
VERDICTS_DIR="evals/runs/_verdicts/$RUN_LABEL"
mkdir -p "$VERDICTS_DIR"
```

### 2. For each case: render, dispatch execute, dispatch grade, write a verdict JSON

Read the dataset's `cases` array. For **each** case (index `i`):

1. **Render the prompt deterministically** (no model): substitute the case's
   `prompt_inputs` into `<name>.current.md`. The framework's `render()` does the
   substitution and `check_placeholders` reconciles the keys — both are offline.
   Capture the rendered prompt string.
2. **Dispatch an execute-subagent** (Task tool, session auth, no key): give it the
   rendered prompt as its full instruction and ask it to return ONLY the prompt's
   raw output. Use the model/effort in `config.SUBAGENT_EXECUTOR_MODEL` /
   `config.SUBAGENT_EFFORT`. This is a single-shot turn — the subagent must not
   dispatch further subagents.
3. **Dispatch a grade-subagent** (Task tool): give it the case's
   `task_description`, `prompt_inputs`, `solution_criteria`, the global
   `EXTRA_CRITERIA` (from `evals/run_eval.py`), and the execute-subagent's output.
   Instruct it to grade per `${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals/prompts/grading.md`
   and to emit **only** a JSON object with keys `strengths`, `weaknesses`,
   `reasoning`, `score` (integer 1-10) — the `verdict_schema()` shape. Subagent
   frontmatter has no structured-output field, so the JSON discipline is in the
   instruction; the next step validates it.
4. **Write the per-case verdict JSON** to `$VERDICTS_DIR/case-<i:02d>.json` with
   this exact shape (the skill writes the file):

   ```json
   {
     "test_case": { ...the dataset case verbatim... },
     "output": "<the execute-subagent's raw output>",
     "verdict": { "strengths": [...], "weaknesses": [...], "reasoning": "...", "score": 8 }
   }
   ```

Do the cases in order so filenames sort deterministically (`case-00`, `case-01`, …).

### 3. Assemble the report (deterministic, no model)

```bash
python3 -m evals.aggregate \
  --run-label "$RUN_LABEL" \
  --verdicts-dir "$VERDICTS_DIR" \
  --dataset evals/datasets/<name>.json
```

This validates every verdict (`schemas.validate_verdict`, which clamps the score and
**raises** on a malformed one), summarizes, and writes
`evals/runs/$RUN_LABEL/{output.json,output.html}` via the framework's report writers.
It prints the run directory. If it exits non-zero, a verdict JSON was malformed —
re-dispatch the offending grade-subagent and re-write that one file.

### 4. Read the report

Open `evals/runs/$RUN_LABEL/output.html`:
- **Summary:** total cases, average score `/10`, **pass rate** (% scoring ≥ `PASS_THRESHOLD`).
- **Per-case table:** scenario, inputs, criteria, raw output, color-coded score, judge reasoning.

`output.json` holds the full record; each result's `verdict` field carries the
judge's `strengths`/`weaknesses` — the most useful signal for *why* a case scored low.

### 5. Diagnose and iterate

- **Low scores from real output flaws** → fix the prompt and re-run against the
  **same** dataset. Compare `output.json` across runs to confirm improvement, **or
  invoke `/je-dev-skills:prompt-engineering-improve` to automate the loop.**
- **Low scores from bad criteria** (off-scope, subjective) → the dataset is the
  problem, not the prompt. Fix via `/je-dev-skills:prompt-evals-create-dataset` (audit step).
- **Mandatory-criterion failures** cap a score at ≤ 3 — check `EXTRA_CRITERIA` first
  when scores cluster low.

Beware judge/executor leakage: keep `SUBAGENT_JUDGE_MODEL` strong and **distinct**
from `SUBAGENT_EXECUTOR_MODEL`. For higher confidence on close calls, widen the dataset.

## Procedure — Path B (keyed fallback, headless/CI)

Use when you need an unattended/CI run or agentic `Trajectory` grading.

1. Set `EXECUTION_MODE = "anthropic_api"` in `evals/config.py`.
2. Implement/keep `run_prompt` in `evals/run_eval.py` — it renders the file-backed
   `<name>.current.md` (via `render()` + `check_placeholders`) and calls the model.
   For agentic systems return a `Trajectory` (import `from evals.evaluator import
   Trajectory, Step`) and set `PROCESS_CRITERIA` in `run_eval.py`.
3. Run:

   ```bash
   pip install -r evals/requirements.txt
   export ANTHROPIC_API_KEY=...      # name is in evals/config.py (API_KEY_ENV)
   python3 -m evals.run_eval evaluate <run_label>
   ```

   This makes `2 × num_cases` calls for a single-shot prompt (one execute + one
   grade per case) and writes `evals/runs/<run_label>/{output.json,output.html}`.

## Definition of done

- A run exists at `evals/runs/<run_label>/` with `output.json` + `output.html`.
- On Path A, one verdict JSON per case was written under `evals/runs/_verdicts/<run_label>/`
  and `aggregate.py` exited 0.
- The report was interpreted: average score, pass rate, and the main weakness themes
  reported back to the user, with a clear next action (fix prompt vs. fix criteria).

## Offline check (no API key)

`python3 -m evals.aggregate --run-label check --verdicts-dir <a dir of verdict JSONs>`
assembles a report from already-written verdicts with **no model call** — use it to
confirm the aggregation wiring. The framework's own pipeline (fake client) is exercised
by `python3 -m evals.examples.smoke_test`.
