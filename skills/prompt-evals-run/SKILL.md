---
name: prompt-evals-run
description: This skill should be used when the user asks to "run a prompt eval", "evaluate my prompt", "grade prompt outputs", "score my agent", "run the evals", "check my prompt against the dataset", or wants to execute and interpret an LLM-graded evaluation. It wires the prompt/agent under test, runs the plugin-resident eval pipeline against the project's frozen cases.json, and interprets the report.
argument-hint: "[eval name to evaluate, e.g. planner]"
allowed-tools: Bash, Read, Write, Edit, Glob, Task
version: 0.3.0
---

# Run a prompt eval

Execute the system under test against a frozen dataset and grade every output with the
LLM judge (run + grade), then interpret the scored report. Re-run this against the
**same** dataset for each prompt revision to compare versions apples-to-apples.

The machinery is **plugin-resident** — it reads the project's `evals/<name>/` artifacts
and is never copied in. There are **two execution paths**, selected by `EXECUTION_MODE`:

- **Path A — no API key (canonical, `EXECUTION_MODE=in_claude_code`, the default).** This
  skill, driven by the interactive session, dispatches subagents to run and grade each
  case (session auth, **no `ANTHROPIC_API_KEY`**), then the deterministic `evals.aggregate`
  assembles the report. **Single-shot prompts only** — a subagent cannot nest subagents.
- **Path B — keyed fallback (`EXECUTION_MODE=anthropic_api`).** The in-process
  `evaluate-artifact` loop with the Anthropic SDK for executor and judge. Requires the API
  key; supports agentic `Trajectory`; for headless/CI runs.

Both paths route through the **same** `run_evaluation` seam, so assertion gating, K-run
variance, and baseline run-delta behave identically. Framework design:
`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`.

## Preconditions

- `evals/<name>/eval.json` + `cases.json` exist (else run setup / create-dataset).
- For prompt-file mode, the prompt template named by `eval.json` `target.prompt_file`
  exists; its `{placeholder}` tokens match the dataset's `prompt_inputs` keys.

Set up shared paths (run framework commands from `$PE` with **absolute** project paths so
the real `evals` package always resolves):

```bash
PE="${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework"
EVAL="$PWD/evals/planner/eval.json"
CASES="$PWD/evals/planner/cases.json"
RUNS="$PWD/evals/planner/runs"
```

## Procedure — Path A (no API key, default)

### 1. Confirm the mode and choose a run label

```bash
(cd "$PE" && python3 -c "from evals import config; print(config.EXECUTION_MODE)")   # expect: in_claude_code
```

Choose a `run_label` — by convention `improve-<name>-round-NN` inside the improve loop,
else a short slug — and a fresh per-case verdict directory:

```bash
RUN_LABEL="<label>"
VERDICTS_DIR="$RUNS/_verdicts/$RUN_LABEL"
OUTPUTS_DIR="$RUNS/_outputs/$RUN_LABEL"
mkdir -p "$VERDICTS_DIR" "$OUTPUTS_DIR"
```

For no-key K-run variance, repeat this loop once per explicit label `<group>__kNN` (do not
derive labels from wall-clock time), then pass each `$RUNS/<group>__kNN/output.json` to
`aggregate` via repeated `--variance-output` flags.

### 2. For each case: render, dispatch execute, run assertions, maybe dispatch grade

Read `cases.json`'s `cases` array. For **each** case (index `i`):

1. **Render the prompt deterministically** (no model) with the plugin-resident helper —
   it reuses `render()` + `check_placeholders`:

   ```bash
   RENDERED=$(cd "$PE" && python3 -m evals.run_eval render-artifact "$EVAL" "$i")
   ```

