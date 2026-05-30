# Anti-patterns - what NOT to do

Read alongside `techniques.md`. Every rung you climb risks one of these. The north-star
thesis (shared with `workflow-design-*`): **don't ask the LLM to do what code should.**

## Say what to do, not what to avoid

"Write 3-5 bullets" beats "don't be too long." Positive, concrete instructions are
followed more reliably than prohibitions.

## No over-prompting

Avoid shouting (`CRITICAL: YOU MUST ALWAYS...`), stacked all-caps, and threat-language.
It does not increase compliance and it crowds out the actual instruction. State the
requirement once, plainly.

## Keep examples consistent with the instructions

When you edit a rule, **update every example** that demonstrated the old rule. A
contradicting example is worse than no example - the model follows the example.

## Concrete ranges over vague adjectives

"Concise", "detailed", "professional" are unmeasurable. Give a range, a section list,
a word budget, or a worked example.

## Don't ask the LLM to do what code should (the north star)

If a step is deterministic - validation, formatting, arithmetic on given numbers,
key-set checks - do it in code, not in the prompt. The plugin's whole stance: code for
the reliable/repeatable/auditable; the model only for genuinely open-ended judgment.
A prompt that says "carefully count and verify the JSON keys" should be a validator.

## Resolve conflicting rules

Two instructions that can't both hold ("be exhaustive" + "answer in one sentence") make
output unpredictable. Find the conflict and pick one; don't paper over it with more rules.

## Prefer private reasoning over forced exposed chain-of-thought

Let the model reason adaptively; don't force a verbose visible "Let me think step by
step..." preamble into the user-facing output unless the output spec asks for it.

## Model-aware by construction

- **No assistant prefill** - prefilling the last assistant turn 400s on Claude Opus 4.7+
  (and the framework already moved off it).
- **No manual `budget_tokens`** - prefer adaptive thinking + `effort`.
- **No sampling-param fiddling** for Opus 4.7+ (temperature/top_p/top_k are rejected).

These are best-practice-only and current as of 2026-05; volatile model specifics belong
in a dated citations reference, not hardcoded into a prompt.
