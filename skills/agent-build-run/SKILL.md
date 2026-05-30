---
name: agent-build-run
description: This skill should be used when the user asks to "run the scaffolded agent", "drive my agent workflow", "execute the agent-build app", "run the workflow end to end", or after agent-build-scaffold has emitted .claude/ artifacts. It drives the scaffolded application in-session by running deterministic scripts and dispatching agentic steps as subagents, one level deep, honoring rubric gates, loops, and termination conditions with no API key on the interactive path.
argument-hint: "[workflow name, e.g. refund-triage] [workflow inputs]"
allowed-tools: Bash, Read, Write, Edit, Glob, Task
version: 0.1.0
---

# Agent Build: Run

Drive a scaffolded agent workflow from `.claude/commands/<workflow>.md` inside
the current Claude Code session.

## Preconditions

- `agent-build-scaffold` has emitted `.claude/` artifacts.
- Generated scripts have real implementations, not `TODO` placeholders.
- Generated subagents contain the real prompt content and complete boundaries.
- `.agent-build-state/` is ignored by git.

## Procedure

1. **Load the orchestration command.** Read
   `.claude/commands/<workflow>.md` and identify the ordered steps, inputs,
   generated scripts, generated subagents, rubric gates, and termination text.

2. **Run each step in order.**
   - For deterministic steps, run the referenced `.claude/scripts/<id>.sh` with
     the required environment variables.
   - For agentic steps, dispatch the referenced subagent as a bounded task and
     provide only the needed workflow inputs and prior artifacts.
   - Keep dispatch one level deep. A generated subagent must not launch nested
     subagents.

3. **Honor gates.** When a step produces a rubric score, write it to
   `.agent-build-state/<rubric>.score`, then let the generated hook semantics
   block or pass according to the gate threshold.

4. **Honor loops and termination.** Continue only while the command's termination
   text says work remains and all gates pass. Stop on failed scripts, failed
   hooks, missing artifacts, or unclear state.

5. **Report the run.** Summarize inputs, steps executed, artifacts produced,
   gates passed or failed, and any manual follow-up required.

## Definition Of Done

- Every command step has either completed or stopped with a clear reason.
- Runtime state is under `.agent-build-state/`.
- Gate outcomes are recorded.
- The final report names produced artifacts and unresolved work.

## Manual Verification Scenario

Use a small validated blueprint with one deterministic step and one agentic step.
Run `agent-build-scaffold`, fill the generated placeholders, then drive the
generated command with no `ANTHROPIC_API_KEY`. The deterministic step should run
locally, the agentic step should be dispatched through the interactive session,
and the final report should explain every artifact and gate outcome.

## Notes

- This skill does not provide an unattended headless runner. Headless execution
  needs a separate keyed runtime wrapper.
- Generated scripts are source artifacts; `.agent-build-state/` is runtime state.
