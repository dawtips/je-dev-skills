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

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
