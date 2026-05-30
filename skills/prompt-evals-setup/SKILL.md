---
name: prompt-evals-setup
description: This skill should be used when the user asks to "set up prompt evals", "add prompt evaluation to this project", "init prompt-eval", "scaffold evals", or wants to bootstrap LLM-graded prompt/agent evaluation around a specific prompt. It scaffolds lightweight, plugin-resident eval artifacts (evals/<name>/eval.json, cases.json, runs/) in the target project — the shared runner/grader/reporting machinery stays in the plugin and is never copied in.
argument-hint: "[target directory, defaults to current project root]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.2.0
---

# Set up prompt evals

Put evals **around a specific prompt** in the current project. This is the one-time
`init` step: it scaffolds lightweight, project-owned artifacts and leaves the shared
eval machinery in the plugin. After it completes, use `prompt-evals-create-dataset` to
freeze a dataset and `prompt-evals-run` to evaluate.

**Plugin-resident, not vendored.** The runner, grader, aggregation, and reporting code
stay at `${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework` and read the
project's artifacts — they are **not** copied into the project. The project owns only:

```text
prompts/planner.md                 # the prompt template under evaluation
evals/planner/
  eval.json                        # target mode, prompt ref/adapter, judge config
  cases.json                       # frozen cases (created by prompt-evals-create-dataset)
  runs/<label>/output.json|html    # generated run artifacts (gitignored)
```

The design contract is
`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`;
the framework reference is
`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`.

## When to use

Use when a project needs evals around a prompt and `evals/<name>/` does not yet exist
for that prompt. If a project already vendored a full `./evals` package from the old
default, see **Migration** below instead of re-scaffolding over it.

## Procedure

Work from the target project root (the argument if given, else `$PWD`).

### 1. Determine the target and the prompt under test

```bash
TARGET="$PWD"   # or the directory passed as the skill argument
PE="${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework"
```

Pick a short eval `NAME` (e.g. `planner`) and decide the target mode with the user:

- **prompt-file** mode (default happy path): the project has a prompt template file
  (e.g. `prompts/planner.md`) with `{placeholder}` variables; the runner renders it and
  the run path grades the output.
- **command-adapter** mode (escape hatch): the prompt logic is embedded in code; a
  project command reads a case JSON on stdin and returns output JSON on stdout.

For prompt-file mode, confirm the template file exists (create a stub with the user if
not).

### 2. Scaffold the artifacts (no framework copy)

Call the plugin-resident `scaffold-artifact` command (which wraps
`scaffold_eval_artifacts`). It creates `evals/<name>/eval.json` + `runs/.gitkeep` and
adds the run-artifact `.gitignore` entry idempotently — and copies **no** framework
code. Run it **from the framework dir with an absolute `$TARGET`** so the real `evals`
package always resolves (a project `evals/` data dir never shadows it):

```bash
# prompt-file mode (default): pass the project-root-relative prompt file.
(cd "$PE" && python3 -m evals.run_eval scaffold-artifact "$TARGET" planner prompt_file prompts/planner.md)

# command-adapter mode (escape hatch): pass the adapter argv as a JSON array.
(cd "$PE" && python3 -m evals.run_eval scaffold-artifact "$TARGET" agent command_adapter '["python","run_agent.py"]')
```

### 3. Review `eval.json`

Open `evals/<name>/eval.json` and confirm with the user: the `target` block,
`extra_criteria`, `assertions`/`assertion_policy`, and the `generation` block
(`task_description`, `prompt_inputs_spec`, `num_cases`) that `prompt-evals-create-dataset`
will use to freeze `cases.json`. Models/thresholds live in the plugin's `config.py`
(read-only here); the per-eval judge knobs live in `eval.json`.

### 4. Verify the scaffold landed (offline, no API key)

```bash
test -f "$TARGET/evals/planner/eval.json" && echo "eval.json OK"
test -f "$TARGET/evals/planner/runs/.gitkeep" && echo "runs/ kept"
# The framework must NOT have been copied into the project:
test ! -e "$TARGET/evals/evaluator" && echo "no framework copy (good)"
grep -q "evals/\*/runs/\*" "$TARGET/.gitignore" && echo ".gitignore wired"
```

The machinery's own offline suite is plugin-owned (run it from the framework, not the
project): `(cd "$PE" && python3 -m unittest discover -s evals/tests -t .)`.

### 5. Report and hand off

Confirm: artifacts scaffolded, `eval.json` reviewed, `.gitignore` wired, no framework
copied. Next: `/je-dev-skills:prompt-evals-create-dataset` to freeze `cases.json`, then
`/je-dev-skills:prompt-evals-run` to evaluate. Running keyed/headless later needs
`pip install -r "$PE/evals/requirements.txt"` and the API key named by `config.API_KEY_ENV`.

## Migration (projects that vendored `./evals`)

The old default copied the whole framework into `./evals`. Those projects keep working —
the legacy `python -m evals.*` commands are unchanged. To migrate to the plugin-resident
layout: keep your `evals/datasets/*.json` (rename to `evals/<name>/cases.json`) and your
prompt file; scaffold `eval.json` per Step 2; then delete the vendored package
(`evals/evaluator/`, `evals/run_eval.py`, etc.) so the single source of truth is the
plugin. Do this only with the user's confirmation.

## Definition of done

- `evals/<name>/eval.json` and `runs/.gitkeep` exist; `cases.json` is created later.
- No framework code copied into the project (`evals/evaluator/` absent).
- `.gitignore` ignores `evals/*/runs/*` (keeping `runs/.gitkeep`).
- `eval.json` reviewed with the user (mode, judge config, generation block).

## Notes

- Python 3.10+ is required. The pure-logic machinery needs no third-party deps; keyed
  runs need the `anthropic` package (in the framework's `requirements.txt`).
- Never edit the plugin's `framework/evals/` from a target project — it is shared. All
  project-specific configuration lives in `eval.json`.
