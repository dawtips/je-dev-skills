# Session 2026-05-31 - T-023 workflow-document-project

## Summary

Shipped `workflow-document-project`, a project-first workflow-design entry point that
inventories an existing project, synthesizes a draft workflow blueprint from evidence, and
writes a companion project-documentation report with actionable feedback. It is an alternate
entry to `workflow-design-interview` (idea-first). The blueprint always stays `status: draft`.

The spec was reviewed first (a multi-agent adversarial pass produced prioritized findings),
the spec/plan were corrected, then the plan was executed to build the skill.

## Key changes

- `skills/workflow-document-project/SKILL.md` — procedural UX; Path A (in-session, default,
  no API key) and Path B (`synthesize --mode anthropic_api`, keyed, headless/CI).
- `skills/workflow-document-project/scripts/document_project.py` — deterministic core:
  conservative file inventory + classification; secret/cache exclusion (case-insensitive,
  `evals/runs` at any depth); excerpt redaction (assignment forms incl. JSON-quoted keys and
  underscore-joined names, provider key prefixes, entropy/key-shape masking that preserves
  SHAs/UUIDs/identifiers); fail-closed synthesis-payload parser (enforces prose/report
  substructure, `status: draft`); blueprint + project-doc rendering; in-process
  `workflow-design-validate` so the report records a real `validation:` result; validated-
  overwrite guard (`--force`); Path B `MAX_INPUT_CHARS` cap; CLI accepts fenced-or-raw JSON.
- `references/exclusions.md`, `references/synthesis-prompt.md` — redaction contract and the
  shared synthesis prompt (full payload substructure spelled out).
- Offline tests: `scripts/tests/{test_inventory,test_synthesis,test_blueprint,test_report,
  test_cli}.py` + `fake_client.py` + fixture project (29 tests). `tools/tests/
  test_workflow_document_project_skill.py` (skill shell + metadata).
- README lifecycle/table + spec link; `.claude-plugin/plugin.json` keywords; `AGENTS.md`
  `## Tests` block now lists the new suite (and the previously-missing `workflow-design-review`
  suite).
- Spec `docs/superpowers/specs/2026-05-30-workflow-document-project-spec.md` updated to match
  the implemented contract (two-path selection, payload substructure §6.3, Path B cap,
  validated-overwrite guard §7, real validation status §8).

## Verification (actual output, from repo root)

All run green on the feature branch and again on `main` after merge:

- `python3 tools/skill_lint.py --root .` → `13 skills | 0 errors | 0 warnings`
- `python3 -m unittest discover -s tools/tests -t tools` → `Ran 17 tests ... OK`
- prompt-evals framework → `Ran 187 tests ... OK`
- `workflow-design-validate` → `Ran 29 ... OK`; `workflow-design-review` → `Ran 50 ... OK`;
  `workflow-design-advise` → `Ran 64 ... OK`
- `workflow-document-project` → `Ran 29 tests ... OK`

The generated fixture blueprint passes the real `workflow-design-validate` 12/12 and stays
`status: draft` (`test_blueprint.py` asserts against the actual validator module, not a mock).

## Reviews

Two independent adversarial review rounds (round 1 correctness/spec; round 2 tests/robustness)
ran over the implementation. Both returned **fix-first**; all valid findings were addressed and
committed in `fix(T-023): address review findings`:

- **CRITICAL (fixed):** redactor missed JSON-quoted-key secrets (`"token": "npm_…"`) — a real
  Path B egress hole; added an optional quote before the `[:=]` separator + a test.
- **IMPORTANT (fixed):** parser did not type-check `report_sections.inferences`/`feedback`, so a
  string rendered character-by-character; now both are list-validated + tests.
- **IMPORTANT (fixed):** test gaps — vacuous `.env` assertion and redaction untested through the
  `rglob` walk; multiple-blueprint detection untested; report inference/open-question merge
  unasserted; Path B CLI glue untested. Added end-to-end exclusion/redaction tests, a
  multi-blueprint test, stronger report assertions, a `run_synthesize` fake-client test.
- **MINOR (fixed):** duplicate `import importlib.util`.
- **Declined, with reason:** (a) greedy assignment-value capture — bounding to `\S+` would
  *leak* `Authorization: Bearer <token>` and space-bearing secrets; over-redacting the rest of a
  secret-bearing line is the safe direction. (b) rejecting empty `open_questions` — a project
  that proves every field can legitimately have none. (c) `validation: not run` fallback — an
  intentional degraded path when the validator module is unreachable.

## Notable techniques / lessons

See `.story/lessons/` entry from this session: verify a plan's *embedded* deterministic code by
extracting and running it against the real dependency before trusting it; and redaction must
cover JSON-quoted-key secrets, not just `k=v` / `k: v`.

## Plan deletion

Deleted ephemeral plan `docs/superpowers/plans/2026-05-31-t023-workflow-document-project.md`;
its durable residue is this handover, the lesson, and the updated spec. The plan's embedded
code was verified (extracted + run against the real validator) before the skill was built.
