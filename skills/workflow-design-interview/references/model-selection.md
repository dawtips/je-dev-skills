# Model & effort selection

Guidelines for choosing a Claude `model` and an `effort` level for each agentic step
or subagent in a blueprint. Loaded by Stage 4 of the interview (the determinism
pass), alongside `patterns.md`. Source grounding: `docs/WORKFLOW_DESIGN_SPEC.md` §6
(stage 4) and §10; the multi-agent research post's effort-scaling heuristics.

> **Claude models only for now.** This skill recommends within the Claude lineup.
> **Concrete model IDs are not hardcoded here** — they live in `citations.md` (the
> volatile-values subsection) so they update as the lineup changes. Recommend by
> *tier* (Haiku / Sonnet / Opus) and resolve to a current ID at build time.

The recommendation is always made **with a written rationale** in the blueprint, the
same way step classification is. Three inputs drive every choice.

## Table of contents

1. [The three inputs](#the-three-inputs)
2. [Routing heuristic: easy to Haiku, harder to Sonnet/Opus](#routing-heuristic-easy-to-haiku-harder-to-sonnetopus)
3. [Effort-scaling heuristics](#effort-scaling-heuristics)
4. [Putting it together: model + effort per step](#putting-it-together-model--effort-per-step)
5. [Worked recommendations](#worked-recommendations)

---

## The three inputs

Decide `model` + `effort` from:

1. **Desired output** — structure and fidelity. Tight structured extraction or
   exact-format JSON tolerates a smaller model; open-ended synthesis, nuanced
   judgment, or long-horizon reasoning wants a larger one.
2. **Task complexity** — depth of reasoning. A lookup or single-step classification
   is easy; a multi-source comparison is harder; novel multi-step problem-solving is
   complex.
3. **Cost/token minimization** — the smallest model and lowest effort that *reliably*
   clears the bar. Do not over-provision: an Opus call where Haiku suffices is wasted
   tokens, and multi-agent escalation already costs ~15× (see `patterns.md`).

The goal is the **cheapest model + effort that meets the quality bar**, not the
biggest available.

---

## Routing heuristic: easy to Haiku, harder to Sonnet/Opus

Match the model tier to task difficulty (resolve tiers to IDs via `citations.md`):

| Difficulty | Signs | Tier |
|------------|-------|------|
| **Easy** | Classification, extraction, formatting, short lookups, bounded inputs, a known-correct answer | **Haiku** |
| **Moderate** | Multi-step reasoning, comparison/synthesis across a few sources, drafting with judgment | **Sonnet** |
| **Hard** | Novel open-ended problem-solving, long-horizon planning, high-stakes judgment, orchestration | **Opus** |

Defaults and rules of thumb:

- Start one tier *below* your instinct and step up only if quality is insufficient —
  cheapest-that-works.
- The **orchestrator** in an orchestrator-workers pattern usually warrants the
  strongest tier (it plans and synthesizes); **workers** doing narrow, bounded
  subtasks can often run a smaller tier.
- A routing step that classifies into known buckets is "easy" → Haiku, even if the
  *downstream* paths use larger models.
- `model: inherit` is available where a subagent should match the caller's model
  rather than pin a tier — use it sparingly and note why.

---

## Effort-scaling heuristics

`effort` (`low` .. `max`) scales the depth/thoroughness of work — number of agents,
tool calls, and iterations. Scale it to the task, not the other way round (an
Anthropic-reported scaling pattern from the multi-agent research work):

| Task shape | Agents | Tool calls / iterations | `effort` |
|------------|--------|--------------------------|----------|
| Simple fact-finding / single lookup | 1 agent | a few tool calls | `low` |
| Direct comparison across a handful of items | 2–4 subagents | moderate | `medium` |
| Broad, complex, open-ended investigation | 10+ subagents | many, deep | `high`–`max` |

Guidance:

- Over-provisioning effort is the "50 subagents for a simple query" failure mode —
  match effort to the *real* breadth of the task.
- Higher effort multiplies token cost; combine the effort table with the ~15× caveat
  before committing to `high`/`max`.
- Effort and model tier are independent dials: a Haiku worker can run at `medium`
  effort (many cheap tool calls); an Opus orchestrator might run `low` effort if it
  only plans and delegates.

---

## Putting it together: model + effort per step

For each agentic step / subagent, in Stage 4:

1. Read the step's **desired output** and **complexity** from its `rationale`.
2. Pick a **tier** with the routing heuristic (easy → Haiku, harder → Sonnet/Opus).
3. Pick an **effort** with the effort-scaling table (breadth of work).
4. Apply **cost minimization**: drop a tier or a notch if the cheaper choice still
   clears the bar.
5. Write the choice **with a rationale** into the blueprint:
   `model: <tier> # rationale`, `effort: <level> # rationale`.

---

## Worked recommendations

- **Email triage classifier** (route an inbound email into known categories) —
  bounded input, known-correct label, tight output. → `model: haiku`,
  `effort: low`. "Classification into fixed buckets; cheapest tier suffices."
- **Competitor researcher worker** (research one competitor, return structured
  findings) — moderate synthesis over a few sources, structured output. →
  `model: sonnet`, `effort: medium`. "Bounded subtask, some judgment; mid tier."
- **Research orchestrator** (plan an open-ended brief, decide how many workers,
  synthesize) — open-ended planning + synthesis, high stakes. → `model: opus`,
  `effort: high`. "Plans dynamically and synthesizes; strongest tier earns its cost."
- **CSV→Slack summary** (deterministic) — *no model at all.* `kind: deterministic`,
  no `model`/`effort`. Code is cheaper and exact; do not provision a model.