2. **Dispatch an execute-subagent** (Task tool, session auth, no key): give it `$RENDERED`
   as its full instruction. Use `config.SUBAGENT_EXECUTOR_MODEL` /
   `config.SUBAGENT_EFFORT`. Single-shot turn — no nested subagents.

   If `target.output_schema` is absent, ask for ONLY the prompt's raw output.

   If `target.output_schema` is present, do not accept raw prose. Dispatch with a
   **forced structured-output tool** named `prompt_eval_output`: the tool is an
   output-sink tool, its input schema is exactly `target.output_schema`, and its
   documented Claude API equivalent is a strict tool (`strict: true`) selected with
   forced-tool behavior (`tool_choice: {"type": "tool", "name": "prompt_eval_output"}`).
   The execute-subagent should have only this output-sink tool available — no
   workspace, network, or subagent tools. If the current client cannot provide a real
   forced tool boundary, **fail closed** and use Path B instead.

   The structured execute-subagent must call `prompt_eval_output` exactly once. Treat
   zero tool calls, multiple tool calls, prose/markdown instead of tool arguments,
   malformed JSON, refusal, or `max_tokens` truncation as execution failure; re-dispatch
   the case or record the case as failed. Persist the tool arguments JSON as the raw
   output only after deterministic validation succeeds:

   ```bash
   OUTPUT_FILE="$OUTPUTS_DIR/case-$(printf '%02d' "$i").txt"
   # With target.output_schema:
   CANDIDATE_FILE="$(mktemp)"
   printf '%s' "$RAW_OUTPUT" > "$CANDIDATE_FILE"
   (cd "$PE" && python3 -m evals.output_schema --eval-json "$EVAL" --output-file "$CANDIDATE_FILE") \
     || { rm -f "$CANDIDATE_FILE"; exit 1; }
   mv "$CANDIDATE_FILE" "$OUTPUT_FILE"

   # Without target.output_schema:
   printf '%s' "$RAW_OUTPUT" > "$OUTPUT_FILE"
   ```

   Run the validation branch only when `target.output_schema` is configured. A non-zero
   validation exit means the candidate bytes are not valid prompt-under-test output; delete
   the candidate and do not send anything to the judge.

3. **Run structural assertions** from `eval.json` (`assertions` + `assertion_policy`)
   against that output:

   ```bash
   EVAL="$EVAL" OUTPUT_FILE="$OUTPUT_FILE" python3 - <<'PY'
   import json, os
   from pathlib import Path
   from evals.artifacts import load_eval_spec
   from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict

   spec = load_eval_spec(os.environ["EVAL"])
   output = Path(os.environ["OUTPUT_FILE"]).read_text(encoding="utf-8")
   gate = evaluate_assertion_gate(output, spec.assertions, spec.assertion_policy)
   print(json.dumps({
       "gate": gate,
       "synthetic_verdict": synthetic_gated_verdict(gate) if gate["judge_skipped"] else None,
   }, indent=2))
   PY
   ```

   Run this from `$PE` (e.g. `(cd "$PE" && EVAL=... OUTPUT_FILE=... python3 - <<'PY' ...)`)
   so `evals` imports resolve.

4. **If `judge_skipped: true`**, do not dispatch a grade-subagent. Write a verdict JSON
   with the synthetic score-1 verdict from `synthetic_gated_verdict(gate)`, the raw output,
   and the assertion evidence.
5. **Otherwise dispatch a grade-subagent** (Task tool): give it the case's
   `task_description`, `prompt_inputs`, `solution_criteria`, the `eval.json`
   `extra_criteria`, and the execute-subagent's output. Instruct it to grade per
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals/prompts/grading.md`
   and emit **only** a JSON object with keys `strengths`, `weaknesses`, `reasoning`,
   `score` (integer 1-10) — the `verdict_schema()` shape.
6. **Write the per-case verdict JSON** to `$VERDICTS_DIR/case-<i:02d>.json` with this
   exact shape (include assertion evidence beside the judge or synthetic verdict):

   ```json
   {
     "test_case": { "...the cases.json case verbatim..." : "..." },
     "output": "<the execute-subagent's raw output>",
     "assertion_gate": {
       "policy": "gate_mandatory",
       "results": [
         { "text": "contains 'kcal'", "passed": true, "evidence": "found 'kcal'",
           "severity": "advisory", "action": "annotate" }
       ],
       "mandatory_failed": false,
       "judge_skipped": false
     },
     "verdict": { "strengths": [], "weaknesses": [], "reasoning": "...", "score": 8 }
   }
   ```

Do the cases in order so filenames sort deterministically (`case-00`, `case-01`, …).

### 3. Assemble the report (deterministic, no model)

```bash
(cd "$PE" && python3 -m evals.aggregate \
  --run-label "$RUN_LABEL" \
  --verdicts-dir "$VERDICTS_DIR" \
  --dataset "$CASES" \
  --runs-dir "$RUNS" \
  --baseline-output "$RUNS/<baseline-label>/output.json" \
  --variance-output "$RUNS/<run-a>/output.json" \
  --variance-output "$RUNS/<run-b>/output.json")
