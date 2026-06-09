# Workflow-Design Interactive Viewer (Tier 2) + Online Sketch (Tier 3) — Specification

A design contract for the **interactive browser viewer** of a workflow blueprint —
Tier 2 of the visual viewer first sketched in
[2026-05-30-workflow-design-advanced-tooling-spec.md](2026-05-30-workflow-design-advanced-tooling-spec.md)
§3. Tier 2 is **purely additive**: it reads the same locked v0.1 blueprint schema
(`WORKFLOW_DESIGN_SPEC.md` §4) the interview produces and the validator gates, and it
changes neither the schema nor any existing skill output.

> **Tickets covered:** [T-026] workflow-design interactive viewer (Tier 2), phase
> `backlog`, type `feature`. Related: [T-025] interview mid-point playback checkpoint
> (separate, small `workflow-design-interview` refinement; not part of the viewer).
>
> **Parent specs.** `WORKFLOW_DESIGN_SPEC.md` §9 owns the visual-viewer roadmap;
> `2026-05-30-workflow-design-advanced-tooling-spec.md` §3 holds the two-tier contract.
> This spec is the detailed Tier 2 contract those two defer to.

---

## 1. Gate decision — why this is being built now

The advanced-tooling spec §3.4 gates Tier 2 on "Tier 1 proving insufficient," and §4.4
requires that opening a deferred tier be **a recorded decision against evidence, not a
roadmap default**.

**Decision (2026-06-08):** the user opened the Tier 2 gate. Recorded here, exactly as
the shipped Tier-1 forms were recorded (advanced-tooling §2.6 advisor, §3.6 visualize).
The motivating evidence:

1. **Static drill-down does not scale to navigation.** Tier 1's `<name>.diagram.md`
   carries per-step and per-subagent tables, but on a blueprint with many steps,
   subagents, and 12 dimensions the reader scrolls a flat document. There is no way to
   click a node and see only its detail, filter to agentic steps, or follow a
   subagent reference. The information is present; the **navigation** is not.
2. **A working reference implementation exists**, which de-risks the build.
   `zhenya-vlasov/idea-finder` (MIT) ships exactly this shape: a deterministic Python
   renderer turns a structured Markdown document into inlined view data, and a small
   browser UI gives clickable drill-down, filtering, and cross-links (its network-to-
   roles graph). It is a parse-to-data-to-interactive-view pipeline over a single
   source document — the same pipeline a blueprint viewer needs.

**What we borrow and what we do not.** Borrow the **interaction patterns** (tab shell,
node → detail panel drill-down, a cross-reference cluster view) and re-implement them
against the v0.1 schema. Do **not** vendor idea-finder's code. Its `render.py` parses
free-form Markdown sections with regex and a stack of fragile fallbacks; our input is a
single validated `yaml` block, so we keep the clean extraction
`workflow-design-visualize` already has and feed the UI from that. This mirrors the
CONTRIBUTING rule for companion plugins: **borrow techniques, not code.**

---

## 2. What Tier 2 renders

Source of truth: the single fenced `yaml` block of `./workflows/<name>.blueprint.md` —
**no new authoring surface**. Tier 2 shows the same model Tier 1 draws, made navigable:

- **Flow view** — the steps in list order, colored and shaped by `kind` (deterministic
  vs agentic), pattern tag, and an `approval_gate` node after any gated step. Identical
  encoding rules to Tier 1 (advanced-tooling §3.6) so the two cannot disagree.
- **Click a node → detail panel** — for a step: `kind`, `rationale`, `pattern`,
  `side_effecting`, `reversible`, `termination`, and any `retry` / `rollback`. For a
  subagent: the four-part contract (`objective`, `output_format`, `tools`, `boundaries`)
  plus `model` / `effort`.
- **Dimension panel** — the 12 cross-cutting dimensions, each shown as `specified` or
  `{n/a: rationale}`, so a reader sees coverage at a glance (the same fact the validator
  gates on).
- **Filter / focus** — show only agentic steps, only side-effecting steps, only gated
  steps; isolate one subagent and its referencing step (by the detail table, not a
  fabricated edge — see §4).
- **Inputs / outputs / pre- and postconditions** — the contract header, readable without
  scrolling the raw file.

---

## 3. Delivery — self-contained HTML, no runtime

**Decision (2026-06-08):** Tier 2 ships as a **single self-contained HTML file**, not a
localhost server.

- The generator emits one sibling artifact, **`<name>.viewer.html`**, next to the
  blueprint (mirrors the `<name>.diagram.md` and `.review.md` sibling conventions).
