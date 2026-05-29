# Citations

Dated source list grounding the `workflow-design-*` skills, plus a **volatile-values**
subsection for details that change faster than the design (model IDs, tool names,
community-lore figures). Source grounding: `docs/WORKFLOW_DESIGN_SPEC.md` §10.

**Convention.** Primary Anthropic sources first; third-party material is secondary
corroboration. Everything that is liable to change carries an explicit *as of* date.
Other reference files (especially `model-selection.md` and `patterns.md`) cite *this*
file rather than hardcoding volatile specifics.

## Table of contents

1. [Primary sources (Anthropic)](#primary-sources-anthropic)
2. [Secondary / corroborating sources](#secondary--corroborating-sources)
3. [Volatile values (re-check on each use)](#volatile-values-re-check-on-each-use)

---

## Primary sources (Anthropic)

- **Agent Skills — overview & best practices.** SKILL.md frontmatter, progressive
  disclosure, scripts-vs-instructions, discovery-optimized descriptions.
  Anthropic docs: <https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview>
  and the engineering best-practices post. *As of 2026-05-29.*
- **Claude Code sub-agents.** `.claude/agents/` markdown agents, the agent/Task tool,
  one-level-deep delegation, context isolation, the four-part subagent contract.
  Anthropic docs: <https://docs.anthropic.com/en/docs/claude-code/sub-agents>.
  *As of 2026-05-29.*
- **Building Effective Agents** — Schluntz & Zhang, **19 Dec 2024**. The five
  workflow patterns (prompt chaining, routing, parallelization, orchestrator-workers,
  evaluator-optimizer), the augmented-LLM building block, and "start simple; add
  complexity only when it improves outcomes."
  <https://www.anthropic.com/research/building-effective-agents>.
- **How we built our multi-agent research system** — Anthropic engineering post. The
  orchestrator-workers pattern in practice, effort-scaling heuristics (1 agent for
  fact-finding; 2–4 for comparisons; 10+ for complex investigation), the artifact
  pattern, and the ~15× token-cost figure.
  <https://www.anthropic.com/engineering/built-multi-agent-research-system>.
  *As of 2026-05-29.*

---

## Secondary / corroborating sources

- **Requirements engineering** — functional/non-functional requirements, MoSCoW
  prioritization, INVEST criteria, Given-When-Then acceptance criteria, definition of
  done, and interview *saturation*. Classical BA / solution-architecture practice.
- **Evaluation rigor** — LLM-as-judge with explicit rubrics, categorical integer
  scales, judge calibration, and known judge biases (position, verbosity,
  self-preference). Grounds the `rubrics` vocabulary and `rubric-templates.md`.
- **Workflow formalisms** — Hoare-logic pre/postconditions and design-by-contract
  (the `preconditions`/`postconditions` and per-step contracts); DAGs / state
  machines (step ordering + `pattern`); Temporal-style retry / idempotency / saga
  compensation (the `retry`, `rollback`, `retry_idempotency`,
  `rollback_compensation` dimensions).

---

## Volatile values (re-check on each use)

These change faster than this skill. **Do not hardcode them into the schema or skill
prose** — cite them from here, and re-verify against current Anthropic docs before
relying on them.

### Current Claude model IDs

Referenced by `model-selection.md` (which recommends by *tier* — Haiku / Sonnet /
Opus — and resolves to an ID here). Map tier → current ID, then verify against the
[models overview](https://docs.anthropic.com/en/docs/about-claude/models/overview)
before use:

| Tier | Current model ID | Notes |
|------|------------------|-------|
| Haiku | `claude-haiku-4-5` | Fastest / cheapest; easy tasks (classification, extraction). |
| Sonnet | `claude-sonnet-4-5` | Balanced; moderate reasoning, synthesis, drafting. |
| Opus | `claude-opus-4-1` (and newer Opus 4.x) | Most capable; hard, open-ended, high-stakes work. |

*As of 2026-05-29.* Model IDs and the lineup change frequently — treat this table as
a snapshot and confirm the exact current IDs and aliases in the models-overview doc.
The blueprint schema deliberately stores only the **tier** (`haiku|sonnet|opus|inherit`),
never a pinned ID, so blueprints survive lineup changes.

### The Task → Agent tool rename

The tool that spawns a subagent has been referred to as both the **Task** tool and
the **Agent** tool across Claude Code versions; the naming has churned. Treat the
*capability* (delegating a bounded subtask to a subagent) as stable and the exact
tool name as volatile — verify the current name in the
[sub-agents doc](https://docs.anthropic.com/en/docs/claude-code/sub-agents) rather
than hardcoding it. *As of 2026-05-29.*

### "Max parallel subagents" is community lore

Specific numbers for the maximum number of subagents that can run in parallel (often
quoted as a fixed figure) are **community lore, not an official, documented limit.**
Do not encode any such number as a hard constraint in a blueprint. Scale subagent
count by the *task* (the effort-scaling heuristics in `model-selection.md`) and the
~15× token-cost trade-off, and verify any platform-imposed concurrency limit against
current docs if it matters. *As of 2026-05-29.*
