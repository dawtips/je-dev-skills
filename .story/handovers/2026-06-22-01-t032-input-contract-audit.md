# Handover — T-032: generation-time input-contract audit in create-dataset

**Date:** 2026-06-22
**Ticket:** T-032 (complete) · **Phase:** eval-hardening
**Branch:** `feat/T-032-input-contract-audit` → merged to `main`, branch deleted
**Plan (deleted before merge):** `docs/superpowers/plans/2026-06-22-T-032-input-contract-audit.md`

## What happened

Applied the cross-repo half of presales-sqnce **#115**. The deterministic enforcement
(runtime `invalidPromptInputs` preflight + `eval-fixtures` drift guard) shipped in
presales-sqnce **PR #116** (merged). The complementary *generation-time* guard belongs in
this repo's create-dataset skill so violating cases are never frozen.

The change could not be pushed from the presales Codespace (token scoped to presales-sqnce →
403 on je-dev-skills). The author recorded the exact patch + apply instructions as a comment
on PR #116. Applied it here verbatim.

### Change
- `skills/prompt-evals-create-dataset/SKILL.md` §5 — new **"Input-contract audit"** subsection
  (+19 lines) inserted between the `exit 1/2` hand-off line and the `cases.json` spot-check
  paragraph. Teaches: when `prompt_inputs` stand in for upstream outputs that declare
  validators, run the project's input-contract check before freezing and refuse to freeze a
  violating case (regenerate valid-by-construction). Documents presales' `eval-fixtures` drift
  guard as the concrete instance; validator-less projects skip the audit.

### Verification (actual output)
- `skill_lint.py` → `6 skills | 0 errors | 0 warnings`
- `tools/tests` → Ran 14, OK
- evals framework → Ran 215, OK
- dev-workflow-init → Ran 15, OK
- prompt-engineering-improve → Ran 53, OK

(The change is docs-only; no deterministic core to add here — the enforcement code lives in
presales-sqnce. The patch was already reviewed upstream: spec + plan Codex loops + adversarial,
pre-PR code review 0 MED+. No separate in-repo review round was run for this verbatim doc insert.)

## Also done this session
- **Branch cleanup:** deleted 4 superseded/obsolete branches (local + remote) so only `main`
  remains — `feat/11-cmd-adapter-render` (command_adapter render already in main via PR #12),
  `claude/dev-workflow-init` and `claude/modest-allen-mRHAU` (skill / AGENTS.md already in main),
  `feat/interactive-viewer-spec` (spec for the blueprint ecosystem T-031 removed).

## Follow-ups
- presales-sqnce **#109** lands the fixture regeneration + standing drift guard + graded
  re-baseline that this generation-time step points at. Close presales #115/#37 once #109 lands.

## Lesson
- L-014 — cross-repo change you can't push: leave a self-contained, apply-able handoff.
