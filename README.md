# je-dev-skills

A Claude Code **plugin** for authoring, measuring, and improving prompts — plus
bootstrapping a project's development workflow — with deterministic code over
non-deterministic model work wherever possible.

## Install

**From the marketplace** (recommended):

```text
/plugin marketplace add dawtips/je-dev-skills
/plugin install je-dev-skills@je-dev-skills
```

The first command registers this repo's marketplace (defined in
[.claude-plugin/marketplace.json](.claude-plugin/marketplace.json)); the second installs the
`je-dev-skills` plugin from it. Once installed, the skills below are available as
`/je-dev-skills:<skill>`.

**Local / development** — point Claude Code straight at a checkout, no marketplace needed:

```bash
claude --plugin-dir /path/to/je-dev-skills
# then, in a target project:
/je-dev-skills:prompt-evals-setup
```

## Project setup

Starting a new project? `/je-dev-skills:dev-workflow-init` scaffolds the **storybloq +
superpowers** development workflow into it — the `.story/` durable memory, the
`docs/superpowers/{specs,plans}` docs skeleton, and a tool-neutral `AGENTS.md` + `CLAUDE.md`
working agreement — so every later change follows one loop: roadmap → ticket → spec → plan →
implement + verify → handover → **delete plan**. This is how *this* repo is built, too.

## Lifecycle

**Author -> measure -> improve**, one journey:

```text
prompt-engineering-author -> prompt-evals-* -> prompt-engineering-improve
     (author prompts)          (measure)          (improve loop)
```

The interactive path runs inside Claude Code on session auth and does not need an
API key. Headless or CI execution uses the keyed fallback (`ANTHROPIC_API_KEY`).

| Skill group | Invoke | What it does |
|-------------|--------|--------------|
| `dev-workflow-init` | `/je-dev-skills:dev-workflow-init` | Bootstrap the storybloq + superpowers dev workflow into a project: `.story/` memory, `docs/superpowers/{specs,plans}`, and an `AGENTS.md`/`CLAUDE.md` working agreement. |
| `prompt-engineering-author` | `/je-dev-skills:prompt-engineering-author` | Author or refactor a strong single-shot prompt from a task description, eval-free. |
| `prompt-evals-*` | `/je-dev-skills:prompt-evals-{setup,create-dataset,run}` | Scaffold plugin-resident eval artifacts around a prompt, freeze a dataset, run the prompt under test, and grade outputs into a scored report. |
| `prompt-engineering-improve` | `/je-dev-skills:prompt-engineering-improve` | Drive an eval-measured improve loop with deterministic stopping rules and model-authored rewrites. |

Cost note: the interactive subagent-dispatch path uses the Claude Code session.
Headless/CI runs draw on keyed API usage. A full eval round is roughly two model
turns per case: execute plus grade.

See the design specs:
[prompt-engineering-skills-design.md](docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md)
and [PROMPT_EVAL_FRAMEWORK_SPEC.md](docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md).

## Design & framework

- **Spec & setup guide:** [PROMPT_EVAL_FRAMEWORK_SPEC.md](docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md)
- **Framework (Python):** **plugin-resident** in
  [skills/prompt-evals-setup/framework/evals/](skills/prompt-evals-setup/framework/evals/)
  and never copied into your project. The setup skill scaffolds only the per-project
  `evals/<name>/` artifacts (`eval.json`, `cases.json`, `runs/`); the shared
  runner/grader/reporting machinery stays in the plugin and resolves via
  `${CLAUDE_PLUGIN_ROOT}`.

## Development

This repo follows its own working agreement — read [AGENTS.md](AGENTS.md) (tool-neutral) and
[CONTRIBUTING.md](CONTRIBUTING.md) before changing skills.

The framework's own tests run offline (no API key):

```bash
cd skills/prompt-evals-setup/framework
python3 -m unittest discover -s evals/tests -t .
python3 -m evals.examples.smoke_test
```

The full offline suite (linter + every test group) is listed in [AGENTS.md](AGENTS.md);
run it from the repo root before declaring work done.
