# Workflow-Design Advanced Tooling (§9 v0.3+) — Specification

A design contract for the two deferred `workflow-design-*` roadmap features: the
**automated model-selection advisor** and the **visual viewer**. Both are purely
additive, read from (or fill) the v0.1 blueprint schema, and ship only if their gate
fires.

> **Tickets covered:** [T-015] workflow-design model-selection advisor §9 (phase
> `backlog`, "deferred / maybe-never"), [T-016] workflow-design visual viewer §9 (phase
> `backlog`, type `feature`, deferred).
>
> **Parent spec.** `WORKFLOW_DESIGN_SPEC.md` §9 ("v0.2+ roadmap") owns both. This spec
> records each as a tracked-but-deferred contract: what it is, what it reads, the tier
> plan, and the gate that justifies building it. Neither changes v0.1.

---

## 1. Purpose & why grouped

Both are §9 v0.3+ tooling layers on top of the **locked v0.1 blueprint schema (§4)** —
they consume the same fenced `yaml` block the interview produces and the validator gates.
Neither is on the critical path; both are "build only if the cheaper v0.1 form proves
insufficient." Grouping them keeps the §9 roadmap's deferred-tooling contract in one
place. They are **independent** of each other and can be built (or dropped) separately.

**Shared invariant.** Both read from / fill the v0.1 schema and leave v0.1 unchanged
(parent spec §9: "purely additive and read from (or fill) the schema locked in §4").

---

## 2. T-015 — Automated model-selection advisor

### 2.1 What ships in v0.1 (context, not this ticket)
The **guideline** form already ships: the interview (parent spec §6, stage 4) recommends
a Claude `model` + `effort` per agentic step / subagent, **with rationale**, from
`references/model-selection.md`. That human-in-the-loop guideline is the baseline this
ticket would replace.

### 2.2 What T-015 adds (the deferred form)
The **automated** form: a script that scores a task — desired output, complexity,
cost/token budget — and **emits a model+effort recommendation programmatically**, rather
than relying on the interviewer applying the guideline by hand.

### 2.3 Constraints
- **Claude models only** (parent spec §9). Model IDs are volatile and live in a single
  named constant with an update-here comment — never scattered (matches the
  `WORKFLOW_DESIGN_REVIEW_SPEC.md` §6.3 / parent §6 convention).
- Reads the v0.1 schema's agentic steps/subagents; writes recommendations back into the
  same `model`/`effort` fields it already defines. No schema change.
