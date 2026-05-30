# Workflow Design Review Plan Handover

## Summary

Completed the planning ticket for the workflow-design semantic review work and prepared the next implementation ticket.

Completed Story ticket:
- `T-010` Write plan for workflow-design semantic review

Updated next ticket:
- `T-011` Build workflow-design-review skill is now open and unblocked. Its description points at the approved plan: `docs/superpowers/plans/2026-05-30-workflow-design-review.md`.

## Key Changes

- Added `docs/superpowers/plans/2026-05-30-workflow-design-review.md`.
- Marked `T-010` complete.
- Updated `T-011` to remove the stale `T-010` blocker and reference the new implementation plan.
- Committed the plan work as `35d47c3 Write workflow-design-review implementation plan`.

## Plan Review Notes

The T-010 plan was reviewed with Story review lenses: clean-code, security, error-handling, and performance.

Actionable feedback was folded into the plan before completion:
- Explicit local complexity boundary for `review_blueprint.py`, including a 500-line extraction checkpoint.
- `DIMENSIONS` declared as the code-side contract, with tests requiring rubric text to mention each dimension name/title.
- Safer shell invocation using a quoted `BLUEPRINT_PATH` variable and `--`.
- Prompt-injection boundary using explicit untrusted-data wording and JSON-encoded blueprint content instead of Markdown fencing.
- Data handling warning that real reviews send the full blueprint to Anthropic.
- Explicit `.blueprint.md` file validation and documented overwrite behavior for `.review.md`.
- Input-size guard via `WORKFLOW_REVIEW_MAX_INPUT_CHARS`.
- Lower output cap and schema constraints for concise reasoning/suggestions.
- Client creation after local blueprint/rubric validation.
- Expanded negative-path tests for invalid/non-mapping YAML, zero/multiple glob matches, malformed tool envelopes, missing package, judge failures, report write failures, and threshold boundaries.
- Default model changed to a strong Sonnet-tier path with Opus documented as opt-in for complex/high-stakes reviews.

## Verification

Fresh checks run during the planning session:
- `python3 tools/skill_lint.py --root .` -> `7 skills | 0 errors | 0 warnings`
- `cd tools && python3 -m unittest discover -s tests -v` -> 7 tests OK
- `cd skills/workflow-design-validate/scripts && python3 -m unittest discover -s tests -v` -> 29 tests OK
- `git diff --check -- .story/tickets/T-010.json docs/superpowers/plans/2026-05-30-workflow-design-review.md` -> clean before the T-010 commit
- `storybloq validate` -> 0 errors, 0 warnings

A snapshot was saved before this handover: `2026-05-30T06-48-47-985.json`.

## Current State

- Story status after `T-010`: 8/18 tickets complete, 1 blocked.
- Remaining true blocked ticket: `T-009`, blocked by open `T-008`.
- `T-011` is ready to implement next.
- Worktree still has the pre-existing untracked `workflows/` directory; leave it untouched unless explicitly asked.

## Recommended Next Work

If continuing Review Layers, implement `T-011` using `docs/superpowers/plans/2026-05-30-workflow-design-review.md` task-by-task.

If continuing phase order from the broader roadmap, `T-008` remains the Agent Build + Substrate candidate and still blocks `T-009`.
