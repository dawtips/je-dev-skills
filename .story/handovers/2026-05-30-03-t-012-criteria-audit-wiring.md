# T-012 Criteria Audit Wiring Handover

## Summary

Completed Story ticket `T-012`: Wire `criteria_audit.py` into `prompt-evals-create-dataset`.

The `prompt-evals-create-dataset` skill now requires the deterministic dataset audit command after generating a frozen dataset:

```bash
python3 -m evals.criteria_audit evals/datasets/<name>.json
```

The skill documents how to handle audit exit codes:
- `0`: clean audit, continue with human spot-check.
- `1`: criteria/scenario findings, edit or regenerate and rerun until clean.
- `2`: unreadable input/setup error, fix before continuing.

It also blocks handoff to `prompt-evals-run` while the audit exits `1` or `2`, and its Definition of Done now requires the audit to exit `0`.

## Files Changed

- `skills/prompt-evals-create-dataset/SKILL.md`
- `tools/tests/test_prompt_evals_create_dataset_skill.py`
- `.story/tickets/T-012.json`

## Verification

Fresh verification before this handover:
- `python3 -m unittest discover -s tools/tests -v` -> 8 tests OK
- `python3 tools/skill_lint.py --root .` -> `10 skills | 0 errors | 0 warnings`
- `storybloq_validate` -> 0 errors, 0 warnings
- `git diff --check` -> clean

Snapshot saved before this handover: `2026-05-30T18-17-05-686.json`.

## Notes

The pre-existing untracked `workflows/` directory remains untouched and should not be included in the T-012 commit.

The next related open ticket is `T-013`: surface `variance` and `run_delta` in `prompt-evals-run` reporting.