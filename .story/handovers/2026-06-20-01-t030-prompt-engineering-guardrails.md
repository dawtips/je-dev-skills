# T-030 — Fold ISS-001 agent-prompt patterns into the prompt-engineering skills

**Date:** 2026-06-20 · **Branch:** `feat/prompt-engineering-guardrails` · **Ticket:** T-030 (complete) · **Issue:** ISS-001 (resolved)

## What was done
ISS-001 (field report on 52 production agents) surfaced six agent-prompt design patterns. Audit found patterns 5 (specific inputs → Rung 1) and 6 (narrow scope → Rung 8 single-shot boundary) already covered. Folded in patterns 1–4:

- **prompt-engineering-author**
  - `anti-patterns.md`: reconciled "say what to do, not what to avoid" — the test is **specificity, not polarity**. A *named* failure-mode prohibition ("do not invent unstated facts") is concrete and belongs; only *vague* negatives ("be accurate") are the anti-pattern.
  - `techniques.md`: new **Rung 3 "Guardrails: name the failure modes"** (named prohibitions · enforced output-structure labels · named pattern lists · a **guarded** quality self-check). Ladder renumbered 8→9 rungs; `SKILL.md` "Rung 7"→"Rung 8" chaining ref fixed.
  - Self-check fenced to genuine-judgment bars only; deterministic checks stay in code/evals (north star preserved). Threaded through `rewrite-procedure.md` + `SKILL.md` Mode A.
- **prompt-engineering-improve**
  - `improve_step.py`: new high-priority `fabrication` theme (+ `filler`/`boilerplate` under tone_style; `hallucinat*` moved reasoning→fabrication). Matching is **precision-over-recall**: word-boundary regex on added-content verbs (fabricate/invent/hallucinate/made-up-`<noun>`) with clause-scoped, position-aware negation. Ambiguous "unsupported…"/"not in the input" phrasing is deliberately left to the model (it equally describes a §1 criteria problem).
  - `diagnosis.md`: fabrication/filler/self-check-drift → Rung 3; fabrication bumped in priority; documented as "a hint, not the classifier — the model confirms against the verdict text."
- **Durable spec** `2026-05-29-prompt-engineering-skills-design.md` updated to match (ladder, anti-pattern nuance, diagnosis table + priority).

## Verification
`skill_lint` 0/0 · 53 offline tests green (prompt-engineering-improve) · tools 21 + evals framework 215 green · skill-reviewer **Pass** (minor polish only).

## Review
Two rounds: skill-reviewer (Pass) + Codex adversarial review run to convergence. Codex drove real fixes: spec drift, a directionality bug (fabrication vs §1 criteria problem), and a regression I introduced (over-broad negation guard). **Residual:** Codex's final verdict stays "needs-attention" only on contrived contrastive/cross-noun phrasings ("should not invent facts *but did*") that need genuine NLU — an inherent limit of substring tallying (affects all five pre-existing themes too). Disposition by user decision: keep the precision-tuned detector; the model is the confirming classifier. Documented in code + `diagnosis.md`.

## Process note (important)
PR #4 (the workflow-design interactive-viewer spec) was discovered to be a **stale branch** whose `T-025`/`T-026` IDs now collide with completed/other work on `main`. That work was set aside (branch `feat/interactive-viewer-spec` left intact, tickets there renumbered to T-028/T-029 before this pivot). ISS-001 had surfaced untracked during that session; it is now the basis of T-030.

## Follow-ups
- `feat/interactive-viewer-spec` branch still exists (viewer spec, deprioritized) — awaiting a decision to keep or delete.
- Fabrication NLU limitation is documented; revisit only if false routing is observed in practice.
