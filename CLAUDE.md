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

## Working preferences

These mirror the shared operating rules used across my repos. (They also live in the
machine-global `~/.claude/CLAUDE.md`; they are committed here so they travel with the
checkout and survive a machine rebuild.)

- **Presenting decision options.** When presenting design or decision options (including
  via the AskUserQuestion tool), every option must: avoid detailed code/function names
  (describe behavior in plain language); show a concrete worked example (a named scenario
  and what happens); and give pros, cons, and a recommendation. Put the analysis in the
  prose preamble above the question, lead with the recommended option and say why.
- **Plain-language writing.** Full sentences with a clear subject and verb. Do not
  compress an idea into a stacked hyphenated noun phrase; prefer plain words over coined
  shorthand or symbols; define a term of art the first time it appears; keep the
  connective words ("so", "because", "which means"). Applies to chat, specs, and
  committed prompts.
- **Autonomy and human gates.** Drive multi-step work autonomously and report what
  happened — do not ask permission to advance between steps of an agreed workflow. Pause
  only at a genuine human review/approve gate, or before a truly irreversible or outward
  action. Do not present equivalent-option forks for non-gate decisions; pick the
  sensible default, state it in one line, and proceed. Scale or token cost is not a gate.
- **Second-model review is report-only.** An independent review model (for example Codex)
  only reports findings — it must not edit, create, or delete files. Tell it "review only";
  after each pass run `git status` to confirm it changed nothing; apply every fix yourself.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
