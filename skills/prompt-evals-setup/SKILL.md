---
name: prompt-evals-setup
description: This skill should be used when the user asks to "set up prompt evals", "add prompt evaluation to this project", "instantiate the eval framework", "init prompt-eval", "scaffold evals", or wants to bootstrap LLM-graded prompt/agent evaluation in the current project. It vendors the bundled Python eval framework into ./evals, configures it, and verifies it offline.
argument-hint: "[target directory, defaults to current project root]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Set up prompt evals

Instantiate the LLM-graded prompt/agent evaluation framework into the current
project. This is the one-time `init` step. After it completes, use
`prompt-evals-create-dataset` to build a dataset and `prompt-evals-run` to evaluate.

The framework is bundled with this skill at
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals`. The full design
is at `${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md` — consult §11
(Bootstrap Procedure) while working.

## When to use

Use when a project needs prompt evaluation and `./evals` does not yet exist. If
`./evals` already exists, do NOT clobber it — run the non-clobbering substrate
update in Step 1, report what was added or still needs manual merge, then point
the user to `prompt-evals-create-dataset`.

## Procedure

Follow these steps in order. Work from the target project root (the argument if
given, else the current working directory).

### 1. Determine the target and guard against clobbering

Set `TARGET` to the skill argument if one was provided, otherwise the current
project root (`$PWD`). Then check for an existing install:

```bash
TARGET="$PWD"   # or the directory passed as the skill argument
ls -la "$TARGET/evals" 2>/dev/null && echo "EXISTS" || echo "ABSENT"
```

If `evals/` already exists, do NOT clobber it. Instead, run the
**non-clobbering substrate update**: copy in ONLY the substrate files that are
missing or that the user has not customized, leaving `config.py`, `run_eval.py`,
and any `prompts_under_test/*.md` the user edited untouched.

```bash
SRC="${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals"
# New top-level substrate modules: safe to add if absent (the framework owns them).
for f in aggregate.py promptprep.py; do
  [ -f "$TARGET/evals/$f" ] || cp "$SRC/$f" "$TARGET/evals/$f"
done
# New tests for the substrate.
for f in tests/test_aggregate.py tests/test_promptprep.py; do
  [ -f "$TARGET/evals/$f" ] || cp "$SRC/$f" "$TARGET/evals/$f"
done
cp -Rn "$SRC/tests/fixtures/." "$TARGET/evals/tests/fixtures/" 2>/dev/null || true
```

For `config.py` (the `EXECUTION_MODE` block) and `run_eval.py` (the file-backed +
mode-aware changes), do NOT overwrite — these are user-editable. Show the user a diff
against the bundled versions and let them merge the `EXECUTION_MODE`/subagent-knob
constants and the mode-aware `main()` by hand if their copy predates the substrate.
Then report what was added and stop.

### 2. Copy the bundled framework into the project

Copy the whole `evals` package wholesale so Python imports (`from evals import ...`)
resolve at the project root, then strip any stale compiled artifacts that may have
been copied along:

```bash
cp -R "${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals" "$TARGET/evals"
find "$TARGET/evals" -name __pycache__ -type d -prune -exec rm -rf {} +
```

Verify the tree landed: `evals/evaluator/`, `evals/prompts/`, `evals/config.py`,
`evals/run_eval.py`, `evals/aggregate.py`, `evals/promptprep.py`, `evals/tests/`,
`evals/examples/`, and the `.gitkeep` dirs `evals/datasets/`, `evals/runs/`, and
`evals/prompts_under_test/`. `aggregate.py` (the no-key Path A report assembler) and
`promptprep.py` (the prompt-prep glue) are part of the substrate — confirm both
copied.

### 3. Configure `evals/config.py`

Read `evals/config.py` and confirm the provider/model/threshold settings with the
user. Defaults target Anthropic Claude:
- `GENERATOR_MODEL` (builds the dataset),
- `EXECUTOR_MODEL` (default for the system under test),
- `JUDGE_MODEL` (strong, and **distinct** from the executor to reduce self-grading bias),
- `API_KEY_ENV` (default `ANTHROPIC_API_KEY`),
- `PASS_THRESHOLD` (a case passes if score ≥ this; default 7).

Edit only what the user wants changed. Keep the judge strong and distinct from the
executor.

### 4. Wire `.gitignore`

Ensure generated artifacts are ignored but the directories are kept. Append to the
project `.gitignore` if these lines are absent:

```
evals/datasets/*
!evals/datasets/.gitkeep
evals/runs/*
!evals/runs/.gitkeep
__pycache__/
*.pyc
```

### 5. Verify offline (no API key required)

Run from the project root so `evals` is importable as the top-level package:

```bash
cd "$TARGET" && python3 -m unittest discover -s evals/tests -t .
cd "$TARGET" && python3 -m evals.examples.smoke_test
```

Both must pass. The unit suite covers the pure logic; the smoke test runs the full
generate → run → grade → report pipeline (single-shot AND agentic paths) with a
fake client. Clean up the smoke artifacts afterward:

```bash
rm -f "$TARGET"/evals/datasets/smoke.json && rm -rf "$TARGET"/evals/runs/smoke-*
```

### 6. Report and hand off

Confirm: framework vendored, config set, `.gitignore` updated, tests + smoke green.
Tell the user the next step is `/je-dev-skills:prompt-evals-create-dataset` to build a
dataset, then `/je-dev-skills:prompt-evals-run` to evaluate. To run for real later:
`pip install -r evals/requirements.txt` and export the API key named by `API_KEY_ENV`.

## Definition of done

- `./evals` exists with the full package.
- `evals/config.py` reviewed/edited with the user.
- `.gitignore` ignores `evals/datasets/*` and `evals/runs/*` (keeping `.gitkeep`).
- Unit tests + smoke test pass offline; smoke artifacts cleaned up.

## Notes

- Python 3.10+ is required. The pure-logic verification needs no third-party deps;
  real runs need the `anthropic` package (in `evals/requirements.txt`).
- Do not edit files under `evals/evaluator/` or `evals/prompts/` during setup —
  they are the vendored framework. Project-specific work happens in `run_eval.py`
  (or a copy) via the later skills.
