---
name: workflow-design-advise
description: This skill should be used when the user asks to "recommend models for my workflow", "which Claude model and effort per agentic step", "audit blueprint model/effort choices", "is my subagent over-provisioned", or right after workflow-design-validate passes. It runs a deterministic Claude model+effort advisor over ./workflows/<name>.blueprint.md and reports recommended tiers with rationale.
argument-hint: "[path to the blueprint; defaults to ./workflows/*.blueprint.md]"
allowed-tools: Bash, Read, Edit, Glob
version: 0.1.0
---

# Workflow Design: Advise (model + effort)

Run a deterministic model-selection advisor over a workflow blueprint. It reads
the single fenced `yaml` block of `<name>.blueprint.md` and recommends a Claude
**tier** (`haiku`/`sonnet`/`opus`) and **effort** for every agentic step and
subagent, applying the routing and effort-scaling rules in
`workflow-design-interview/references/model-selection.md`. It is offline and
deterministic — no API key, no model call. Genuine judgment (a subagent's task
difficulty) is surfaced as a review flag, never guessed.

## Precondition

A blueprint must exist (written by `workflow-design-interview` to
`./workflows/<name>.blueprint.md`). If the user passed a path, use it; otherwise
Glob `./workflows/*.blueprint.md`. If none exists, stop and point the user at
`workflow-design-interview`. Run this **after** `workflow-design-validate`
passes — advice on an incomplete blueprint is premature.

## Procedure

1. **Install deps once** (idempotent):

   ```bash
   pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-advise/scripts/requirements.txt
   ```

2. **Run the advisor** against the blueprint path:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-advise/scripts/advise_model.py <path> --date <YYYY-MM-DD>
   ```

   Exit codes: `0` = report produced, `2` = file unreadable, not exactly one
   fenced `yaml` block, or a malformed `steps`/`subagents` entry. Add `--strict`
   to exit `1` when any subagent's current `model`/`effort` disagrees with the
   advice (useful as a gate). Add `--json` for machine-readable output (no
   `--date` needed). Add `--budget high` when the workflow is cost/token
   constrained — it caps effort at `medium` to bound the ~15× multiplier (the
   guideline's cost-minimization input; supply it yourself rather than have the
   tool guess from prose).

3. **Read the report.** A table of `Target | Kind | Recommended | Effort |
   Current | Agree | Review`, then a per-target rationale. `Agree = NO` marks an
   over- or under-provisioned subagent; `Review = !` means the advisor assumed
   the task difficulty and a human should confirm it.

4. **Apply accepted recommendations** with the Edit tool:
   - **Subagents** — update `subagents[i].model` and `subagents[i].effort` in
     the `yaml` block to the recommended tier/effort when you agree. Confirm any
     `Review = !` difficulty first; leave `model: inherit` in place unless you
     have a reason to pin a tier.
   - **Agentic steps** — these have **no** `model`/`effort` field in the schema,
     so step recommendations are **advisory**: record the chosen model/effort in
     the step's prose `rationale`, do **not** add a `model` field to a step.

5. **Re-validate.** Run `workflow-design-validate` again to confirm the edited
   `yaml` block still passes.

## Definition of done

Every subagent's `model`/`effort` is either confirmed to agree with the advice
or deliberately overridden with a recorded reason, and any `Review = !` items
have had their difficulty confirmed by a human.

## Notes

- **Deterministic and advisory.** Same input → same output. The advisor encodes
  the v0.1 guideline; it does not replace human judgment on a subagent's
  difficulty (flagged for review). It ties effort to task breadth and tier to
  difficulty/role, so the guideline's "independent dials" cases (a Haiku worker
  at medium effort, an Opus orchestrator at low effort) are a human override,
  not auto-produced.
- **Gated feature.** Per `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md`
  §2.4 this is a "maybe-never" tool — build/use it only when the by-hand
  guideline proves insufficient. Claude models only.
- **Tiers, not IDs.** Blueprints store a tier; concrete model IDs live in one
  constant in `advise_model.py`, re-verified against the volatile-values table
  in `${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-interview/references/citations.md`.
