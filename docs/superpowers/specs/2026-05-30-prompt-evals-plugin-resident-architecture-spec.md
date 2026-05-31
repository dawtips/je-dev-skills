# Prompt-Evals Plugin-Resident Architecture — Specification & Design

A design contract for **stopping the vendoring of the eval framework into target
projects** and adopting the official `skill-creator` artifact pattern: shared machinery
stays in the plugin; target projects keep only lightweight, owned eval artifacts.

> **Ticket covered:** [T-018] Refactor prompt evals to plugin-resident prompt artifacts
> (phase `agent-build`, type `feature`).
>
> **Relationship to other specs (read first — this is a *retrofit*, not a precursor).**
> When this spec was first drafted it assumed it was the *upstream* dependency of the
> eval live-path integration work (`2026-05-30-eval-live-path-integration-spec.md`,
> T-013/T-014/T-019). That is no longer true: **T-013/T-014/T-019 already shipped and
> merged** (all `complete`, `completedDate 2026-05-30`, merge `86fa682`) against today's
> vendored `./evals` layout. So this refactor lands *after* them and must **retrofit** a
> plugin-resident layout *under* an already-wired live run path. The governing design
> consequence is §3: the new artifact path **routes through the same
> `live_run.run_evaluation` seam those tickets hardened**, inheriting assertion gating,
> K-run variance, and baseline run-delta rather than re-implementing or re-vendoring them.
> It revises the lifecycle described in `PROMPT_EVAL_FRAMEWORK_SPEC.md` (which assumes the
> framework is vendored into `./evals`).

---

## 1. Purpose & problem

This repo is a Claude Code plugin of skills used while **building other new agentic
systems**. The prompt-evals workflow should optimize for that development use case.

