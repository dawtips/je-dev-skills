# T-031 — Remove the blueprint ecosystem (8 skills + specs + tests + refs)

**Date:** 2026-06-20 · **Branch:** `remove-blueprint-ecosystem` · **Ticket:** T-031 (complete)

## Why
User directive: "get rid of the blueprint and viewer pieces completely." Clarified scope (the
"blueprint" is the shared `v0.1` workflow-design schema woven through ~8 skills, not a single
piece): the user chose **the entire blueprint ecosystem** — everything that reads or writes a
blueprint.

## What was removed (`git rm`)
- **8 skills:** `workflow-design-{interview,validate,review,advise,visualize}`,
  `workflow-document-project`, `agent-build-{scaffold,run}`.
- **5 specs** (described only the removed skills): `WORKFLOW_DESIGN_SPEC.md`,
  `WORKFLOW_DESIGN_REVIEW_SPEC.md`, `2026-05-30-workflow-design-advanced-tooling-spec.md`,
  `2026-05-30-workflow-document-project-spec.md`, `2026-05-29-agent-build-and-execution-spec.md`.
- **2 tool tests:** `tools/tests/test_workflow_design_visualize_skill.py`,
  `tools/tests/test_workflow_document_project_skill.py`.

Net: 137 files changed, ~11k deletions. 6 skills remain: `dev-workflow-init`,
`prompt-engineering-author`, `prompt-engineering-improve`, `prompt-evals-{setup,create-dataset,run}`.

## References scrubbed in living files
- **README.md** — lifecycle (`Author → measure → improve`), skill table, spec links, intro all rewritten.
- **AGENTS.md** — test block trimmed to the surviving suites; removed the agent-build-scaffold bash note.
- **CONTRIBUTING.md** — group-verb naming list, the "mirror validate_blueprint" pointer (→ `improve_step.py`), and the validator-tests block (→ improve-loop helper tests).
- **`.claude-plugin/plugin.json` + `marketplace.json`** — descriptions rewritten; blueprint/workflow/agent-build/visualize keywords dropped.
- **Kept-skill prose** — `prompt-engineering-author` (SKILL.md + anti-patterns.md + techniques.md) and `dev-workflow-init/SKILL.md`: `workflow-design-*`/`agent-build-*` mentions reworded to generic "orchestrated multi-step workflow"; dangling "Mirrors workflow-design-validate" comments removed from `tools/skill_lint.py` and `improve_step.py`.

## Deliberately preserved as historical record
- **`.story/` history** (handovers/lessons/completed tickets T-002/009/010/011/016/025) — durable; left as-is per AGENTS.md ("mark complete, never delete").
- **`2026-05-29-prompt-engineering-skills-design.md`** — a dated, approved design contract for the **kept** prompt-engineering skills. Rather than rewrite an approved record into fiction, it carries a **`⚠️ Superseded context (T-031)`** banner flagging that its `workflow-design-*`/`agent-build-*`/blueprint mentions are historical out-of-plugin context; the one broken markdown link to the deleted architecture spec was neutralised to plain text + "removed in T-031".

## Plan
None. Mechanical deletion + reference scrub — no `docs/superpowers/plans/` scratchpad was created (nothing to delete before merge).

## Verification
`skill_lint` **6 skills / 0 errors / 0 warnings**. All surviving offline suites green: tools/tests (14), eval framework (OK), dev-workflow-init (15), prompt-engineering-improve (OK). `graphify update` rebuilt the graph (1279 nodes).

## Review (two independent rounds)
- **Cross-file tracer (Explore):** no surviving functional dependency from any kept file into a deleted skill/spec/module; no broken `${CLAUDE_PLUGIN_ROOT}` paths or markdown links in living docs.
- **skill-reviewer:** both edited kept skills valid and coherent; only an optional comma-splice polish at `prompt-engineering-author/SKILL.md` — applied.

## Follow-up
Version bump `0.5.0 → 0.6.0` (minor: pre-1.0 removal of user-visible capability) as a direct commit to `main` after merge, per AGENTS.md.
