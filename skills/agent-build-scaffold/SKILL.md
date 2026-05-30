---
name: agent-build-scaffold
description: This skill should be used when the user asks to "scaffold an agent", "build the agent from my blueprint", "turn my workflow design into Claude Code files", "generate subagents and hooks", "render my blueprint into a runnable agent", or after workflow-design-validate passes and prompt-engineering-author has produced prompts. It renders a validated blueprint into .claude/ subagents, hooks, scripts, and an entry-point command, warning when a subagent is used where a script would do.
argument-hint: "[path to the validated <name>.blueprint.md]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Agent Build: Scaffold

Render a validated workflow blueprint into Claude-Code-native artifacts:
subagents, deterministic scripts, rubric gate hooks, `hooks.json`, and a single
entry-point command.

## Preconditions

- A validated `<name>.blueprint.md` exists. If no path is provided, find
  candidates with Glob: `./workflows/*.blueprint.md`.
- The blueprint has already passed `workflow-design-validate`.
- Prompt text for agentic steps has been authored or is ready to paste into the
  generated subagent bodies.

## Procedure

1. **Install renderer dependency.**

   ```bash
   pip3 install -r ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/requirements.txt
   ```

2. **Dry-run first.** Read the target plan and warnings before writing files:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/scaffold.py <path> --dry-run
   ```

   If warnings say an agentic step looks mechanical, pause and decide whether the
   blueprint should be simplified before generating artifacts.

3. **Verify volatile runtime details.** Read
   `${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/references/citations.md`
   and confirm current Claude Code behavior for subagent frontmatter, hook event
   names, and the current Task/Agent dispatch affordance.

4. **Write the artifacts.**

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/scaffold.py <path>
   ```

   Existing generated files are not overwritten by default. Re-run with
   `--force` only after reviewing the dry-run output and deciding replacement is
   intentional.

   The command writes:
   - `.claude/agents/<id>.md`
   - `.claude/scripts/<id>.sh`
   - `.claude/hooks/<name>-gate.sh`
   - `.claude/hooks.json`
   - `.claude/commands/<workflow>.md`

5. **Wire real content.**
   - Replace each script `TODO` with deterministic business logic.
   - Paste or reference the authored prompt in each generated subagent body.
   - Keep `output_format` in the body; do not move it into frontmatter.
   - Preserve idempotency guards for side-effecting scripts.

6. **Ignore runtime state.** Add `.agent-build-state/` to the target project's
   `.gitignore` if it is not already ignored.

7. **Hand off to run.** Use `agent-build-run` to drive the generated entry-point
   command in-session.

## Definition Of Done

- Dry-run warnings have been reviewed.
- Artifacts are written under `.claude/`.
- Generated scripts and hooks are executable.
- Agentic prompts and deterministic script bodies have been filled in.
- `.agent-build-state/` is ignored by git.

## Offline Check

```bash
cd ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts
python3 -m unittest discover -s tests -t .
```

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/references/rendering-map.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/references/patterns.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/references/citations.md`