Today, `prompt-evals-setup`'s happy path **vendors the entire bundled Python eval
framework into each target project as `./evals`** (`cp -R
${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals "$TARGET/evals"`). For a
plugin whose purpose is to help a developer put evals *around a specific prompt*, copying
an eval engine into the project is the wrong default: evals should feel like **development
artifacts around that prompt**, not like a copied engine the developer now owns and must
maintain (and that drifts from the plugin's version).

The official `skill-creator` solves the analogous problem by keeping shared eval
machinery inside the skill bundle and leaving only lightweight artifacts in the target.
This spec adapts that pattern to prompt-evals.

---

## 2. The `skill-creator` comparison (acceptance-criterion #1)

The chosen pattern is justified by direct comparison with the official `skill-creator`
eval flow, the current prompt-evals vendoring, and the proposed plugin-resident model.

**What `skill-creator` actually does** (read from
`~/.claude/plugins/cache/claude-plugins-official/skill-creator/.../skills/skill-creator/`):

- **Plugin bundle holds *all* machinery and templates:** `scripts/*.py` (`run_eval.py`,
  `aggregate_benchmark.py`, `run_loop.py`), `eval-viewer/generate_review.py` +
  `viewer.html`, `assets/eval_review.html`, `agents/*.md` grader/analyzer instruction
  sets, `references/schemas.md`. None of this is ever copied into the user's skill.
- **Target holds only artifacts + results + feedback:** a sibling
  `<skill-name>-workspace/` containing `iteration-N/eval-ID/{eval_metadata.json,
  with_skill/{outputs/,grading.json,timing.json}, without_skill/...}`, plus
  `benchmark.json`, `benchmark.md`, `feedback.json`. Pure JSON/outputs — no engine.
- **Plugin machinery reads the target's artifacts:** `generate_review.py` walks the target
  workspace, embeds outputs into a standalone HTML viewer (or serves it), and POSTs
  feedback back into the workspace; `aggregate_benchmark.py` reads `grading.json` files
  from the target and writes `benchmark.json` back. The viewer is plugin-owned and reads
  *local* artifacts.

**Comparison table.**

| Concern | `skill-creator` (reference) | prompt-evals **today** (vendored) | prompt-evals **proposed** (this spec) |
|---|---|---|---|
| Runner / grader / aggregator code | plugin `scripts/` only | **copied into `./evals`** | plugin `framework/evals/` only |
| Viewer / report machinery | plugin `eval-viewer/` only | **copied into `./evals`** | plugin `framework/evals/` only |
| What the target owns | `*-workspace/` JSON + outputs + feedback | the **entire framework** + config + data | `evals/<name>/{eval.json,cases.json,runs/}` |
| How machinery finds target data | path arg → walks workspace | `import evals` resolves the copy | path arg (`eval.json`) → resolves project paths |
| Version drift risk | none (single source) | **high** (each copy forks) | none (single source) |
| Generated run artifacts | in workspace, gitignored | in `evals/runs/`, gitignored | in `evals/<name>/runs/`, gitignored |

**Why this pattern wins here:** a single source of truth for the machinery (no per-project
forks to maintain or patch), a target tree that reads as "evals *about my prompt*" rather
than "an engine I now own," and a clean path arg boundary that is equally usable by a
future packaged CLI (§6). The cost — machinery is resolved via `${CLAUDE_PLUGIN_ROOT}`
rather than a local `import evals` — is exactly the cost `skill-creator` already pays, and
is acceptable for a dev-time plugin.

---

## 3. Decision: one unified run path (no parallel, less-capable runner)

**This is the load-bearing decision of the refactor.** The live-path tickets already
shipped four deterministic capabilities onto the **vendored** run path:
`live_run.run_evaluation` performs **assertion gating before the paid judge**, writes the
report, and accepts `baseline=` (run-delta) and `variance_runs=` analysis; `run_eval
evaluate-variance` orchestrates **K-run variance** via `variance_runner.run_k_variance`.

A naive plugin-resident refactor would add a *second* artifact runner that renders a prompt
and grades it — and silently **lose** assertions, variance, and run-delta, making the new
*default* path less capable than the legacy one. That is rejected.

Instead, the artifact path is a **thin front-end over the existing seam**:

> `evaluate-artifact <eval.json>` builds a `run_function` (prompt-file render or
> command-adapter subprocess) and reads `assertions`/`extra_criteria`/`assertion_policy`
> from `eval.json`, then calls the **existing** `live_run.run_evaluation(...)` with
> `dataset_file = evals/<name>/cases.json` and `runs_dir = evals/<name>/runs`. K-run
> variance reuses `run_k_variance` with the artifact `run_once`; run-delta reuses the
> `baseline=` parameter; the report is the existing `report.write_json/write_html`.

Concretely, `run_evaluation` already takes everything needed as explicit keyword
parameters — `dataset_file`, `runs_dir`, `assertions`, `assertion_policy`,
`extra_criteria`, `process_criteria`, `run_label`, `baseline`, `variance_runs` — so the
artifact front-end supplies **project-relative paths** and inherits every live-path
feature with **no re-wiring and no capability regression**. This is what makes T-018 a
retrofit *under* T-013/T-014/T-019 rather than a competitor to them.

---

## 4. Target-project shape (the desired happy path)

A new agentic project should look like this — **artifacts, not an engine**:

```text
new-agentic-project/
  prompts/
    planner.md                 # the prompt template under evaluation
  evals/
    planner/
      eval.json                # config/spec: target mode, prompt ref, judge config
      cases.json               # frozen eval cases (variables per case)
      runs/
        <timestamp>/
          output.json          # generated per-case outputs + grades (run_evaluation)
          output.html          # rendered report (run_evaluation)
```

Project-owned files are limited to: **eval specs, frozen cases, prompt references /
adapters, and generated run artifacts.** The **shared runner, grader, aggregation, and
viewer/reporting machinery stay plugin-owned** under
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals` and read those artifacts
— never copied in.

> Note: `run_evaluation` writes `output.json`/`output.html` (not `outputs.json`/
> `report.html`). The earlier draft's filenames are corrected here to match the actual
> writer, so the live-path report surface is inherited verbatim.

Generated run artifacts under `runs/` get a `.gitignore` entry written by setup; the
directory is preserved with `runs/.gitkeep`.

### 4.1 `eval.json` schema (project-owned config)

```json
{
  "name": "planner",
  "target": {
    "mode": "prompt_file",
    "prompt_file": "prompts/planner.md"
  },
  "cases_file": "cases.json",
  "runs_dir": "runs",
  "extra_criteria": "Must include ...",
  "process_criteria": null,
  "assertions": [ { "type": "contains", "value": "...", "severity": "advisory" } ],
  "assertion_policy": "gate_mandatory"
}
```

- `target.mode` ∈ `{ "prompt_file", "command_adapter" }` (validated on load).
- Prompt-file mode uses `target.prompt_file`; command-adapter mode uses
  `target.command` (an argv array) instead.
- **Path resolution (deterministic, from the prescribed layout):** given the path to
  `eval.json`, `eval_dir` is its parent (`<project>/evals/<name>`) and
  `project_root = eval_dir.parents[1]` (`<project>`). `cases_file` and `runs_dir` resolve
  relative to `eval_dir`; `prompt_file` and the command-adapter `command`/cwd resolve
  relative to `project_root`. This keeps `cases.json`/`runs/` co-located with the eval and
  prompt/command references rooted where the developer authored them. v1 derives
  `project_root` purely from the prescribed layout; a `--project-root` override for
  non-standard layouts is a possible later addition, not part of this change.
- `cases_file` points at the frozen dataset, which uses the **existing** dataset shape
  consumed by `run_evaluation`: a JSON object with a `cases` array (each case has
  `prompt_inputs`) and optional `provenance.task_description`.

---

## 5. Two evaluation target modes

The runner must support two modes, so it covers both the simple prompt case and real
embedded-prompt apps:

1. **Prompt-file mode (default happy path).** The project has a prompt template file
   (`prompts/planner.md`); eval cases provide the variables; the runner renders the prompt
   and the run path grades the output. Rendering **reuses** `promptprep.check_placeholders`
   (raising `MissingPlaceholderError` listing all missing keys) and
   `evaluator/templates.render(template, /, **values)` — it does **not** duplicate
   placeholder/render logic. Documented as the default for evaluating a specific prompt in
   a new agentic system.

2. **Command-adapter mode (escape hatch).** For real agentic systems where the prompt
   logic is embedded in code. `eval.json` `target.command` names a **project command**;
   the runner invokes it as a subprocess with the case JSON on **stdin** and reads
   output/trajectory JSON from **stdout**; the run path grades and reports. Documented as
   the escape hatch for embedded prompts or multi-step agents.

`eval.json`'s `target.mode` records which mode a given eval uses; `build_run_function`
dispatches on it to produce the `RunFunction` that `run_evaluation` executes.

---

## 6. Execution model & the open architecture decision

**Where must evals run?** Two answers with different consequences:

- **Claude-Code-only (dev-time) — chosen for v1.** Evals only need to run *inside Claude
  Code* during development. Two sub-paths mirror today's framework:
  - **In-Claude-Code (default, no API key):** the `prompt-evals-run` skill orchestrates
    subagents. The deterministic pieces are plugin-owned CLIs — a new `render-artifact
    <eval.json> <case_index>` renders a case's prompt for the executor subagent, and the
    **existing** `python -m evals.aggregate --runs-dir evals/<name>/runs --dataset
    evals/<name>/cases.json ...` (already layout-agnostic) writes the report. No framework
    copy required.
  - **Keyed (`EXECUTION_MODE=anthropic_api`, headless-ish):** `evaluate-artifact
    <eval.json> [run_label]` runs in-process through `run_evaluation` with an
    `AnthropicClient` judge. Mode-gated exactly like the legacy `evaluate` (returns guidance
    and exit 3 under `in_claude_code`).
- **Headless / CI as a packaged CLI — deferred.** A fully standalone CLI the project can
  invoke without the plugin runtime is a larger distribution surface. **Deferred**, but the
  artifact layout and the `eval.json` path-arg boundary are deliberately CLI-compatible, so
  a packaged CLI is an **additive later step, not a rewrite**.

This is the single decision that most shapes the runner's packaging; v1 is Claude-Code-only
with a CLI-compatible layout.

---

## 7. Lifecycle changes

`prompt-evals-setup` is revised so setup **does not vendor framework code by default**.
Instead it creates/updates the lightweight project artifacts:

- `evals/<name>/eval.json` (config/spec, incl. target mode + prompt ref/adapter),
- `evals/<name>/cases.json` once cases are frozen (default no-key interactive
  authoring, or keyed `generate-artifact` for headless/CI),
- `evals/<name>/runs/` (with `.gitkeep`) for outputs, grades, and reports,
- a `.gitignore` entry for generated run artifacts (idempotent insertion of
  `evals/*/runs/*` plus a `!evals/*/runs/.gitkeep` negation).

New deterministic, plugin-owned surface (all offline-testable):

- `evals/artifacts.py` — `EvalSpec`/`TargetSpec`, `load_eval_spec(eval_json_path)`,
  `scaffold_eval_artifacts(project_root, name, *, mode, prompt_file=…/command=…)`,
  idempotent `.gitignore` insertion, and the §4.1 path-resolution helpers.
- `evals/artifact_runner.py` — `render_prompt_file(spec, prompt_inputs)` (reuses
  promptprep + templates), `run_command_adapter(spec, case)` (subprocess; case JSON on
  stdin), `build_run_function(spec)` (dispatch on mode), and `evaluate_artifact(spec,
  judge_client, *, run_label=None, baseline=None, variance_runs=None)` which calls
  `run_evaluation` with project-relative `dataset_file`/`runs_dir`.
- `evals/run_eval.py` — additive CLI branches `generate-artifact <eval.json>`,
  `evaluate-artifact <eval.json> [run_label]`, and `render-artifact <eval.json>
  <case_index>`. **Legacy `generate`/`evaluate`/`evaluate-variance` behavior is kept
  intact** for already-vendored projects.

`prompt-evals-create-dataset` mirrors the run-path split: the default interactive session
generates cases and writes the frozen `cases.json` with `generation_mode: in_session_no_key`;
`generate-artifact <eval.json>` remains the keyed SDK path for unattended runs. Both paths
produce the same dataset shape consumed by `criteria_audit`, `prompt-evals-run`, and
`aggregate`.

The other prompt-evals skills (`-create-dataset`, `-run`) are re-pointed at the artifact
layout rather than a vendored package, with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework"`.

---

## 8. Acceptance criteria (from the ticket, made testable)

- The design **explicitly compares** current vendoring against the official
  `skill-creator` eval approach, and justifies the chosen pattern (**§2**, with table).
- `prompt-evals-setup` **no longer assumes copying the full framework into `./evals`** as
  the default architecture; setup scaffolds the §4 artifact layout instead.
- Project-owned files are limited to eval specs, frozen cases, prompt references/adapters,
  and generated run artifacts (§4).
- Plugin-owned files contain the shared runner, grader, aggregation, and viewer/reporting
  machinery, resolved via `${CLAUDE_PLUGIN_ROOT}`.
- **Prompt-file mode** documented as the default happy path (§5.1) and **reuses**
  promptprep/templates (no duplicated render logic).
- **Command-adapter mode** documented as the escape hatch (§5.2).
- The **dev-time-vs-headless/CI** decision (§6) is called out, decided
  (Claude-Code-only v1), and the layout is forward-compatible with the deferred CLI.
- **No capability regression:** the already-merged live-path features
  (assertions/variance/run-delta) are preserved by routing the artifact path through the
  existing `run_evaluation` seam (**§3**); the new default path is at least as capable as
  the legacy vendored path. This supersedes the original draft's "expressible without
  re-vendoring" wording, which assumed the live-path work had not yet landed.

---

## 9. Migration & compatibility

- Existing projects that already vendored `./evals` keep working: the legacy CLI commands
  and the vendoring substrate update are retained; the refactor changes the **default** for
  new setups. `prompt-evals-setup` documents a migration note for vendored projects (the
  shared machinery moves back to the plugin; the project keeps its specs/cases/runs).
- `PROMPT_EVAL_FRAMEWORK_SPEC.md`'s "vendored `evals/` top level" language (§1, §2, §5,
  §11 bootstrap, §13 hardening) is annotated with a pointer to this spec as the superseding
  architecture for new setups.
