# In-Claude-Code Execution Substrate Handover

## Summary

Implemented the full in-Claude-Code execution substrate plan on branch `in-cc-execution-substrate` in worktree `/home/dawti/.config/superpowers/worktrees/je-dev-skills/in-cc-execution-substrate`.

Completed Story ticket:
- `T-008` Build in-Claude-Code execution substrate

## Key Changes

- Added `EXECUTION_MODE` and Path A subagent dispatch knobs in `skills/prompt-evals-setup/framework/evals/config.py`.
- Added deterministic prompt-prep glue in `evals/promptprep.py` with offline tests.
- Added deterministic no-model report assembly in `evals/aggregate.py`, including verdict fixtures and tests.
- Made `evals/run_eval.py` file-backed, render-based, and mode-aware while preserving the existing `LOOP_PARAMS` block owned by prompt-engineering-improve.
- Rewrote `skills/prompt-evals-run/SKILL.md` so the canonical Path A uses interactive execute/grade subagent dispatch plus `aggregate.py`, with keyed `anthropic_api` retained as fallback.
- Updated `skills/prompt-evals-setup/SKILL.md` so fresh vendoring includes `aggregate.py`/`promptprep.py`, and existing installs use a non-clobbering substrate update.

## Review Fixes Applied

Two review rounds were run with subagents.

Initial review findings addressed:
- `aggregate.py` now records actual `EXTRA_CRITERIA` in `meta.extra_criteria`, defaulting from `evals.run_eval.EXTRA_CRITERIA` or accepting `--extra-criteria`.
- `aggregate.py --dataset` now validates verdict count and each verdict `test_case` against the dataset `cases`, rejecting stale/missing/wrong verdict files.
- Setup docs no longer tell agents to stop when `./evals` exists; they route through the non-clobbering substrate update.
- Subagent defaults now match the plan: `claude-haiku-4-5-20251001` executor and `medium` effort.
- `run_eval.LOOP_PARAMS` was restored and preserved.

Final independent review found no blocking issues.

## Verification

Fresh verification on the final branch head:
- `cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .` -> 69 tests OK.
- `cd skills/prompt-evals-setup/framework && python3 -m evals.examples.smoke_test` -> `SMOKE TEST: PASS`.
- `cd skills/workflow-design-validate/scripts && python3 -m unittest discover -s tests -v` -> 29 tests OK.
- `cd tools && python3 -m unittest discover -s tests -v` -> 7 tests OK.
- `python3 tools/skill_lint.py --root .` -> `7 skills | 0 errors | 0 warnings`.
- `git diff --name-only main -- skills/prompt-evals-setup/framework/evals/evaluator skills/prompt-evals-setup/framework/evals/prompts` -> empty; framework core unchanged.
- `git diff --check main...HEAD` -> clean.
- Keyed fallback monkeypatch sanity -> `keyed-path-routes-OK`.

A snapshot was saved before this handover: `2026-05-30T08-15-34-789.json`.

## Current State

- Branch: `in-cc-execution-substrate`.
- Worktree: `/home/dawti/.config/superpowers/worktrees/je-dev-skills/in-cc-execution-substrate`.
- `T-008` is complete in Story data.
- The branch is ready to push.
- The original checkout `/home/dawti/je-dev-skills` still has its pre-existing untracked `workflows/` directory and was not modified.

## Residual Risk

- Path A's actual Task/subagent orchestration is an interactive behavior and remains a manual acceptance scenario; the deterministic aggregation and keyed fallback are covered by tests.
- Existing project installs require the documented manual merge for user-editable `config.py` and `run_eval.py` if those files predate the substrate.

## Recommended Next Work

- `T-009` agent-build-scaffold + agent-build-run can proceed now that the substrate work is complete.
- `T-018` may revisit the broader prompt-evals architecture if the project wants plugin-resident eval machinery rather than vendoring framework code into target projects.
