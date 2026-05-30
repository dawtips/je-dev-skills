---
name: prompt-engineering-author
description: This skill should be used when the user asks to "write a prompt", "author a prompt", "draft a system prompt", "improve this prompt", "refactor my prompt", "make this prompt better", "apply prompt best practices", or wants a strong single-shot prompt built from a task description or an existing prompt refactored against best practices. Standalone and eval-free - it never touches ./evals.
argument-hint: "[task description to author from, OR path to an existing prompt to improve]"
allowed-tools: Read, Write, Edit, Glob
version: 0.1.0
---

# Prompt Engineering: Author

Turn a task (or an existing prompt) into a well-built **single-shot** prompt. Standalone,
eval-free, fast. **Never touches `./evals`.** To then measure and iterate the prompt,
hand it to `/je-dev-skills:prompt-engineering-improve` (which needs a frozen dataset).

This SKILL is a table of contents. **Load each reference only when its step is reached** -
never all up front.

## Modes

- **Mode A - generate:** a task description (+ optional input variables / output
  expectations) -> a new prompt.
- **Mode B - improve:** an existing prompt (+ optional issue list, or a diagnosis handed
  over from `prompt-engineering-improve`) -> a refactored prompt + a short changelog.

Pick the mode from the argument: a task description -> A; a path to / paste of an existing
prompt -> B.

## Procedure

### Mode A - generate

1. **Clarify the task.** Name the deliverable, its scope, the audience, and the success
   condition. Identify the input variables - each becomes a `{placeholder}`. Identify the
   output shape (sections, length as a concrete range).
2. **Climb the ladder only as far as needed.** Read
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/techniques.md` and
   start at Rung 1, adding rungs only if the task genuinely needs them.
3. **Obey the constraints.** Read
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/anti-patterns.md`
   and apply it as you write.
4. **Emit the prompt** as a text file at a path the user chooses, plus the list of
   declared `{placeholder}` variables. Do **not** write anything under `./evals`.

### Mode B - improve

1. **Gather the diagnosis.** Use the user's issue list, or the dominant theme + chosen
   rung handed over from `prompt-engineering-improve`.
2. **Follow the shared rewrite procedure.** Read and follow
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`
   (which itself pulls in `techniques.md` + `anti-patterns.md`).
3. **Emit** the refactored prompt + a short changelog (technique -> weakness targeted).
   Preserve the prompt's `{placeholder}` set exactly.

## Definition of done

- A valid prompt text file exists at the user-chosen path with its declared
  `{placeholder}` variables listed back to the user.
- **Mode B** additionally emits a changelog of techniques applied.
- **Nothing under `./evals` was created or modified** (this skill is eval-free).

## Boundaries

- **Single-shot prompts only** in v1. If the task needs two jobs (extract->summarize) or
  multiple tools, that is chaining/agentic - flag it and point to `workflow-design-*` /
  `agent-build-*`, do not cram it into one prompt (techniques.md Rung 7).
- This skill does **not** define success criteria or build datasets (that is
  `prompt-evals-create-dataset`) and does **not** run evals (that is
  `prompt-evals-run` / `prompt-engineering-improve`).
