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

For no-key K-run variance, repeat the Path A case loop once per explicit label
generated from `<group_label>__kNN`. Do not derive labels from wall-clock time. After
the K runs exist, pass each `evals/runs/<group_label>__kNN/output.json` to
`python3 -m evals.aggregate` using repeated `--variance-output` flags.

### 2. For each case: render, dispatch execute, run assertions, maybe dispatch grade, write a verdict JSON

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
3. **Run structural assertions** configured in `evals.run_eval.ASSERTIONS` using
   `evals.run_eval.ASSERTION_POLICY`. These checks run locally against the
   execute-subagent's raw output and produce the `assertion_gate` evidence that
   the skill writes beside the verdict. Persist the raw output first so the
   assertion helper and later troubleshooting read the same bytes:

   ```bash
   OUTPUTS_DIR="evals/runs/_outputs/$RUN_LABEL"
   mkdir -p "$OUTPUTS_DIR"
   OUTPUT_FILE="$OUTPUTS_DIR/case-$(printf '%02d' "$i").txt"
   printf '%s' "$RAW_OUTPUT" > "$OUTPUT_FILE"

   RUN_LABEL="$RUN_LABEL" CASE_INDEX="$i" python3 - <<'PY'
   import json
   import os
   from pathlib import Path
   from evals import run_eval
   from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict

   output_path = (
       Path("evals/runs/_outputs")
       / os.environ["RUN_LABEL"]
       / f"case-{int(os.environ['CASE_INDEX']):02d}.txt"
   )
   gate = evaluate_assertion_gate(
       output_path.read_text(encoding="utf-8"),
       run_eval.ASSERTIONS,
       policy=run_eval.ASSERTION_POLICY,
   )
   print(json.dumps({
       "gate": gate,
       "synthetic_verdict": synthetic_gated_verdict(gate) if gate["judge_skipped"] else None,
   }, indent=2))
   PY
   ```

4. **If `judge_skipped: true`, do not dispatch a grade-subagent.** Write a verdict
   JSON with the synthetic score-1 verdict from `synthetic_gated_verdict(gate)`,
   the raw output, and the assertion evidence.
5. **Otherwise dispatch a grade-subagent** (Task tool): give it the case's
   `task_description`, `prompt_inputs`, `solution_criteria`, the global
   `EXTRA_CRITERIA` (from `evals/run_eval.py`), and the execute-subagent's output.
   Instruct it to grade per `${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals/prompts/grading.md`
   and to emit **only** a JSON object with keys `strengths`, `weaknesses`,
   `reasoning`, `score` (integer 1-10) — the `verdict_schema()` shape. Subagent
   frontmatter has no structured-output field, so the JSON discipline is in the
   instruction; the next step validates it.
6. **Write the per-case verdict JSON** to `$VERDICTS_DIR/case-<i:02d>.json` with
   this exact shape (the skill writes the file). Always include assertion evidence
   beside the judge or synthetic verdict:

   ```json
   {
     "test_case": { ...the dataset case verbatim... },
     "output": "<the execute-subagent's raw output>",
     "assertion_gate": {
       "policy": "gate_mandatory",
       "results": [
         {
           "text": "contains 'kcal'",
           "passed": true,
           "evidence": "found 'kcal'",
           "severity": "advisory",
           "action": "annotate"
         }
       ],
       "mandatory_failed": false,
       "judge_skipped": false
     },
     "verdict": { "strengths": [...], "weaknesses": [...], "reasoning": "...", "score": 8 }
   }
   ```

Do the cases in order so filenames sort deterministically (`case-00`, `case-01`, …).

### 3. Assemble the report (deterministic, no model)

```bash
python3 -m evals.aggregate \
  --run-label "$RUN_LABEL" \
  --verdicts-dir "$VERDICTS_DIR" \
  --dataset evals/datasets/<name>.json \
  --baseline-output evals/runs/<baseline-label>/output.json \
  --variance-output evals/runs/<run-a>/output.json \
  --variance-output evals/runs/<run-b>/output.json
```

The `--baseline-output` and `--variance-output` flags are explicit. Do not infer a
"previous" or "latest" run by timestamp. If no baseline is supplied, the report
analyst section says the baseline delta is not available. If fewer than two variance
outputs are supplied, it says variance needs >=2 runs. These are advisory report
sections only; they do not change the run verdict.

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
   python3 -m evals.run_eval evaluate-variance <group_label> <k>
   ```

   Each case executes the prompt/agent, then runs `run_eval.ASSERTIONS` through
   `ASSERTION_POLICY` before judge grading. A gated mandatory assertion failure
   persists `assertion_gate`, writes the deterministic synthetic score-1 verdict,
   and skips the judge call; advisory assertions are recorded and still grade.

   This makes up to `2 × num_cases` calls for a single-shot prompt (one execute + one
   grade per case) and writes `evals/runs/<run_label>/{output.json,output.html}`.

   K-run variance multiplies that upper bound by `K`: up to
   `K × (run + grade) × num_cases`. State that budget to the user before launching.
   The labels are deterministic and explicit:
   `<group_label>__k00`, `<group_label>__k01`, and so on. Use the resulting
   `output.json` files as `--variance-output` inputs to the report analyst section.

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
