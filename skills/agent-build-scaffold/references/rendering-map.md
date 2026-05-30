# Blueprint Element To Claude Code Construct

This is the canonical mapping `agent-build-scaffold` applies. Every rendered
artifact is produced by `../scripts/scaffold.py` and covered by offline tests in
`../scripts/tests/`.

Volatile Claude Code specifics, such as subagent frontmatter fields, model
aliases, hook event names, and the Task/Agent tool name, are cited from
`citations.md`. The scaffolder emits a conservative skeleton and requires a
runtime verification step before relying on volatile behavior.

## Mapping Table

| Blueprint element | Rendered to | Renderer | Determinism |
|---|---|---|---|
| `steps[].kind: deterministic` | `.claude/scripts/<id>.sh` | `render_step_script` | deterministic |
| `steps[].kind: agentic` | paired `.claude/agents/<subagent-id>.md` | `render_subagent` | contained non-determinism |
| subagent contract: `objective`, `output_format`, `tools`, `boundaries` | `tools` in frontmatter; the other three as body sections | `render_subagent` | declarative |
| rubric `gate` | explicit gate script `.claude/hooks/<name>-gate.sh` named by the generated command | `render_hook` | deterministic |
| side-effecting step | script with namespaced, sanitized `.agent-build-state/<step-id>-<safe-idempotency-key>.done` marker | `render_step_script` | deterministic guard |
| reversible step | script rollback note | `render_step_script` | documentation only |
| blueprint inputs | slash-command `argument-hint` | `render_entry_command` | deterministic |
| whole workflow | `.claude/commands/<workflow>.md` | `render_entry_command` | deterministic sequencing |

## Load-Bearing Rules

1. `output_format` is a body section, never frontmatter. Claude Code subagent
   frontmatter does not provide a portable output schema field; structured output
   is requested in the prompt body and checked by downstream deterministic glue.
2. The scaffolder warns when an agentic step looks mechanical. Extraction,
   parsing, formatting, lookup, sorting, filtering, and fixed transformations are
   script candidates unless the blueprint gives a genuine judgment signal.
3. Side-effecting markers are namespaced by step and sanitize runtime values
   before using them in paths.
4. Gate scripts are invoked explicitly after a score file exists. They are not
   auto-registered as project-wide Claude Code hooks because lifecycle hook
   timing is too broad for per-workflow score files.
5. The generated command keeps orchestration one level deep. It may dispatch
   generated subagents, but generated subagents must not dispatch nested agents.

## Not Rendered In This Cut

- A keyed Agent SDK/headless wrapper. The interactive path runs through Claude
  Code session auth; headless execution remains a future wrapper.
- Model or effort auto-tuning. The blueprint can recommend tiers; the user
  verifies current runtime names before use.
- Fully implemented business logic. Deterministic scripts are placeholders with
  stable headers, guards, and rollback notes for the user to fill in.
