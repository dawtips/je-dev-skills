# Session 2026-05-31 — T-016 workflow-design-visualize (visual viewer, Tier 1)

## Summary

Shipped `workflow-design-visualize`, the §9 visual-viewer **Tier 1**: a deterministic
`yaml`→Mermaid generator that renders a validated blueprint as a sibling
`<name>.diagram.md` (a `flowchart` of the steps in list order + per-step / per-subagent
drill-down tables). Tier 2 (interactive browser viewer) stays gated per the
advanced-tooling spec §3.4 and was **not** built. Offline, deterministic, no API key,
no model call.

## Key changes

- `skills/workflow-design-visualize/SKILL.md` — procedural shell (`allowed-tools: Bash,
  Read, Glob`); precondition "run after `workflow-design-validate` passes"; documents the
  run command, exit codes (0/2), `--stdout`/`--out`, and how to view Mermaid (GitHub
  native / VS Code + extension / mermaid.live).
- `skills/workflow-design-visualize/scripts/visualize_blueprint.py` — the deterministic
  core. Reuses the validator's single-fenced-`yaml`-block contract (exit 2 on bad input).
  Encoding maps one-to-one to schema fields, no inference: **edges = `steps` list order**;
  `kind`→color+shape+label-text (deterministic=rectangle, agentic=rounded, missing/unknown
  =gray rectangle labeled `unspecified`); `pattern`→`· <pattern>` label tag when not
  `none`; `approval_gate`→hexagon node **after** the step; `subagents`→separate `subgraph`
  with **no fabricated step→subagent edges**. Mermaid-safe node ids (slugify, dedupe,
  no-leading-digit, **reserved-keyword guard** → `n_end` etc.), label + table-cell
  escaping, no timestamp (byte-stable). CLI writes the sibling artifact.
- `scripts/requirements.txt` (PyYAML), `scripts/tests/` — 48 offline `unittest` tests
  (golden Mermaid for `minimal`/`multi`, dup-id + escaping, gate placement, determinism
  incl. a cross-process `PYTHONHASHSEED` check, tables, CLI, edge cases) + fixtures.
- `tools/tests/test_workflow_design_visualize_skill.py` — skill-shell + repo-metadata test.
- Repo integration: README group row (adds `visualize`), `.claude-plugin/plugin.json`
  keywords (`mermaid`, `diagram`, `visualization`), `AGENTS.md` `## Tests` block,
  `WORKFLOW_DESIGN_SPEC.md` §9 (Tier 1 marked shipped), advanced-tooling spec §3.6 (the
  build contract) + §4/§5 reconciled to "Tier 2 stays deferred; Tier-1 forms shipped".

## Verification (actual output, worktree then to be re-run on main)

- `python3 tools/skill_lint.py --root .` → `14 skills | 0 errors | 0 warnings`
- `tools/tests` → `Ran 21 tests ... OK`
- prompt-evals framework → `Ran 187 ... OK`
- workflow-design-validate `29 OK`; -review `50 OK`; -advise `64 OK`;
  workflow-document-project `29 OK`
- **workflow-design-visualize → `Ran 48 tests ... OK`**

## Reviews

Two independent rounds, both addressed:

1. **Per-unit spec + code-quality** (subagent-driven). Unit A (core module): all §3.6
   encoding rules verified in code; fixed an `sg_subagents` subgraph-id collision, `_cell`
   whitespace handling, non-dict-row consistency, and added a cross-process determinism
   test + a mid-flow gate golden. Unit B (skill + integration): spec-compliant; clarified
   the "Wrote <output path>" doc line and tightened two skill-test assertions.
2. **Adversarial multi-lens Workflow** (5 lenses → per-finding verification, 11 confirmed
   / 0 refuted). One real correctness bug + cheap fidelity/coverage/doc fixes — all
   applied in `ba64d82`:
   - **Mermaid reserved-keyword node ids** (e.g. `id: end`) produced an unrenderable
     diagram — verified end-to-end against Mermaid v11.15.0's real parser. Fixed with a
     `MERMAID_RESERVED` guard (`end`→`n_end`) + tests. (See the lesson from this session.)
   - `_cell` now escapes `& < > \`` so drill-down tables render HTML-like field values
     faithfully; captions disclose the `unspecified` kind and conditional pattern tag;
     stale "both stay deferred/open" spec lines reconciled; added tests for the
     unspecified/unknown kind, subagent model/effort label variants, empty-pattern
     suppression, `--out` content, and the missing-file `ERROR` line.

## Plan deletion

Deleted the ephemeral plan `docs/superpowers/plans/2026-05-31-T-016-workflow-design-visualize.md`
before merge (AGENTS.md hard rule). Its durable residue is this handover, the lesson, and
the advanced-tooling spec §3.6.

## Notes

- The interview/validate schema (`<slug>` step ids) does not exclude `end`/`subgraph`/etc.,
  so the reserved-keyword guard is load-bearing, not theoretical.
- The adversarial round used the **real Mermaid parser** (jsdom) to prove the bug — code
  reading alone (round 1) missed it. Tool-grounded verification earned its keep.
