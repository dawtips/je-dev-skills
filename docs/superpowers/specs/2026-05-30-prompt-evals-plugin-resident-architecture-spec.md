# Prompt-Evals Plugin-Resident Architecture — Specification & Design

A design contract for **stopping the vendoring of the eval framework into target
projects** and adopting the official `skill-creator` artifact pattern: shared machinery
stays in the plugin; target projects keep only lightweight, owned eval artifacts.

> **Ticket covered:** [T-018] Refactor prompt evals to plugin-resident prompt artifacts
> (phase `agent-build`, type `feature`).
>
> **Relationship to other specs.** This refactor **redefines "the live run path"** that
> the eval live-path integration work (`2026-05-30-eval-live-path-integration-spec.md`,
> T-013/T-014/T-019) wires into — that spec names this one as a hard upstream dependency
> for its in-loop tickets. It revises the lifecycle described in
> `PROMPT_EVAL_FRAMEWORK_SPEC.md` (which assumes the framework is vendored into `./evals`).

---

## 1. Purpose & problem

This repo is a Claude Code plugin of skills used while **building other new agentic
systems**. The prompt-evals workflow should optimize for that development use case.

Today, `prompt-evals-setup`'s happy path **vendors the entire bundled Python eval
framework into each target project as `./evals`.** For a plugin whose purpose is to help
a developer put evals *around a specific prompt*, copying an eval engine into the project
is the wrong default: evals should feel like **development artifacts around that prompt**,
not like a copied engine the developer now owns and must maintain.

The official `skill-creator` solves the analogous problem by keeping shared eval
machinery inside the skill bundle and leaving only lightweight artifacts in the target.
This spec adapts that pattern to prompt-evals.

---

## 2. Target-project shape (the desired happy path)

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
          outputs.json         # generated per-case outputs
          grades.json          # judge grades
          report.html          # rendered report
```

Project-owned files are limited to: **eval specs, frozen cases, prompt references /
adapters, and generated run artifacts.** The **shared runner, grader, aggregation, and
viewer/reporting machinery stay plugin-owned** and read those artifacts via
`${CLAUDE_PLUGIN_ROOT}` — never copied in.

Generated run artifacts under `runs/` get `.gitignore` entries written by setup.

---

## 3. Two evaluation target modes

The runner must support two modes, so it covers both the simple prompt case and real
embedded-prompt apps:

1. **Prompt-file mode (default happy path).** The project has a prompt template file
   (`prompts/planner.md`); eval cases provide the variables; the plugin runner renders
   the prompt, sends it to an LLM, and grades the output. This is the documented default
   for evaluating a specific prompt in a new agentic system.

2. **Command-adapter mode (escape hatch).** For real agentic systems where the prompt
   logic is embedded in code. `eval.json` points at a **project command** that accepts a
   case and returns output/trajectory JSON; the plugin grader handles scoring and reports.
   Documented as the escape hatch for embedded prompts or multi-step agents.

`eval.json` records which mode a given eval uses; the runner dispatches on it.

---

## 4. Lifecycle changes

`prompt-evals-setup` is revised so setup **does not vendor framework code by default**.
Instead it creates/updates the lightweight project artifacts:

- `evals/<prompt-name>/eval.json` (config/spec, incl. target mode + prompt ref/adapter),
- `evals/<prompt-name>/cases.json` once cases are generated,
- `evals/<prompt-name>/runs/` for outputs, grades, and reports,
- `.gitignore` entries for generated run artifacts.

The plugin-owned runner/grader/viewer then reads those artifacts and executes the eval.
The other prompt-evals skills (`-create-dataset`, `-run`) are re-pointed at the
artifact layout rather than a vendored package.

---

## 5. The open architecture decision (must be resolved in the design)

**Where must evals run?** Two answers with different consequences:

- **Claude-Code-only (dev-time).** Evals only need to run *inside Claude Code* during
  development. The plugin runner is invoked via the skill; no packaged CLI is required.
  Simpler; matches the plugin's stated purpose.
- **Headless / CI too.** If evals must also run outside Claude Code (CI, headless), the
  shared machinery likely needs to be a **packaged CLI** the project can invoke without
  the plugin runtime — a larger surface and a distribution question.

The design **must call this out explicitly** and pick a default (recommended:
Claude-Code-only for v1, with the artifact layout deliberately CLI-compatible so a
packaged CLI is an additive later step, not a rewrite). This is the single decision that
most shapes the runner's packaging.

---

## 6. Acceptance criteria (from the ticket, made testable)

- The design **explicitly compares** current vendoring against the official
  `skill-creator` eval approach, and justifies the chosen pattern.
- `prompt-evals-setup` **no longer assumes copying the full framework into `./evals`** as
  the default architecture.
- Project-owned files are limited to eval specs, frozen cases, prompt references/adapters,
  and generated run artifacts (§2).
- Plugin-owned files contain the shared runner, grader, aggregation, and viewer/reporting
  machinery, resolved via `${CLAUDE_PLUGIN_ROOT}`.
- **Prompt-file mode** documented as the default happy path (§3.1).
- **Command-adapter mode** documented as the escape hatch (§3.2).
- The **dev-time-vs-headless/CI** decision (§5) is called out, decided, and the layout
  is forward-compatible with the deferred option.
- The eval live-path tickets (T-013/T-014/T-019) are expressible against the new run path
  without re-vendoring (this spec is their named upstream dependency).

---

## 7. Migration & compatibility

- Existing projects that already vendored `./evals` keep working; the refactor changes the
  **default** for new setups, and documents a migration note for vendored projects (the
  shared machinery moves to the plugin; the project keeps its specs/cases/runs).
- `PROMPT_EVAL_FRAMEWORK_SPEC.md`'s "vendored `evals/` top level" language is updated to
  reflect plugin-residence, or annotated with a pointer to this spec as the superseding
  architecture.

---

## 8. Definition of done

- This spec (or its derived plan) records the vendoring-vs-`skill-creator` comparison and
  the resolved §5 decision.
- `prompt-evals-setup` creates the §2 artifact layout (no framework copy by default),
  including `.gitignore` entries, with offline tests over the generated layout.
- The plugin-owned runner reads project artifacts and dispatches on the §3 target mode;
  both modes documented in the relevant `SKILL.md` files.
- Cross-spec pointers updated: framework spec annotated (§7); the eval live-path spec's
  §2 dependency satisfied or sequenced.
- Skill linter + offline suites pass with actual output shown (per `AGENTS.md`).

---

## 9. Scope boundaries

- **Not here:** the live-path *wiring* of assertions/variance/run-delta — that is the eval
  live-path spec (T-013/T-014/T-019). This spec only re-shapes the path they plug into.
- **Not here:** a packaged headless/CI CLI implementation — deferred per §5 (layout stays
  compatible so it is additive later).
- **Not here:** changes to the judge/evaluator core grading logic — this is an
  artifact-location and lifecycle refactor, not a grading change.
