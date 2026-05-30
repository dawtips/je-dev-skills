# Eval Live-Path Integration Handover

## Summary

Completed Story tickets `T-013`, `T-014`, and `T-019` for the prompt eval live path.

The branch wires the existing deterministic eval cores into the live/report workflow without
editing `evaluator/evaluator.py`, `evaluator/grade.py`, `evaluator/run.py`, or eval prompts:

- `T-013`: adds report-analyst baseline delta and variance sections, with explicit
  `--baseline-output` and repeatable `--variance-output` inputs.
- `T-014`: adds `assertion_gate.py` and `live_run.py` so keyed live runs evaluate
  structural assertions before judge grading, persist assertion evidence, and skip the
  judge only for gated mandatory failures.
- `T-019`: adds explicit K-run variance orchestration with labels of the form
  `<group_label>__kNN`, validates CLI inputs, and calls the existing variance core.

Final review found that report rendering exposed aggregate analysis but dropped per-case
delta/variance details. Commit `f912869` fixed this by rendering the existing `per_case`
analysis rows and adding report-analyst tests for Markdown and escaped HTML output.

## Files Changed

- `.story/tickets/T-013.json`
- `.story/tickets/T-014.json`
- `.story/tickets/T-019.json`
- `.story/handovers/2026-05-30-05-eval-live-path-integration.md`
- `.story/lessons/L-002.json`
- `docs/superpowers/specs/PROMPT_EVAL_FRAMEWORK_SPEC.md`
- `docs/superpowers/plans/2026-05-30-t013-t014-t019-eval-live-path-integration.md` deleted
- `skills/prompt-evals-run/SKILL.md`
- `skills/prompt-evals-setup/framework/evals/aggregate.py`
- `skills/prompt-evals-setup/framework/evals/assertion_gate.py`
- `skills/prompt-evals-setup/framework/evals/evaluator/report.py`
- `skills/prompt-evals-setup/framework/evals/examples/smoke_test.py`
- `skills/prompt-evals-setup/framework/evals/live_run.py`
- `skills/prompt-evals-setup/framework/evals/report_analyst.py`
- `skills/prompt-evals-setup/framework/evals/run_eval.py`
- `skills/prompt-evals-setup/framework/evals/variance_runner.py`
- eval framework tests covering aggregate/report/assertion/live-run/run-eval/variance behavior

## Verification

Fresh verification before this handover:

- `python3 tools/skill_lint.py --root .` -> `11 skills | 0 errors | 0 warnings`
- `python3 -m unittest discover -s tools/tests -t tools` -> 8 tests OK
- `(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)` -> 98 tests OK
- `python3 -m unittest discover -s skills/workflow-design-validate/scripts/tests -t skills/workflow-design-validate/scripts` -> 29 tests OK
- `(cd skills/prompt-evals-setup/framework && python3 -m evals.examples.smoke_test)` -> `SMOKE TEST: PASS`
- prohibited core diff check for `evaluator/evaluator.py`, `evaluator/grade.py`, `evaluator/run.py`, and eval prompts -> no output
- `git diff --check` -> clean

## Notes

Ephemeral plan deleted as part of the closeout:
`docs/superpowers/plans/2026-05-30-t013-t014-t019-eval-live-path-integration.md`.

The durable design contract is `docs/superpowers/specs/2026-05-30-eval-live-path-integration-spec.md`;
the implementation summary and verification evidence live in this handover.
