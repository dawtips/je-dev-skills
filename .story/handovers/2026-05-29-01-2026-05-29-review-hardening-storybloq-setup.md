# Session 2026-05-29 — plugins review, eval hardening (WS1), skill-lint (WS4), spec reconciliation, storybloq setup

## Summary
Reviewed `anthropics/claude-plugins-official` against this plugin, reconciled the specs/plans with the findings, built two workstreams (eval-framework hardening + skill self-lint), expanded the workflow-design semantic-review design, and stood up storybloq to track all remaining work. Branch: `prompt-engineering-skills` (clean merge point).

## Decided / built
1. **Review outcome (T-005):** no official plugin *replaces* anything here; the value is pattern transfer (variance, baseline-delta, non-discriminating-criteria detection, plugin-dev agent-authoring reuse, math-olympiad context-isolated review). Added `CONTRIBUTING.md` (companion-plugin policy: install skill-creator/plugin-dev/pr-review-toolkit alongside, don't vendor; methodology-ownership line).
2. **WS1 eval hardening (T-003):** five offline, deterministic, tested modules at `skills/prompt-evals-setup/framework/evals/` — `runs_util`, `run_delta`, `variance`, `criteria_audit`, `assertions`. Full offline suite now 54 tests; smoke green; framework core untouched (composition invariant). Plan: `docs/superpowers/plans/2026-05-29-eval-framework-hardening.md`.
3. **WS4 skill-lint (T-004):** `tools/skill_lint.py` + tests, wired into `CONTRIBUTING.md`. Audit clean: 5 skills, 0 errors, 0 warnings.
4. **Spec reconciliation (T-005):** PROMPT_EVAL §13 marked *shipped* with module names; agent-build §3.5 + plan cite `plugin-dev` for subagent authoring; WORKFLOW_DESIGN §9.1 expanded into a buildable semantic-review design; prompt-engineering plan forward-note points `improve_step.py` at `run_delta.compute_delta` + `variance.suggested_regression_band`.

## Recommended next
**T-006 `prompt-engineering-author`** — standalone, eval-free, no deps; plan ready (`2026-05-29-prompt-engineering-skills.md` Tasks 11–14). Then **T-008 substrate** → unblocks T-007 (improve) and T-009 (agent-build).

## Conventions / gotchas
- Use `python3`, not `python`, on this environment.
- **Composition invariant:** never edit `evals/evaluator/*.py` or `evals/prompts/`; new framework code goes at the `evals/` top level. Verify with `git status` on those paths.
- Deterministic + offline-tested over prose; reserve the LLM for genuine judgment.
- Implementation plans in `docs/superpowers/plans/` are detailed TDD docs — read the plan AND its spec before coding.
- The untracked `workflows/` dir is a pre-existing test artifact — leave it alone.

## Coverage note
All active-scope work is specced + planned EXCEPT T-010 (workflow-design semantic review still needs its plan written from §9.1). Backlog (T-014..T-017) is intentionally deferred/YAGNI.