```

`--runs-dir "$RUNS"` directs the report into the project's `evals/<name>/runs/`. The
`--baseline-output` / `--variance-output` flags are explicit — do not infer a "previous"
or "latest" run by timestamp. With no baseline, the report says the delta is unavailable;
with fewer than two variance outputs, it says variance needs ≥2 runs. These are advisory
report sections; they do not change the verdict.

This validates every verdict (`schemas.validate_verdict`, which clamps the score and
**raises** on a malformed one), summarizes, and writes
`$RUNS/$RUN_LABEL/{output.json,output.html}`. If it exits non-zero, a verdict JSON was
malformed — re-dispatch that grade-subagent and re-write the one file.

### 4. Read the report

Open `$RUNS/$RUN_LABEL/output.html`:
- **Summary:** total cases, average score `/10`, **pass rate** (% scoring ≥ `PASS_THRESHOLD`).
- **Per-case table:** scenario, inputs, criteria, raw output, color-coded score, reasoning.

`output.json` holds the full record; each result's `verdict` carries the judge's
`strengths`/`weaknesses` — the most useful signal for *why* a case scored low.

### 5. Diagnose and iterate

This is the **single-pass** "what's wrong; fix and re-run" step — diagnose once, then hand
off. The automated multi-round loop lives in `/je-dev-skills:prompt-engineering-improve`,
not here. Read the shared reference before diagnosing:
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md` (one home,
two readers — cite it, never fork it).

- **First gate — the criteria-vs-prompt guard** → before recommending any rewrite, decide
  whether the **prompt** is wrong or the **success criteria** are. If the judge wants content
  not in the inputs, the rubric demands an unstated format, the rationale conflicts with the
  rubric, or it needs hidden domain knowledge, the **dataset** is the problem — fix it via
  `/je-dev-skills:prompt-evals-create-dataset`, do **not** touch the prompt.
- **Mandatory-criterion failures first** → any case scoring **≤ 3** failed a mandatory
  criterion. Check `extra_criteria` and fix that gate before any secondary-criteria polish.
- **Genuine prompt flaws** → fix the prompt and re-run against the **same** dataset, or
  invoke prompt-engineering-improve to automate the loop.

Keep `SUBAGENT_JUDGE_MODEL` strong and **distinct** from `SUBAGENT_EXECUTOR_MODEL` to avoid
self-grading leakage; widen the dataset for higher confidence on close calls.

## Procedure — Path B (keyed fallback, headless/CI)

Use for unattended/CI runs or agentic `Trajectory` grading.

1. Set `EXECUTION_MODE = "anthropic_api"` in the framework's `config.py` (or export the
   override the project uses).
2. For prompt-file mode, no per-project code is needed — the runner renders
   `target.prompt_file` and calls the executor. If `target.output_schema` is configured,
   `evaluate-artifact` passes it to Claude JSON outputs as
   `output_config={"format":{"type":"json_schema","schema": target.output_schema}}`; if
   absent, `output_config` is omitted. For an embedded agent, use **command-adapter** mode
   (`target.command`) so the project's own code produces output.
3. Run from the framework dir with the absolute `$EVAL`:

   ```bash
   pip install -r "$PE/evals/requirements.txt"
   export ANTHROPIC_API_KEY=...      # name is in config.py (API_KEY_ENV)
   (cd "$PE" && python3 -m evals.run_eval evaluate-artifact "$EVAL" "$RUN_LABEL")
   (cd "$PE" && python3 -m evals.run_eval evaluate-artifact-variance "$EVAL" "<group>" "<k>")
   ```

   Each case executes the prompt/agent, runs the `eval.json` assertions through the policy
   before judge grading (a gated mandatory failure writes the synthetic score-1 verdict and
   skips the judge), and writes `$RUNS/<run_label>/{output.json,output.html}`. A single-shot
   run makes up to `2 × num_cases` calls; K-run variance multiplies that by `K`
   (labels `<group>__k00`, `<group>__k01`, …). State that budget before launching.

   A case whose executor or judge raises (transient API error, malformed grade) is
   recorded as a scored-1 failure carrying an `error` field — and listed under
   `meta.errors` — rather than aborting the whole run, so partial results are never
   lost. Command adapters are bounded by `config.ADAPTER_TIMEOUT_SECONDS` (default 120s)
   so a hung adapter times out into that same per-case failure.

## Definition of done

- A run exists at `evals/<name>/runs/<run_label>/` with `output.json` + `output.html`.
- On Path A, one verdict JSON per case under `runs/_verdicts/<run_label>/` and
  `aggregate` exited 0.
- The report was interpreted: average score, pass rate, and the main weakness themes
  reported back, with a clear next action (fix prompt vs. fix criteria).

## Offline check (no API key)

`(cd "$PE" && python3 -m evals.aggregate --run-label check --verdicts-dir <dir of verdict
JSONs> --runs-dir <a temp dir>)` assembles a report from already-written verdicts with **no
model call**. The framework's own pipeline (fake client) is exercised by
`(cd "$PE" && python3 -m evals.examples.smoke_test)`.