- All view data is **inlined** into the file (a `<script>` data block), and the JS/CSS
  are inlined too. **No external network fetch at view time, no CDN, no server, no API
  key** — open it by double-click, offline. This keeps the plugin's no-runtime,
  offline-first north star that Tier 1 was built around; a localhost server (idea-
  finder's `serve.py` model) was considered and rejected for Tier 2 because it adds a
  running process and a port for no gain over an inlined file.
- **No timestamp, no randomness** in the output, so the same blueprint produces a
  byte-identical `<name>.viewer.html` and the artifact is diffable and versioned
  alongside the blueprint — the exact property that makes Tier 1 trustworthy.

---

## 4. Constraints (inherited from the Tier-1 contract)

1. **Additive, schema-stable.** Reads the v0.1 §4 schema only; emits a sibling artifact;
   never edits the blueprint and never changes the schema or the validator.
2. **Deterministic generation.** A pure schema → HTML transform: no model call, fully
   offline-testable (fixture blueprint → expected inlined data structure / golden HTML).
   Reuse the `yaml`-extraction and step/subagent model already in
   `skills/workflow-design-visualize/scripts/visualize_blueprint.py`; the Mermaid path
   and the HTML path share one parsed model so they cannot drift.
3. **Encoding maps one-to-one to schema fields — no inference.** Same rules as
   advanced-tooling §3.6: `kind` → color **and** shape **and** label text (color is never
   the only signal — accessibility); `pattern` → a tag; `approval_gate` → a gate node
   after the step; edges follow **`steps` list order** (the v0.1 schema has no
   `next`/`depends_on`).
4. **No fabricated subagent links.** The schema has no field tying a step to the subagent
   it delegates to. Subagents render in their own cluster; the relationship is carried by
   the detail panel and a caption, never by an invented edge.
5. **Self-contained and dependency-light.** Inline a minimal vanilla-JS/CSS view; do not
   pull a build toolchain or a runtime framework into the plugin. (idea-finder's React UI
   is the pattern reference, not a dependency to adopt.)

---

## 5. Skill home — extend `workflow-design-visualize`, do not add a skill

Tier 1 and Tier 2 are the **same feature** (the visual viewer) with two render targets.
Add an HTML output mode to the existing skill rather than a new `workflow-design-*`
member:

- `visualize_blueprint.py` gains a `--html` flag (and/or `--format html|mermaid`) that
  emits `<name>.viewer.html`; default output stays the Mermaid `<name>.diagram.md` so
  nothing changes for current users.
- The shared parsed model feeds both targets. Same exit codes as today (`0` written,
  `2` on the bad-input conditions: not exactly one fenced `yaml` block; block not a
  mapping).
- The SKILL.md gains a short Tier 2 section: when to emit the HTML viewer, how to open it
  (double-click the file), and that it is regenerated from the blueprint — never hand
  edited.

This keeps the group-verb naming clean and avoids a second skill that re-extracts the
same `yaml`.

---

## 6. Phasing — read-only first, then write, then drive

Per the 2026-06-08 scoping decision, Tier 2 lands in phases; only Phase A is in scope now.

- **Phase A — navigate and drill down (in scope, T-026).** Read-only. Click, filter,
  follow cross-links. The `yaml` block stays the single source of truth, edited in the
  file. This is the whole of T-026.
- **Phase B — edit in the browser (future, gated).** Edit fields in the UI and write back
  to the `yaml` block. Deferred deliberately: an in-place YAML round-trip is the exact
  fragility the advisor spec called out (advanced-tooling §2.6, where automated `--apply`
  was deferred "low value vs. risk"). Opens as its own ticket against evidence that
  file-edit friction is real.
- **Phase C — drive execution (future, gated).** Launch / inspect `agent-build-*` runs
  from the viewer, turning it into a control surface. Largest scope; crosses from "design
  artifact" into a runtime UI, so it must clear its own gate and likely its own spec.

Phases B and C are recorded here so the sequence is explicit; neither is scheduled.

---

## 7. Tier 3 — online interface (SKETCH ONLY, gated)

Recorded as a deferred outline, not a build. The plugin's north star is offline,
no-key, runs-inside-Claude-Code; anything **hosted** departs from it, so Tier 3 must
clear a gate with evidence (the §4.4 gated-not-scheduled rule), the same as Tier 2 did.

- **Leading candidate: shareable read-only links.** Publish a blueprint view to a URL so
  a stakeholder explores the design without Claude Code. View-only, no accounts. This is
  the smallest useful online step and the least ethos-breaking (it is the self-contained
  `<name>.viewer.html` of §3, just hosted somewhere reachable).
- **Heavier options, not recommended without strong evidence:** collaborative editing
  (accounts, persistence, conflict handling) or a full hosted workspace (the whole
  design → view → eval loop online). Both pull the project into hosting, auth, and stored
  user data — a different product, governed by a different threat model than an offline
  plugin.
- **Gate.** Tier 3 opens only on evidence that the self-contained file cannot be shared
  the way users need (e.g. recurring requests to send a live design to a non-technical
  stakeholder). Until then it stays a sketch.

---

## 8. Definition of done (Phase A / T-026)

- `visualize_blueprint.py` emits a self-contained `<name>.viewer.html` from the v0.1
  `yaml` block, with all data/JS/CSS inlined, no network fetch, no timestamp →
  byte-identical on regenerate.
- The viewer renders the flow, per-node detail panels (steps + subagents), the 12-
  dimension panel, and filters; encoding matches Tier 1 one-to-one (no drift, no
  fabricated edges).
- Offline `unittest` fixtures assert the generated data model (and a golden HTML
  smoke check) from fixture blueprints; same bad-input exit `2` as the validator and
  the Mermaid path.
- `skills/workflow-design-visualize/SKILL.md` documents the `--html` mode and that the
  artifact is generated, not hand-edited.
- `skill_lint.py` passes; `WORKFLOW_DESIGN_SPEC.md` §9 and advanced-tooling §3 updated to
  record Tier 2 as open/shipped.

---

## 9. Scope boundaries

- **Not here:** any change to the v0.1 schema or the validator (read-only consumer).
- **Not here:** an execution engine — Phase A is a view; driving runs is Phase C, gated.
- **Not here:** vendoring idea-finder's `render.py` or its React UI — borrow the
  interaction patterns, re-implement against the schema (§1).
- **Not here:** Tier 3 hosting — §7 is a gated sketch, not a build.
