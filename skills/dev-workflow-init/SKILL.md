---
name: dev-workflow-init
description: This skill should be used when the user wants to "set up a new project with this dev workflow", "bootstrap storybloq and superpowers", "scaffold the working agreement", "add the spec/plan/handover workflow to a repo", or otherwise stand up the storybloq (durable memory) + superpowers (spec->plan->implement->verify) development loop in a fresh or existing project. It writes the .story/ memory skeleton, the docs/superpowers/{specs,plans} docs skeleton, AGENTS.md + CLAUDE.md, and the git ignores, then seeds the first roadmap phase and ticket.
argument-hint: "[project name, e.g. order-portal] [optional target dir, default .]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Dev Workflow: Init

Stand up the combined **storybloq + superpowers** development workflow in a project, so
every later change follows one loop: **roadmap -> ticket -> spec (if non-obvious) -> plan
-> implement + adversarially verify -> handover + lesson -> delete plan -> integrate +
clean up automatically.**

The two systems combine under a single rule, which the generated `AGENTS.md` states in
full:

> **superpowers is the *method* (how you build). storybloq is the *memory* (what
> persists). A plan is the one disposable artifact that bridges them — deleted before
> merge.**

This SKILL is a table of contents. The deterministic skeleton is written by a tested
script; you only drive the parts that need judgment (naming, seeding the first real
ticket).

## Preconditions

- A target directory exists (a git repo is ideal but not required).
- Decide the project's short name. If the user did not give one, ask before Step 1.

## Procedure

### 1. Scaffold the skeleton (deterministic)

Run the renderer from the plugin. It refuses to clobber existing files unless `--force`,
so it is safe to run in a populated repo; preview first with `--dry-run`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-workflow-init/scripts/init_project.py" \
  --name "<project name>" --root "<target dir>" --dry-run
```

Review the file list with the user, then drop `--dry-run` to write. This creates:

- `.story/config.json`, `.story/roadmap.json` (one `foundation` phase), `.story/.gitignore`
- `.story/tickets/T-001.json` (a placeholder seed ticket), plus `.story/handovers/` and
  `.story/lessons/` (kept via `.gitkeep`)
- `docs/superpowers/specs/` and `docs/superpowers/plans/` (kept via `.gitkeep`)
- `AGENTS.md` (the canonical, tool-neutral working agreement) and `CLAUDE.md` (imports it
  via `@AGENTS.md`)
- a storybloq runtime-state block appended to the root `.gitignore` (idempotent)

### 2. Seed the first real roadmap phase and ticket (judgment)

The scaffold ships a generic `foundation` phase and a placeholder `T-001`. Replace them
with the project's reality:

- Edit `.story/roadmap.json`: rename/split `foundation` into the phases the project
  actually has, keeping the `{id, label, name, description}` shape and `PHASE N` labels.
- Edit `.story/tickets/T-001.json` (or add `T-002`, …) so the first ticket names a real
  first unit of work: a concrete `title`, `description`, `phase` matching a roadmap id,
  `status: open`, and `blockedBy: []`. Keep the zero-padded `T-00N` id convention and the
  `order` field (increments of 10 leave room to insert).

### 3. Fill the project-specific blanks (judgment)

- In `CLAUDE.md`, fill the **Project specifics** comment: how to run the app, where the
  entry points are, environment quirks.
- In `AGENTS.md`, fill the **Tests** section with the project's real test/lint commands
  once they exist (leave the placeholder if the project has none yet).
- Do **not** weaken the "Deleting plans once implemented" rule, the branch/worktree
  cleanup rule, or the hard rules — those are the point of the workflow.

### 4. Commit the scaffold

Commit the new files as one change (e.g. `chore: bootstrap storybloq + superpowers dev
workflow`). From here, all further work goes through the loop in `AGENTS.md`.

## Definition of done

- `.story/` exists with a valid `config.json`, a `roadmap.json` whose phases reflect the
  project, and at least one real `open` ticket.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` exist (plans empty but tracked).
- `AGENTS.md` and `CLAUDE.md` exist; `CLAUDE.md` imports `AGENTS.md` via `@AGENTS.md`.
- Root `.gitignore` ignores `.story/{snapshots,sessions}/` and `.story/status.json`.
- `AGENTS.md` says completed plans are deleted before merge, completed work is merged
  locally to the default branch, verification is rerun there, and the feature worktree
  and branch are removed.
- The scaffold is committed.

## Boundaries

- This skill **bootstraps** the workflow; it does not run it. The ongoing loop is owned by
  the generated `AGENTS.md` (and, for agent apps, the `workflow-design-*` / `agent-build-*`
  skills).
- It does **not** install storybloq or superpowers as tools. The generated files are
  tool-neutral: they describe the working agreement and the durable artifacts, and they
  work whether or not the storybloq CLI is installed. Per `CONTRIBUTING.md`, depend on the
  installed companion tools rather than vendoring them.
- Re-running on a populated repo requires `--force` and will overwrite the listed files —
  preview with `--dry-run` first and check with the user.

## Verify

The script is offline and unit-tested. Run its suite from the repo root:

```bash
cd "${CLAUDE_PLUGIN_ROOT}/skills/dev-workflow-init/scripts" && \
  python3 -m unittest discover -s tests -t .
```
