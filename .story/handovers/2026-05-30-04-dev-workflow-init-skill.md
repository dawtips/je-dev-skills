# dev-workflow-init skill

## Summary

Added `dev-workflow-init`, a project-setup skill that scaffolds the combined **storybloq +
superpowers** development workflow into any target project. It is the on-ramp to the working
agreement established earlier this session (`AGENTS.md`): a fresh project gets the durable
memory, the docs skeleton, and the working agreement in one step, then follows the loop.

Closes ticket `T-021`.

## Key changes

- `skills/dev-workflow-init/scripts/init_project.py` — deterministic, std-lib-only
  scaffolder. Writes `.story/{config,roadmap,.gitignore,tickets/T-001}`,
  `.story/{handovers,lessons}/.gitkeep`, `docs/superpowers/{specs,plans}/.gitkeep`,
  `AGENTS.md`, `CLAUDE.md`, and an idempotent storybloq runtime block appended to the root
  `.gitignore`. Up-front collision check (no partial scaffolds); `--force` and `--dry-run`.
- `skills/dev-workflow-init/scripts/tests/test_init.py` — 14 offline unit tests (skeleton,
  JSON validity, gitignore preserve+idempotency, collision/force/dry-run, CLI exit codes).
- `skills/dev-workflow-init/SKILL.md` — table-of-contents skill: run the script, then drive
  the judgment parts (seed real roadmap phases + first ticket, fill project-specific blanks).
- `README.md` — new "Project setup" section + a `dev-workflow-init` row in the skills table.
- `.claude-plugin/plugin.json` — added `project-setup`, `storybloq`, `superpowers` keywords.

## Verification (actual output)

- `cd skills/dev-workflow-init/scripts && python3 -m unittest discover -s tests -t .` ->
  `Ran 14 tests ... OK`.
- `python3 tools/skill_lint.py --root .` -> `11 skills | 0 errors | 0 warnings`.
- End-to-end smoke in a temp dir: dry-run previewed 11 files, real run wrote the full tree,
  an existing `.gitignore` was preserved and extended, and a no-`--force` re-run was
  correctly refused.

## Notes

- The generated `AGENTS.md` mirrors this repo's own working agreement, including the
  "Deleting plans once implemented" rule, but is genericized (no je-dev-skills test commands;
  a Tests placeholder for the consumer to fill).
- The skill is tool-neutral: the generated files describe the working agreement and durable
  artifacts and work whether or not the storybloq CLI is installed — consistent with
  CONTRIBUTING.md's "depend on companion tools, don't vendor" policy.
