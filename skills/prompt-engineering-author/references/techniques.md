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

## Rung 3 - Guardrails: name the failure modes

When the failure is the model *adding* something unwanted - inventing facts, padding with
filler, slipping in biased language, or quietly deciding its output is "good enough" - a
positive instruction cannot fix it, because there is no positive behavior to request.
Constrain the failure mode directly. Four cheap, high-leverage guardrails:

- **Named prohibitions (a "what you do NOT do" list).** Enumerate the specific failure
  modes and the reason each is wrong, e.g. "do not invent pain points the input doesn't
  state", "do not open with 'I hope this finds you well' or any filler warm-up". A
  *named* prohibition is concrete and belongs here; a *vague* one ("don't be verbose",
  "be accurate") does not - state those positively or drop them (see `anti-patterns.md`).
  Keep the list short and specific; a wall of prohibitions is over-prompting.
- **Enforced output structure as a guardrail (not just formatting).** Make a failure
  *visible* through the required shape: label each item by source type and flag when
  low-quality sources dominate; require a field that a gap would leave conspicuously
  empty. The structure enforces the constraint; "cite your sources" only hopes for it.
- **Named pattern lists beat generic checks.** Instead of "avoid biased language",
  enumerate the patterns and the why ("rockstar/ninja" = masculine-coded; "cultural fit"
  without defined criteria = can mask bias). The named version catches what the generic
  one misses and teaches the reason.
- **A quality self-check before delivering.** End the prompt with a short check the model
  runs against its *own* output before returning it ("Before answering, confirm: every
  claim traces to the input; no filler opener; within the length range - revise if any
  fails"). Scope it to **genuine-judgment** bars only. A *deterministic* check (key-set
  validation, arithmetic, schema conformance) is **not** a self-check item - it belongs in
  code / evals, never in the prompt (the north star; see `anti-patterns.md`). This rung
  earns its place most when the authored prompt ships **without** an eval harness, where a
  self-check is the only quality gate the prompt has.

**Fixes:** fabricated / unsupported content, filler and boilerplate, biased or coded
language, unlabeled low-quality sourcing, and "good-enough" quality drift.

## Rung 4 - Examples (one-shot / multishot)

Show 1-3 worked examples wrapped in `<example>` tags. Make them **diverse** and include
a **corner case**. Examples teach format and edge handling faster than prose rules.
Keep examples **consistent** with the current instructions (an example that contradicts
an edited rule is an anti-pattern). **Fixes:** format drift, edge-case failures,
"almost-right" structure.

## Rung 5 - XML structure (separate instructions from data)

Wrap instructions, input data, and examples in distinct tags (`<instructions>`,
`<input>`, `<examples>`) so the model never confuses what to *do* with what to *read*.
**Fixes:** the model treating data as instructions, structure bleed, injection-ish
confusion on long inputs.

## Rung 6 - Role framing (in-text, v1)

Open with a one-line role ("You are an exacting nutrition coach...") **in the prompt text**
(v1 uses in-text role, not a system/user split - see the skill's non-goals). A role
calibrates tone, vocabulary, and rigor. **Fixes:** wrong register, tone/style off,
under-rigorous answers.

## Rung 7 - Adaptive thinking / reasoning scaffolding

Ask the model to reason before answering on genuinely hard cases - prefer **adaptive
thinking** (let the model decide depth) and private reasoning over forced *exposed*
chain-of-thought. Do **not** set manual `budget_tokens`; prefer `effort`. **Fixes:**
shallow or wrong reasoning on the hard cases, arithmetic/logic slips.

## Rung 8 - Chaining (the single-shot boundary)

When one prompt is doing two jobs (e.g. extract then summarize), splitting into a chain
helps - but a chain is **beyond single-shot** (v1 scope). **Flag it**: recommend the
user consider splitting into an orchestrated multi-step workflow rather than cramming two
jobs into one prompt.

## Rung 9 - Long-context tips

For long inputs: put the **documents first, the query last**; reference data by tag;
ask the model to quote the relevant span before answering. **Fixes:** lost-in-the-middle
misses, ignored late instructions.

---

**Climbing rule.** Start at the lowest rung that could fix the diagnosed weakness. Each
added rung costs tokens and risks over-prompting (see `anti-patterns.md`). The
diagnosis->rung map in
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md` tells
you which rung a given failure theme points to.