- `2026-05-30-eval-live-path-integration-spec.md` §2's "resolve T-018 before building
  T-014/T-019" sequencing note is annotated as **resolved after the fact**: the live-path
  work landed first, and T-018 retrofits under it by reusing the `run_evaluation` seam.

---

## 10. Definition of done

- This spec records the vendoring-vs-`skill-creator` comparison (§2) and the resolved §6
  decision, and locks the unified-run-path decision (§3).
- `prompt-evals-setup` creates the §4 artifact layout (no framework copy by default),
  including the `.gitignore` entry, with offline tests over the generated layout.
- The plugin-owned artifact runner dispatches on the §5 target mode and routes through
  `run_evaluation`; both modes are documented in the relevant `SKILL.md` files.
- Cross-spec pointers updated: framework spec annotated (§9); the eval live-path spec's §2
  sequencing note annotated as resolved.
- Skill linter + the four offline suites in `AGENTS.md` pass with actual output shown.

---

## 11. Scope boundaries

- **Not here:** the live-path *wiring* of assertions/variance/run-delta — that already
  shipped (T-013/T-014/T-019). This spec **reuses** that seam (§3), it does not re-wire it.
- **Not here:** a packaged headless/CI CLI implementation — deferred per §6 (layout stays
  compatible so it is additive later).
- **Not here:** changes to the judge/evaluator core grading logic or to `run_evaluation`'s
  internals — this is an artifact-location, lifecycle, and front-end refactor, not a
  grading or seam change.
- **Not here:** rewriting the bundled framework's own default config paths
  (`config.DATASETS_DIR`/`RUNS_DIR` stay as the legacy defaults); the artifact front-end
  supplies explicit project-relative paths to `run_evaluation`/`aggregate` and never relies
  on those defaults.
