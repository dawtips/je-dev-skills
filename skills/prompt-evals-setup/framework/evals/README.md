# evals — prompt evaluation framework

LLM-graded prompt/agent evaluation. Generate a diverse test dataset from a
plain-English task description, run your prompt-under-test against it, and grade
each output with an LLM judge. Full design: [../docs/PROMPT_EVAL_FRAMEWORK_SPEC.md](../docs/PROMPT_EVAL_FRAMEWORK_SPEC.md).

## Layout

```
evals/
  evaluator/          # the framework (vendored reference implementation)
  prompts/            # the 3 (+1) framework prompts — these ARE the framework
  datasets/           # frozen *.json datasets (+ provenance). git-ignored
  runs/               # timestamped result artifacts (json + html). git-ignored
  prompts_under_test/ # your versioned prompt/agent definitions
  examples/           # offline smoke test + fake client
  tests/              # unit tests for the pure logic (stdlib unittest)
  config.py           # models, temperatures, thresholds, paths
  run_eval.py         # copy-and-edit entrypoint
```

## Verify the install (offline, no API key)

```bash
python -m unittest discover -s evals/tests -t .   # unit tests
python -m evals.examples.smoke_test               # full pipeline with a fake client
```

## Run for real

```bash
pip install -r evals/requirements.txt
export ANTHROPIC_API_KEY=sk-...

python -m evals.run_eval generate   # build + freeze the dataset (one-time, expensive)
python -m evals.run_eval evaluate   # run the prompt-under-test + grade (repeat as you iterate)
```

Open the newest `evals/runs/<timestamp>/output.html` to read the scored report.

## Single-shot vs. agentic

- **Single-shot:** `run_function(prompt_inputs) -> str`.
- **Agentic:** `run_function(prompt_inputs) -> Trajectory` (carries `final_output`
  plus the ordered `steps`/tool calls). Grading then scores process as well as
  the final output. See `Trajectory`/`Step` in `evaluator/schemas.py`.

## Iterating

Freeze the dataset once. Re-run `evaluate` against the **same** dataset for every
prompt revision to compare versions apples-to-apples. Regenerate only when the
task or input schema changes.
