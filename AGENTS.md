# Working agreement for je-dev-skills

This repo ships **Claude Code skills** for building agent apps. It is built with two
companion methodologies. This file is the canonical, tool-neutral working agreement;
Codex reads it directly, and `CLAUDE.md` imports it for Claude Code.

## The two methodologies and how they combine

- **superpowers** is the *method*: spec → plan → implement → **adversarially verify**.
  It contributes durable **specs** and disposable **plans**.
- **storybloq** (`.story/`) is the *durable memory*: roadmap, tickets, handovers, lessons.

They overlap on exactly one thing — the narrative of work (a superpowers *plan* and a
storybloq *handover* both describe what was done). Resolve it with one rule:

> **Specs are durable. Plans are disposable. Handovers are the single narrative of record.**

A plan is a working scratchpad for *one* build. When its ticket closes, distill the plan's
durable residue into the spec (if the design changed), a handover (what happened), and a
lesson (what to remember) — then **delete the plan file**. Plans must never accumulate on
`main`.

## The loop

For any non-trivial change, work this order:

1. **Roadmap** — place the work in a phase (`.story/roadmap.json`). Durable.
2. **Ticket** — open one in `.story/tickets/` with status, phase, and `blockedBy`. Durable;
   mark `complete` when done, never delete.
3. **Spec (only if the design is non-obvious)** — write a durable design contract in
   `docs/superpowers/specs/`. Skip for mechanical changes.
4. **Plan** — write the build scratchpad in `docs/superpowers/plans/`. **Ephemeral.** Name
   it `<date>-<ticket>-<slug>.md` and start it with `Status: In progress`.
5. **Implement + adversarially verify** (the superpowers discipline):
   - Build the **deterministic core first**, with offline `unittest` fixtures. Reserve the
     LLM for genuine judgment (see `CONTRIBUTING.md`).
   - Run all offline test suites and the skill linter; **report actual output**, don't claim
     green from memory.
   - Run **two independent review rounds** (e.g. `code-review` / `skill-reviewer`) and
     address findings before declaring done.
6. **Handover + lesson** — write the single narrative in `.story/handovers/` and any durable
   learning in `.story/lessons/`. Durable.
7. **Delete the plan** — include the deletion in the feature branch before merge; see the
   rule below. This closes the work loop.
8. **Integrate and clean up automatically** — merge completed work to the default
   branch locally, rerun verification there, then remove the worktree and delete the
   local branch.

## Deleting plans once implemented (required)

When a ticket reaches `complete` and its change is ready to merge to the default branch:

1. Confirm the plan's durable content now lives elsewhere:
   - design decisions → the relevant file in `docs/superpowers/specs/`,
   - what-happened narrative → a `.story/handovers/` entry,
   - reusable learnings → a `.story/lessons/` entry.
2. `git rm docs/superpowers/plans/<that-plan>.md` on the feature branch **before merge**.
3. Reference the deleted plan's filename in the handover so history stays traceable.

Do **not** keep "completed" plans around as documentation — that is what specs, handovers,
and git history are for. If a plan was never merged (abandoned), delete it too and note why
in a handover. A plan with `Status: Complete` sitting in `docs/superpowers/plans/` is a bug
to fix, not a state to preserve.

## Integrating and cleaning up branches/worktrees

After verification, handover/lesson, and plan deletion, do not ask what integration path
to use. This project always uses local merge cleanup:

1. Always merge completed work back to the default branch locally.
2. Rerun the required verification on the merged result.
3. Remove the worktree.
4. Delete the local branch.

Do not offer PR, "keep branch", or "what next?" options for completed work. Always
remove the worktree and delete the local branch after the verified local merge. The
only exception is an explicit user instruction to pause before merge or discard the work.

## Hard rules

- **Never commit a plan to the default branch as a permanent artifact.** Plans live only
  while their ticket is open; keep them in `docs/superpowers/plans/`, and delete before merge.
- **Don't vendor companion tools.** Depend on installed plugins; do not copy their code into
  this tree (see `CONTRIBUTING.md`).
- **Deterministic over non-deterministic** wherever possible; closed-form logic is tested
  code, not prose.
- **Verify before declaring done.** Tests + linter + two reviews, with real output shown.

## Where things live

| Artifact | Path | Lifespan |
|---|---|---|
| Roadmap / phases | `.story/roadmap.json` | durable |
| Tickets | `.story/tickets/` | durable (mark complete) |
| Handovers | `.story/handovers/` | durable |
| Lessons | `.story/lessons/` | durable |
| Specs (design contracts) | `docs/superpowers/specs/` | durable |
| Plans (build scratchpads) | `docs/superpowers/plans/` | **ephemeral — delete before merge** |
| Skills (the product) | `skills/` | the deliverable |

## Tests (run from repo root unless noted)

```bash
python3 tools/skill_lint.py --root .
python3 -m unittest discover -s tools/tests -t tools
(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)
python3 -m unittest discover -s skills/workflow-design-validate/scripts/tests -t skills/workflow-design-validate/scripts
python3 -m unittest discover -s skills/workflow-design-review/scripts/tests -t skills/workflow-design-review/scripts
python3 -m unittest discover -s skills/workflow-design-advise/scripts/tests -t skills/workflow-design-advise/scripts
python3 -m unittest discover -s skills/workflow-document-project/scripts/tests -t skills/workflow-document-project/scripts
python3 -m unittest discover -s skills/workflow-design-visualize/scripts/tests -t skills/workflow-design-visualize/scripts
```
