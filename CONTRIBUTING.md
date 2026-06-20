# Contributing to je-dev-skills

## Companion plugins (install alongside — do **not** vendor)

This repo is built and maintained *with* several official Anthropic plugins from
[`claude-plugins-official`](https://github.com/anthropics/claude-plugins-official). They are
**dev-time companions**: install them in your Claude Code environment when working on this repo.
Do not copy ("vendor") them into this tree — depend on the installed plugin instead, so they stay
independently versioned and we don't duplicate or freeze their code.

| Companion plugin | Use it for |
|---|---|
| `skill-creator` | Iterating on the skills *in this repo* — draft → test → review → improve, plus its description-triggering optimizer (`run_loop.py`). |
| `plugin-dev` | Authoring conventions: `skill-development`, `agent-development` (system-prompt design, triggering examples, `validate-agent.sh`), and the `skill-reviewer` / `plugin-validator` agents. |
| `pr-review-toolkit`, `code-review` | Reviewing changes to this repo before merge (correctness, silent failures, type design, simplification). |

Install: `/plugin install <name>@claude-plugins-official`.

### Methodology ownership (avoid overlap)

`skill-creator` and this repo's planned `prompt-engineering-*` group both run an "improve via evals"
loop. Keep the line clean:

- **`skill-creator`** improves **the skills in this repo** (author-time, this repo's own artifacts).
- **`prompt-engineering-improve`** improves **end-user prompts in target projects** (this repo's
  shipped runtime).

They share *techniques*, not *jobs*. Borrow patterns from `skill-creator` (variance, baseline
deltas, non-discriminating-criteria detection, overfitting-aware held-out selection) into our own
framework rather than routing users between two tools for the same task.

## Repo conventions

- **Deterministic over non-deterministic where possible.** Closed-form logic (stopping math, coverage
  checks, deltas, tallies) is **code with offline `unittest` fixtures**, not prose — mirror
  `prompt-engineering-improve/scripts/improve_step.py`. Reserve the LLM for genuine judgment.
- **Group-verb skill naming:** `prompt-engineering-*`, `prompt-evals-*`.
- **Skill descriptions** are third-person with concrete trigger phrases; **bodies** are
  imperative/infinitive (no second person). Use **progressive disclosure** — lean `SKILL.md`,
  detail in `references/` — where there is enough detail to defer; don't split short linear procedures
  for its own sake. `tools/skill_lint.py` checks the deterministic parts (frontmatter, `name`==dir,
  recommended fields, third-person description, `${CLAUDE_PLUGIN_ROOT}` refs resolve, body length).
- **Review, then adversarially verify, before declaring done.** Run the offline tests and report the
  actual output.

## Tests

The eval framework's tests run offline (no API key):

```bash
cd skills/prompt-evals-setup/framework
python3 -m unittest discover -s evals/tests -t .
python3 -m evals.examples.smoke_test
```

The prompt-engineering improve-loop helper's tests:

```bash
python3 -m unittest discover -s skills/prompt-engineering-improve/scripts/tests -t skills/prompt-engineering-improve/scripts
```

The skill linter (and its own tests) — run from the repo root:

```bash
python3 tools/skill_lint.py --root .                              # lint every skill (exit 1 on errors)
python3 -m unittest discover -s tools/tests -t tools              # the linter's unit tests
```
