---
name: run-prompt-eval
description: This skill should be used when the user asks to "run a prompt eval", "evaluate my prompt", "grade prompt outputs", "score my agent", "run the evals", "check my prompt against the dataset", or wants to execute and interpret an LLM-graded evaluation. It wires the prompt/agent under test, runs the project's ./evals pipeline against a frozen dataset, and interprets the report.
argument-hint: "[dataset name to evaluate against, e.g. meal-plan]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Run a prompt eval

Execute the system under test against a frozen dataset and grade every output with
the LLM judge (Stages 2–3: run + grade), then interpret the scored report. Re-run
this against the **same** dataset for each prompt revision to compare versions
apples-to-apples.

Framework design: `${CLAUDE_PLUGIN_ROOT}/docs/PROMPT_EVAL_FRAMEWORK_SPEC.md`.

## Preconditions

- `./evals` exists (else run `/je-dev-skills:setup-prompt-evals`).
- A frozen dataset exists in `evals/datasets/` (else run `/je-dev-skills:create-eval-dataset`).

## Procedure

### 1. Implement the system under test

In `evals/run_eval.py`, implement the `run_prompt` function — the only user-owned
piece. It builds the prompt from `prompt_inputs`, calls the model, and returns the
result. (`run_prompt` is the bundled template's name for the function; the framework
receives it via the `run_function=` parameter — implement/replace `run_prompt`.)

- **Single-shot:** return raw text — `(prompt_inputs: dict) -> str`.
- **Agentic:** return a `Trajectory` — `(prompt_inputs: dict) -> Trajectory` — carrying
  `final_output` plus ordered `Step`s (assistant turns and tool calls). Import from
  `evals.evaluator`:

  ```python
  from evals.evaluator import Trajectory, Step
  ```

  For agentic runs, set the `PROCESS_CRITERIA` constant in `run_eval.py` to grade
  *how* the agent worked (right tools, no needless steps, error recovery), not just
  the final answer. The template threads it through to grading automatically.

### 2. Run the evaluation

```bash
pip install -r evals/requirements.txt
export <API_KEY_ENV>=...        # name is in evals/config.py (default ANTHROPIC_API_KEY)
python3 -m evals.run_eval evaluate
```

Per case this makes one grading call plus whatever calls your `run_prompt` makes —
exactly one for a single-shot prompt (so `2 × num_cases` total), but an arbitrary
number per case for an agent. Results are written to a **timestamped** run at
`evals/runs/<timestamp>/` — never overwriting prior runs.

### 3. Read the report

Open the newest `evals/runs/<timestamp>/output.html`:
- **Summary:** total cases, average score `/10`, **pass rate** (% scoring ≥ `PASS_THRESHOLD`).
- **Per-case table:** scenario, inputs, criteria, raw output, color-coded score, judge reasoning.

`output.json` holds the full record; each result's `verdict` field carries the
judge's `strengths`/`weaknesses` — the most useful signal for *why* a case scored low.

### 4. Diagnose and iterate

- **Low scores from real output flaws** → fix the prompt/agent and re-run against the
  **same** dataset. Compare `output.json` across runs to confirm improvement.
- **Low scores from bad criteria** (off-scope, subjective) → the dataset is the
  problem, not the prompt. Fix via `/je-dev-skills:create-eval-dataset` (audit step).
- **Mandatory-criterion failures** cap a score at ≤ 3 — check `extra_criteria` first
  when scores cluster low.

Beware judge/executor leakage: keep `JUDGE_MODEL` strong and **distinct** from
`EXECUTOR_MODEL`. For higher confidence on close calls, run multiple times or widen
the dataset.

## Definition of done

- A timestamped run exists in `evals/runs/` with `output.json` + `output.html`.
- The report was interpreted: average score, pass rate, and the main weakness themes
  reported back to the user, with a clear next action (fix prompt vs. fix criteria).

## Offline check (no API key)

`python3 -m evals.examples.smoke_test` exercises the full run+grade pipeline (both
single-shot and agentic) with a fake client to confirm wiring before a real run.
