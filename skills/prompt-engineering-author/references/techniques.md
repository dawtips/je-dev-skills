# Technique catalogue - the escalation ladder

An **escalation ladder**: cheapest / highest-leverage first. When authoring or
rewriting, climb only as far as the diagnosed need requires (see
`rewrite-procedure.md`: pick the minimum rungs; do not max out). Each rung names what
it fixes and the smallest version that delivers it.

## Rung 1 - Clear & direct

State the task, the deliverable, and its scope in plain imperative prose. Name the
audience and the success condition. Most prompts that "don't work" are under-specified,
not under-engineered. **Fixes:** vague output, off-scope answers, missing deliverable.

## Rung 2 - Output guidelines + process steps

Specify the output shape (sections, length as a concrete range, ordering) and, when the
task has a procedure, enumerate the steps the model should follow. Prefer concrete
ranges ("3-5 bullets") over "be concise". **Fixes:** inconsistent length/shape, skipped
sub-tasks, missing required content.

## Rung 3 - Examples (one-shot / multishot)

Show 1-3 worked examples wrapped in `<example>` tags. Make them **diverse** and include
a **corner case**. Examples teach format and edge handling faster than prose rules.
Keep examples **consistent** with the current instructions (an example that contradicts
an edited rule is an anti-pattern). **Fixes:** format drift, edge-case failures,
"almost-right" structure.

## Rung 4 - XML structure (separate instructions from data)

Wrap instructions, input data, and examples in distinct tags (`<instructions>`,
`<input>`, `<examples>`) so the model never confuses what to *do* with what to *read*.
**Fixes:** the model treating data as instructions, structure bleed, injection-ish
confusion on long inputs.

## Rung 5 - Role framing (in-text, v1)

Open with a one-line role ("You are an exacting nutrition coach...") **in the prompt text**
(v1 uses in-text role, not a system/user split - see the skill's non-goals). A role
calibrates tone, vocabulary, and rigor. **Fixes:** wrong register, tone/style off,
under-rigorous answers.

## Rung 6 - Adaptive thinking / reasoning scaffolding

Ask the model to reason before answering on genuinely hard cases - prefer **adaptive
thinking** (let the model decide depth) and private reasoning over forced *exposed*
chain-of-thought. Do **not** set manual `budget_tokens`; prefer `effort`. **Fixes:**
shallow or wrong reasoning on the hard cases, arithmetic/logic slips.

## Rung 7 - Chaining (the single-shot boundary)

When one prompt is doing two jobs (e.g. extract then summarize), splitting into a chain
helps - but a chain is **beyond single-shot** (v1 scope). **Flag it**: recommend the
user consider `workflow-design-*` / `agent-build-*` rather than cramming two jobs into
one prompt.

## Rung 8 - Long-context tips

For long inputs: put the **documents first, the query last**; reference data by tag;
ask the model to quote the relevant span before answering. **Fixes:** lost-in-the-middle
misses, ignored late instructions.

---

**Climbing rule.** Start at the lowest rung that could fix the diagnosed weakness. Each
added rung costs tokens and risks over-prompting (see `anti-patterns.md`). The
diagnosis->rung map in
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md` tells
you which rung a given failure theme points to.
