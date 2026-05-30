# CLAUDE.md

The working agreement for this repo is tool-neutral and lives in `AGENTS.md`. Read and
follow it.

@AGENTS.md

## Claude Code specifics

- Skills resolve plugin-relative paths via `${CLAUDE_PLUGIN_ROOT}`; keep references under it.
- When iterating on the skills in this repo, use the `skill-creator` / `plugin-dev`
  companion plugins (install, don't vendor — see `CONTRIBUTING.md`).
- Before declaring a task done, run the linter and the offline test suites listed in
  `AGENTS.md` and paste the actual output.
