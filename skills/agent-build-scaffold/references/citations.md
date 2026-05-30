# Citations: agent-build-*

Dated references for the volatile Claude Code details used by
`agent-build-scaffold`. Re-check these before relying on generated artifacts in a
target project.

## Primary Sources

- Anthropic Agent Skills documentation: SKILL.md frontmatter, progressive
  disclosure, scripts-vs-instructions, and discovery-optimized descriptions.
  As of 2026-05-30.
- Anthropic Claude Code subagents documentation: `.claude/agents/` markdown
  agents, tool allowlists, context isolation, and one-level delegation behavior.
  As of 2026-05-30.
- Anthropic Claude Code hooks documentation: hook configuration shape, event
  names, command execution, and exit-code blocking behavior. As of 2026-05-30.
- Anthropic "Building Effective Agents" research note: start simple, use
  workflows when deterministic control is available, add agents only for genuine
  judgment. As of 2026-05-30.

## Volatile Values

### Subagent Frontmatter

The generated subagent uses `name`, `description`, `model`, and `tools`
frontmatter. Current Claude Code subagent docs require `name` and `description`;
verify the full schema before using generated files in a new runtime version.

### Model And Effort Names

Blueprints store model tiers such as `haiku`, `sonnet`, `opus`, or `inherit`.
Generated files preserve the provided value, but the user should confirm current
runtime aliases and billing implications before running.

### Hook Event Names

The scaffolder defaults rubric gates to `SubagentStop` and emits the documented
command-hook nesting. Current Claude Code docs use exit code `2` for blocking
policy hooks; verify event names and blocking semantics before treating the hook
as a hard gate.

### Task Or Agent Tool Naming

Claude Code versions and clients have referred to subagent dispatch as either
Task or Agent. Generated command prose describes the capability, not a hardcoded
tool name. Use the current client affordance for bounded subagent dispatch.
