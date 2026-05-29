# je-dev-skills

A Claude Code **plugin** of skills for adding LLM-graded prompt/agent evaluation to
any project. Generate a diverse test dataset from a plain-English task, run your
prompt-under-test against it, and grade each output with an LLM judge into a scored
report.

## Skills

| Skill | Invoke | What it does |
|-------|--------|--------------|
| `prompt-evals-setup` | `/je-dev-skills:prompt-evals-setup` | One-time init: vendor the eval framework into `./evals`, configure it, verify offline. |
| `prompt-evals-create-dataset` | `/je-dev-skills:prompt-evals-create-dataset` | Define a task + input spec + mandatory criteria, generate & freeze a dataset, audit the criteria. |
| `prompt-evals-run` | `/je-dev-skills:prompt-evals-run` | Wire the prompt/agent under test, run the evaluation, read the report, iterate. |

The skills form a lifecycle: **setup → create dataset → run eval (repeat)**, mapping
onto the framework's generate → run → grade stages.

## Workflow Design skills

| Skill | Invoke | What it does |
|-------|--------|--------------|
| `workflow-design-interview` | `/je-dev-skills:workflow-design-interview` | Run a staged discovery interview that turns an idea into a checked `./workflows/<name>.blueprint.md`. |
| `workflow-design-validate` | `/je-dev-skills:workflow-design-validate` | Run a deterministic completeness check over a workflow blueprint and report the gaps to fix. |

The skills form a lifecycle: **interview → validate (repeat)** — design the blueprint,
then lint it for completeness until it passes. See the design spec at
[docs/WORKFLOW_DESIGN_SPEC.md](docs/WORKFLOW_DESIGN_SPEC.md).

## Design & framework

- **Spec & setup guide:** [docs/PROMPT_EVAL_FRAMEWORK_SPEC.md](docs/PROMPT_EVAL_FRAMEWORK_SPEC.md)
- **Reference implementation (Python):** bundled in
  [skills/prompt-evals-setup/framework/evals/](skills/prompt-evals-setup/framework/evals/),
  copied into a project by the setup skill.

## Install / try locally

```bash
claude --plugin-dir /path/to/je-dev-skills
# then, in a target project:
/je-dev-skills:prompt-evals-setup
```

The framework's own tests run offline (no API key):

```bash
cd skills/prompt-evals-setup/framework
python -m unittest discover -s evals/tests -t .
python -m evals.examples.smoke_test
```
