# Session 2026-05-30 — T-015 workflow-design model-selection advisor

## Summary
Shipped **T-015** (phase `backlog` → complete): the new **`workflow-design-advise`**
skill — a deterministic Claude model+effort advisor over a validated blueprint. Built as
a **deliberate override of the spec §2.4 "maybe-never" gate** (user explicitly chose to
build it via `/superpowers:writing-plans` on the advanced-tooling spec, then "ultracode is
on, use that"). Branch `t015-model-selection-advisor` (local merge cleanup per AGENTS.md).
Plan (deleted before merge): `docs/superpowers/plans/2026-05-30-t015-model-selection-advisor.md`.

## What shipped
`skills/workflow-design-advise/`:
- `scripts/advise_model.py` — pure rule scorer `score(TaskSignals) -> (tier, effort,
  rationale)` encoding `model-selection.md`'s routing + effort-scaling tables; a blueprint
  adapter deriving signals structurally; report (Markdown + `--json`); CLI with
  `--strict`/`--budget`/`--date`.
- `SKILL.md` thin wrapper (mirrors `workflow-design-validate`), `requirements.txt`, and
  **seven** offline test files (64 tests).

## Key design decisions (also recorded in advanced-tooling spec §2.6)
1. **Steps are advisory; only subagents are writeable.** The v0.1 schema puts
   `model`/`effort` on `subagents`, **not** `steps` — so the advisor never writes to a
   nonexistent `steps[i].model`; step recommendations are advisory (record in prose).
2. **Recommends tiers, not IDs.** One `MODEL_IDS` constant (update-here comment, cites
   `citations.md`); blueprints stay tier-only.
3. **Honest determinism.** A subagent's task *difficulty* is genuine judgment the
   structure can't settle → assumed `moderate` + surfaced as `needs_review`, never guessed.
4. **Budget is human-supplied.** `--budget high` caps **effort** at `medium` (bounds the
   ~15× multiplier); cost pressure is never inferred from blueprint prose.
5. **Mechanism: script-emits + skill-applies.** The script is a pure analyzer; the SKILL
   drives the `model`/`effort` Edits (validate precedent). Automated `--apply` deferred.

## How it was built — three adversarial review rounds (the notable part)
Implemented inline (sequential single-file TDD; fan-out would conflict), then ran the
adversarial review as **workflows** — the right place for independent perspectives.
- **Round 1** (5 lenses → per-finding verify): **16 confirmed**. Headline: `budget_pressure`
  was tested but **dead** (no derive path set it; the tier-cap was unreachable). Also a
  crash on non-dict list elements, and "unset" model/effort mis-reported as a disagreement.
- **Round 2** (3 lenses, scoped to the fix commit): **4 confirmed — including a regression
  my round-1 fix introduced**: the `_agreement` "unset → undecided" change was too broad
  and let a *half-specified-but-wrong* subagent escape `--strict`. Plus a residual
  `enumerate(scalar)` crash the per-entry guard missed, and a tautological derive test.
- **Round 3** (2 lenses, scoped to round-2 diff): **1 nit** — a falsy non-list container
  (`steps: {}`) collapsed via `or []` before the type guard. Fixed for a uniform contract.

Convergence 16 → 4 → 1 → clean. Every finding fixed and **behaviorally verified** (e.g.
`--budget high` caps plan effort high→medium; `steps: 5` → exit 2 no traceback;
partial-wrong model trips `--strict`; a row-mutation now fails the de-tautologized test).

## Verification (actual output, final merged-candidate)
- `python3 tools/skill_lint.py --root .` → `12 skills | 0 errors | 0 warnings`
- `tools/tests` → `Ran 12 ... OK`
- evals framework → `Ran 145 ... OK`
- `workflow-design-validate` → `Ran 29 ... OK` / `PASS`
- `workflow-design-advise` → `Ran 64 ... OK`
Commits: `bd90ed2` (build) → `795e989` (r1 fixes) → `e11987d` (r2 fixes) → `47939e3`
(r3 nit) → `51f3a40` (lifecycle docs + T-015 complete).

## Lifecycle wiring
`model-selection.md` points to the advisor; `AGENTS.md` lists the new offline suite;
`WORKFLOW_DESIGN_SPEC.md` §9 marks the advisor **shipped**; advanced-tooling spec gains
**§2.6** recording the gate override + design decisions.

## Gotcha worth remembering
A bugfix is itself new code and a frequent source of regressions: round 2 found that a
round-1 fix opened a new `--strict` escape. **Review the fix commit, not just the original
code** — captured as a lesson. Also: don't keep a *tested-but-unreachable* dial (the
original `budget_pressure` tier-cap); make it genuinely reachable end-to-end or remove it.

## Recommended next
Remaining backlog (all still gated/deferred): **T-016** workflow-design visual viewer
(§9; Tier-1 Mermaid is the clean ready candidate), **T-017** prompt-engineering §8.
