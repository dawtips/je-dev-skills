# Working agreement (AGENTS.md/CLAUDE.md) + plan cleanup

## Summary

Established a unified working agreement that combines the two methodologies used to build
this repo — **superpowers** (the spec → plan → implement → adversarially-verify method) and
**storybloq** (`.story/` durable memory: roadmap, tickets, handovers, lessons) — and applied
the new "delete plans on merge" rule retroactively.

## Key changes

- Added `AGENTS.md`: the canonical, tool-neutral working agreement (Codex reads it directly).
  Encodes the combined loop, the durable-vs-ephemeral artifact table, hard rules, and an
  explicit "Deleting plans once implemented" procedure.
- Added `CLAUDE.md`: thin Claude Code entry point that imports `AGENTS.md` via `@AGENTS.md`
  and adds Claude-Code-only notes (`${CLAUDE_PLUGIN_ROOT}`, companion plugins, verify-before-done).
- Resolved the superpowers/storybloq overlap with one rule: **specs are durable, plans are
  disposable, handovers are the single narrative of record.**

## Plans deleted (all tickets complete; narratives preserved in earlier handovers)

- `docs/superpowers/plans/2026-05-29-agent-build-group.md` (T-009)
- `docs/superpowers/plans/2026-05-29-eval-framework-hardening.md` (T-003)
- `docs/superpowers/plans/2026-05-29-in-cc-execution-substrate.md` (T-008)
- `docs/superpowers/plans/2026-05-29-prompt-engineering-skills.md` (T-006, T-007)
- `docs/superpowers/plans/2026-05-29-workflow-design-skills-v0.1.md` (T-002)
- `docs/superpowers/plans/2026-05-30-workflow-design-review.md` (T-010, T-011)

The two durable specs under `docs/superpowers/specs/` were kept. `docs/superpowers/plans/`
is retained (with `.gitkeep`) as the home for future ephemeral plans.

## Notes

- Paths in `AGENTS.md` intentionally point at the existing `docs/superpowers/{specs,plans}`
  layout rather than restructuring to `docs/{specs,plans}`.
- Going forward: a plan with `Status: Complete` sitting in `docs/superpowers/plans/` is a bug
  — distill its residue into the spec/handover/lesson and `git rm` it on merge.
