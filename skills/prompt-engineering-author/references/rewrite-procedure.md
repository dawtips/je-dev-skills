# Rewrite procedure - the shared seam

The single home for *how* to produce or improve a prompt. Read by **two** callers:
`prompt-engineering-author` Mode B (improve an existing prompt) **and**
`prompt-engineering-improve`'s rewrite step (after diagnosis). Both read this file by
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`.
It is part of the group contract - moving/renaming it breaks `prompt-engineering-improve`.

## Inputs to a rewrite

- The current prompt text (or, for Mode A generate, the task description).
- The diagnosed weakness (from a user-supplied issue list, or from
  `prompt-engineering-improve`'s diagnosis: the dominant theme + the chosen ladder rung).
- The technique ladder (`techniques.md`) and the constraints (`anti-patterns.md`).
- Guardrail: do not max out the ladder; pick only the minimum rungs required.

## The procedure

1. **Name the single most important fix.** One dominant weakness per round. If the
   diagnosis flags a **mandatory-criterion failure**, that is the fix - nothing else
   matters until the gate passes.
2. **Pick the MINIMUM rungs that fix it.** Use the diagnosis->rung map. Do **not** max
   out the ladder; every added rung costs tokens and risks over-prompting. Prefer the
   lowest rung that plausibly resolves the diagnosed theme.
3. **Apply the rung(s)** to the prompt text, obeying every anti-pattern: prefer positive
   instructions but use *named* prohibitions for add-content failure modes (Rung 3
   guardrails), keep examples consistent with edited instructions, concrete ranges, no
   over-prompting, resolve conflicts, prefer adaptive thinking over forced exposed
   chain-of-thought. A self-check the prompt runs on its own output is for genuine-judgment
   bars only - deterministic checks stay in code, never in the prompt.
4. **Preserve the placeholders.** The set of `{placeholder}` variables must stay exactly
   the closed key set the dataset uses - do not add, drop, or rename a placeholder during
   a rewrite (that breaks the frozen dataset's contract; if the input set must change,
   that is a `prompt-evals-create-dataset` change, not a rewrite).
5. **Soften imperatives.** Replace shouting/threats with plain, single statements.
6. **Emit two things:** the rewritten prompt (Layer-1 text) and a **short changelog** -
   one line per technique applied and which weakness it targets.

## Output contract

- **The prompt** as a text file. In standalone author use, write to a path the user
  chooses (never under `./evals`). In the improve loop, write the candidate to
  `evals/prompts_under_test/<name>.vN.md`, then copy the chosen candidate into
  `evals/prompts_under_test/<name>.current.md` *before* measuring.
- **The changelog** as a short bullet list (technique -> weakness targeted), shown to the
  user / recorded in the round's trace.

## What stays the model's job vs. code's job

The model **names the dominant theme and writes the new prompt text**. The float math,
argmax, stop verdict, tally, and `EXTRA_CRITERIA` freeze are `improve_step.py`'s job -
never re-derive them in prose.
