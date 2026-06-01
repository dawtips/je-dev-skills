---
name: workflow-design-visualize
description: This skill should be used when the user asks to "visualize my workflow", "render a blueprint diagram", "show a mermaid flowchart of my workflow", "draw the workflow steps", "see the workflow design as a picture", or right after workflow-design-validate passes and they want a diagram. It runs a deterministic yaml→Mermaid generator over ./workflows/<name>.blueprint.md and writes a <name>.diagram.md sibling with a flowchart and drill-down tables.
argument-hint: "[path to the blueprint; defaults to ./workflows/*.blueprint.md]"
allowed-tools: Bash, Read, Glob
version: 0.1.0
---

# Workflow Design: Visualize

Render a workflow blueprint to a Mermaid diagram. It reads the single fenced
`yaml` block of `<name>.blueprint.md` and writes a sibling `<name>.diagram.md`
holding a `flowchart` of the steps in **list order** — colored and shaped by
`kind` (rectangle = deterministic, rounded = agentic), with a `· <pattern>` tag
on each step, a hexagon `approval_gate` node after any gated step, and a separate
cluster for `subagents` — plus per-step and per-subagent drill-down tables. It is
offline and deterministic: no API key, no model call, no timestamp, so
regenerating produces byte-identical output.

## Precondition

A blueprint must exist (written by `workflow-design-interview` to
`./workflows/<name>.blueprint.md`). If the user passed a path, use it; otherwise
Glob `./workflows/*.blueprint.md`. If none exists, stop and point the user at
`workflow-design-interview`. Run this **after** `workflow-design-validate`
passes — a picture of an incomplete blueprint can mislead.

## Procedure

1. **Install deps once** (idempotent):

   ```bash
   pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-visualize/scripts/requirements.txt
   ```

2. **Run the generator** against the blueprint path:

   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-visualize/scripts/visualize_blueprint.py <path>
   ```

   It writes a sibling `<name>.diagram.md` and prints `Wrote <path>`. Exit codes:
   `0` = written, `2` = file unreadable or the blueprint has anything other than
   exactly one fenced `yaml` block. Add `--stdout` to print the artifact instead
   of writing it, or `--out <path>` to choose the output file.

3. **Show the result.** Read the generated `<name>.diagram.md` and tell the user
   where it is and how to view the flowchart: open it on GitHub (renders
   ` ```mermaid ` blocks natively), or in VS Code's Markdown preview with a
   Mermaid preview extension, or paste the `mermaid` block into mermaid.live. The
   drill-down tables are plain Markdown and render anywhere.

4. **Regenerate after edits.** The diagram is derived from the blueprint — after
   any change to the `yaml` block, re-run step 2. Do not hand-edit
   `<name>.diagram.md`.

## Definition of done

A sibling `<name>.diagram.md` exists next to the blueprint, contains one
`mermaid` flowchart that matches the blueprint's steps/subagents in list order,
and renders in a Mermaid-aware Markdown viewer.

## Notes

- **Deterministic and additive.** Same blueprint → byte-identical diagram. The
  generator only reads the v0.1 schema
  (`docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §4.1); it never edits the
  blueprint and never changes the schema.
- **Edges follow `steps` list order.** The v0.1 schema has no explicit
  `next`/`depends_on` field, so ordering is taken from the steps list (spec §7).
  Parallel fan-out is shown as a `· parallelize` tag, not as separate branches.
- **No fabricated subagent links.** Subagents render in their own cluster; the
  schema has no field tying a step to the subagent it delegates to, so no edges
  are drawn between steps and subagents.
- **Tier 1 of the visual viewer.** Per
  `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md` §3,
  this is the static-Mermaid tier; the interactive browser viewer (Tier 2) is
  gated and intentionally not built.