- If built, prefer a **deterministic scorer** over an LLM call where the routing logic is
  expressible as rules (the plugin's "deterministic over non-deterministic" north star);
  reserve any model call for genuine judgment.

### 2.4 Gate (this is "maybe-never")
Pursued **only if the v0.1 guideline proves insufficient** — i.e. interviewers
demonstrably misroute model/effort despite the guideline. Absent that evidence, T-015
stays deferred. The decision to build is itself a recorded finding, not a default.

### 2.5 Definition of done (if built)
A scorer takes (output spec, complexity signal, budget) → `model` + `effort` +
rationale; model IDs in one constant; deterministic core offline-tested; writes into the
v0.1 fields without schema change; parent spec §9 updated to mark it shipped.

### 2.6 Status — shipped (T-015)
Built as a **deliberate override of the §2.4 "maybe-never" gate** (the user chose to
build it; recorded here and in the T-015 handover, so it is a recorded finding, not a
silent default). Lives in `skills/workflow-design-advise/` (`scripts/advise_model.py` +
six offline test files). Decisions that refine this contract:

- **Mechanism: script-emits + skill-applies.** The script is a pure analyzer; it prints a
  report (and `--json`), and the SKILL.md drives the `model`/`effort` edits with the Edit
  tool — mirroring `workflow-design-validate` (analyzer + agent edits), avoiding a fragile
  in-place YAML round-trip. An automated `--apply` is **deferred** (low value vs. risk).
- **Steps are advisory; only subagents are writeable.** The v0.1 schema (§2) stores
  `model`/`effort` on `subagents`, not `steps`, so step recommendations are advisory
  (recorded in prose), never written to a nonexistent step field.
- **Tiers over IDs; honest determinism.** Recommends a tier (one `MODEL_IDS` constant
  re-verified against `citations.md`); a subagent's task *difficulty* is surfaced as a
  human `needs_review` flag rather than guessed.
- **Budget input is human-supplied.** `--budget high` caps effort at `medium` (bounding the
  ~15× multiplier); cost pressure is never inferred from blueprint prose.

---

## 3. T-016 — Visual viewer

### 3.1 What it renders
Render a validated blueprint visually: the step **flow** (a DAG showing ordering,
parallel sections, approval gates, and deterministic-vs-agentic coloring) plus
**drill-down** into each step's and subagent's details. Source of truth: the same fenced
`yaml` block — no new authoring surface.

### 3.2 Two tiers, cheapest first (parent spec §9)
- **Tier 1 — Mermaid (likely default).** Deterministically generate a **Mermaid
  flowchart** from the blueprint `yaml` and emit it alongside the blueprint. Renders for
  free in GitHub / VSCode / Markdown previews, **zero runtime**. This is the expected
  shipping tier.
- **Tier 2 — browser viewer (only if Tier 1 insufficient).** A small interactive view —
  clickable nodes → step / subagent detail panels. Built only if static Mermaid proves
  inadequate for the drill-down need.

### 3.3 Constraints
- **Deterministic generation.** Tier 1 is a pure schema→Mermaid transform: no model call,
  fully offline-testable (fixture blueprint → expected Mermaid string). This fits the
  plugin's determinism north star and the repo's offline-test ethos.
- Coloring/encoding maps directly to schema fields (`kind: deterministic|agentic`,
  parallel sections, approval gates) so the diagram cannot drift from the validated
  structure.
- Reads the v0.1 schema only; emits a sibling artifact next to the blueprint (diffable,
  versioned alongside it — mirrors the review report convention).

### 3.4 Gate
Tier 1 is low-risk and could ship whenever a visual aid is wanted. **Tier 2 is gated** on
Tier 1 proving insufficient — do not build the browser viewer speculatively.

### 3.5 Definition of done (if built)
Tier 1: deterministic `yaml`→Mermaid generator with offline fixture tests; emits a sibling
diagram artifact; encodes ordering/parallel/gates/determinism coloring; parent spec §9
updated. Tier 2 only opens as its own ticket if Tier 1 is shown insufficient.

### 3.6 Status — Tier 1 shipped (T-016)
Tier 1 is shipped: the user requested the visual aid, and per §3.4 Tier 1 is
**ungated** ("could ship whenever a visual aid is wanted"), so this is within contract, not
a gate override. **Tier 2's gate was opened 2026-06-08**; its detailed contract is
[2026-06-08-workflow-design-interactive-viewer-spec.md](2026-06-08-workflow-design-interactive-viewer-spec.md)
(T-026), with read-only navigation as the in-scope Phase A. Tier 1 lives in
`skills/workflow-design-visualize/` (`scripts/visualize_blueprint.py` + offline tests).
The decisions that refine this contract:

- **Skill: `workflow-design-visualize`.** A new `workflow-design-*` member, run after
  `workflow-design-validate` passes. Offline, deterministic, no API key, no model call — a
  pure `yaml`→Mermaid transform mirroring `workflow-design-validate`'s analyzer shape.
- **Artifact: a Markdown sibling `<name>.diagram.md`.** Emitted next to the blueprint
  (mirrors the `.review.md` convention). It holds one fenced `mermaid` block plus a
  **drill-down** details section — a per-step table and a per-subagent table — which is
  Tier 1's static stand-in for §3.1's interactive drill-down. The file carries **no
  timestamp**, so regenerated output is byte-stable and diffable.
- **Edges = `steps` list order.** `step[i] → step[i+1]`, following the ordered `steps`
  list (parent spec §7: ordering comes from the steps DAG). The v0.1 schema (§4.1) has no
  explicit `next`/`depends_on` field, so a data-flow DAG would have to string-match
  free-form `inputs`/`outputs` (e.g. `run_id`, `topic`) — fuzzy and drift-prone. List
  order is unambiguous and **cannot drift** from the validated structure (§3.3).
- **Encoding maps one-to-one to schema fields — no inference (§3.3).**
  - `kind` → node **color *and* shape** (deterministic = rectangle + one `classDef`;
    agentic = rounded + another), with the kind also written in the label text so the
    diagram reads without color (accessibility).
  - `pattern` → a `· <pattern>` tag in the node label when not `none` (kept off the shape
    to avoid Mermaid multi-class merge quirks; the full pattern is in the detail table).
  - `approval_gate` → a hexagon gate node inserted **after** the step it is declared on
    (`step → gate → next`); `none` inserts nothing. The "after the step" placement (the
    step's result passes a human gate before the flow continues) is the documented
    convention.
  - `subagents` → a separate `subgraph` cluster, one node per subagent labeled with `id`
    plus `model`/`effort`. **No fabricated step→subagent edges** — the v0.1 schema has no
    field linking a step to the subagent it delegates to, and inventing one is exactly the
    drift §3.3 forbids; the relationship is carried by the detail table and a caption.
- **Robust, deterministic core.** Mermaid-safe node ids (slugified, duplicate `id`s
  disambiguated, no leading digit), label escaping (`"`, `[`, `]`, `&`, `<`, `>`),
  graceful `steps: []` and missing-optional-field handling, and exit `2` on the same
  bad-input conditions as the validator (not exactly one fenced `yaml` block; the block is
  not a mapping). Offline `unittest` fixtures assert golden Mermaid strings.

---

## 4. Shared design rules

1. **Additive, schema-stable.** Both read from / fill the v0.1 §4 schema; neither changes
   v0.1 or the validator (parent spec §9).
2. **Deterministic first.** The viewer Tier 1 is pure transform; the advisor prefers a
   rule scorer over a model call — both offline-testable.
3. **Volatile model IDs isolated.** Any Claude model reference lives in one named constant
   with an update-here comment.
4. **Gated, not scheduled.** Building any deferred tier is a recorded decision against
   evidence, not a roadmap default. The shipped Tier-1 forms were such decisions (T-015
   §2.6 — a deliberate override of the §2.4 "maybe-never" gate; T-016 §3.6 — under the
   §3.4 ungated allowance). **Tier 2's §3.4 gate was opened by a recorded decision on
2026-06-08** (T-026; see
[2026-06-08-workflow-design-interactive-viewer-spec.md](2026-06-08-workflow-design-interactive-viewer-spec.md)
§1).

---

## 5. Scope boundaries

- **Not here:** `workflow-design-scaffold` — superseded by the `agent-build-*` group
  (parent spec §9; `2026-05-29-agent-build-and-execution-spec.md` §3). The viewer renders
  a blueprint; it does not generate runtime artifacts.
- **Not here:** any execution engine — the blueprint stays a design artifact (parent spec
  §9 "Other non-goals").
- **Not here:** non-Claude models in the advisor (parent spec §9: Claude only).
- The viewer's **Tier 2 gate was opened 2026-06-08** (T-026; contract in
  [2026-06-08-workflow-design-interactive-viewer-spec.md](2026-06-08-workflow-design-interactive-viewer-spec.md)).
  Its **Tier 3 (online) stays a gated sketch** (that spec §7). The Tier-1 forms of
  both features are shipped (T-015 §2.6, T-016 §3.6).
