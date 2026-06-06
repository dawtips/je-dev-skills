# Session 2026-05-31 - T-024 no-key create-dataset

## Summary

Shipped T-024: `/je-dev-skills:prompt-evals-create-dataset` now documents a default
interactive, no-key Path A for freezing real project datasets, while preserving the keyed
`generate-artifact` Path B for headless/CI.

This closes the gap where `prompt-evals-run` could execute without a project API key, but
`prompt-evals-create-dataset` still said real datasets categorically required
`ANTHROPIC_API_KEY`.

## Key changes

- `skills/prompt-evals-create-dataset/SKILL.md` now has:
  - Path A (`no API key, default`) for in-session dataset authoring;
  - Path B (`keyed fallback`) for SDK-backed `generate-artifact`;
  - a provenance contract for `generator_model: "interactive_session"` and
    `generation_mode: "in_session_no_key"`;
  - a deterministic shape guard that resolves `cases_file` from `eval.json`, validates
    provenance, validates per-case `task_description` and `scenario`, checks exact
    `prompt_inputs` keys, rejects whitespace-only criteria, and enforces an ISO-8601 UTC
    `created_at`.
- `docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`
  now records that `cases.json` can be frozen either by default no-key interactive
  authoring or by keyed `generate-artifact`.
- `.story/tickets/T-024.json` is complete.

No generated `cases.json` examples were added.

## Verification (actual output, from repo root)

Ran red structural checks first; both exited `1` before implementation:

- `rg -n "Path A .*no-key interactive|Path B .*keyed|interactive_session" skills/prompt-evals-create-dataset/SKILL.md`
- `rg -n 'interactive session generates cases|generate-artifact remains the keyed' docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`

Targeted post-fix checks:

- `rg -n "Path A .*no API key|Path B .*keyed|interactive_session|generation_mode" skills/prompt-evals-create-dataset/SKILL.md` printed the Path A/Path B and provenance lines.
- `rg -n 'generation_mode: in_session_no_key|keyed \`generate-artifact\`' docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md` printed the spec lines.
- Temp-project simulation with custom `cases_file: custom-cases.json` resolved that path and printed `dataset shape ok`.

Full offline suite after review fixes:

- `python3 tools/skill_lint.py --root .` -> `13 skills | 0 errors | 0 warnings`
- `python3 -m unittest discover -s tools/tests -t tools` -> `Ran 17 tests ... OK`
- prompt-evals framework -> `Ran 187 tests ... OK`
- `workflow-design-validate` -> `Ran 29 tests ... OK`
- `workflow-design-review` -> `Ran 50 tests ... OK`
- `workflow-design-advise` -> `Ran 64 tests ... OK`
- `workflow-document-project` -> `Ran 29 tests ... OK`

Several suites intentionally print negative-fixture `ERROR`/`FAIL` text while still exiting
0 and ending in `OK`; that matched the baseline behavior.

## Reviews

Two independent review rounds ran:

- Spec-compliance review found no Critical or Important issues.
- Skill-usability review found three valid contract gaps:
  - Path A shape check did not require per-case `task_description` or `scenario`;
  - Path A provenance was documented but not validated;
  - `$CASES` could diverge from a custom `cases_file` in `eval.json`.

All three were fixed. The same reviewer re-checked the fixes, then flagged two low-level
guard gaps (ISO timestamp parseability and whitespace-only criteria), which were also
fixed. Final focused re-review found no remaining findings.

## Plan deletion

Deleted ephemeral plan `docs/superpowers/plans/2026-05-31-T-024-no-key-create-dataset.md`
before merge. Its durable residue is this handover, the completed ticket, and the updated
architecture spec.
