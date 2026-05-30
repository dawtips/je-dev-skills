# je-dev-skills

A Claude Code **plugin** that helps build agent applications end to end, with
deterministic code over non-deterministic model work wherever possible.

## Lifecycle

**Design -> author -> build & run -> measure -> improve**, one journey:

```text
workflow-design-* -> prompt-engineering-author -> agent-build-* -> prompt-evals-* -> prompt-engineering-improve
   (design)             (author prompts)           (build/run)      (measure)          (improve loop)
```

The interactive path runs inside Claude Code on session auth and does not need an
API key. Headless or CI execution uses the keyed fallback (`ANTHROPIC_API_KEY`).

| Skill group | Invoke | What it does |
|-------------|--------|--------------|
| `workflow-design-*` | `/je-dev-skills:workflow-design-{interview,validate,review}` | Turn an idea into a checked `./workflows/<name>.blueprint.md`, lint it for structural completeness, and run advisory semantic review. |
| `prompt-engineering-author` | `/je-dev-skills:prompt-engineering-author` | Author or refactor a strong single-shot prompt from a task description, eval-free. |
| `agent-build-*` | `/je-dev-skills:agent-build-{scaffold,run}` | Render a validated blueprint plus authored prompts into `.claude/` subagents, hooks, scripts, and an entry-point command, then drive them in-session one level deep. |
| `prompt-evals-*` | `/je-dev-skills:prompt-evals-{setup,create-dataset,run}` | Vendor the eval framework, freeze a dataset, run the prompt or agent under test, and grade outputs into a scored report. |
| `prompt-engineering-improve` | `/je-dev-skills:prompt-engineering-improve` | Drive an eval-measured improve loop with deterministic stopping rules and model-authored rewrites. |

Cost note: the interactive subagent-dispatch path uses the Claude Code session.
Headless/CI runs draw on keyed API usage. A full eval round is roughly two model
turns per case: execute plus grade.

See the design specs:
[docs/WORKFLOW_DESIGN_SPEC.md](docs/WORKFLOW_DESIGN_SPEC.md),
[docs/WORKFLOW_DESIGN_REVIEW_SPEC.md](docs/WORKFLOW_DESIGN_REVIEW_SPEC.md),
[docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md](docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md),
and [docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md](docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md).

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
python3 -m unittest discover -s evals/tests -t .
python3 -m evals.examples.smoke_test
```
