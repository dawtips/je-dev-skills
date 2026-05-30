"""Deterministic scaffolder: stand up the storybloq + superpowers dev workflow in a project.

Writes the storybloq memory skeleton (`.story/`), the superpowers docs skeleton
(`docs/superpowers/{specs,plans}/`), the tool-neutral working agreement
(`AGENTS.md` + `CLAUDE.md`), and the git ignores for storybloq runtime state.

Pure file scaffolding with no third-party deps; the interactive parts (naming the
project, seeding the first roadmap phase and ticket) are driven by SKILL.md after
this runs. Refuses to clobber existing files unless ``--force`` is given.

Usage:
    python3 init_project.py --name <project> [--root <dir>] [--force] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

TODAY_ENV = "DEV_WORKFLOW_INIT_DATE"  # tests pin the date; falls back to real today.


class InitError(ValueError):
    """Raised when the project cannot be scaffolded safely."""


def slugify(value: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to single hyphens, trim hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _today() -> str:
    pinned = os.environ.get(TODAY_ENV)
    if pinned:
        return pinned
    from datetime import date

    return date.today().isoformat()


def story_config(project: str) -> str:
    config = {
        "features": {
            "handovers": True,
            "issues": True,
            "reviews": True,
            "roadmap": True,
            "tickets": True,
        },
        "language": "generic",
        "project": project,
        "schemaVersion": 1,
        "type": "generic",
        "version": 2,
    }
    return json.dumps(config, indent=2) + "\n"


def story_roadmap(project: str, today: str) -> str:
    roadmap = {
        "blockers": [],
        "date": today,
        "phases": [
            {
                "description": "First slice of real work. Rename and split as the shape "
                "of the project emerges.",
                "id": "foundation",
                "label": "PHASE 0",
                "name": "Foundation",
            }
        ],
        "title": project,
    }
    return json.dumps(roadmap, indent=2) + "\n"


def seed_ticket(project: str, today: str) -> str:
    ticket = {
        "blockedBy": [],
        "createdDate": today,
        "description": "Placeholder seed ticket created by dev-workflow-init. Replace its "
        "title/description with the first real unit of work, or delete it.",
        "id": "T-001",
        "order": 10,
        "phase": "foundation",
        "status": "open",
        "title": f"Bootstrap {project}",
        "type": "chore",
    }
    return json.dumps(ticket, indent=2) + "\n"


STORY_GITIGNORE = "snapshots/\nstatus.json\nsessions/\n"

ROOT_IGNORE_BLOCK = (
    "\n# storybloq runtime state (durable artifacts are tracked; runtime is not)\n"
    ".story/snapshots/\n"
    ".story/sessions/\n"
    ".story/status.json\n"
)

CLAUDE_MD = """# CLAUDE.md

The working agreement for this repo is tool-neutral and lives in `AGENTS.md`. Read and
follow it.

@AGENTS.md

## Project specifics

<!-- Add anything Claude Code needs that is specific to this project: how to run the
app, where the entry points are, environment quirks. Keep durable design in
docs/superpowers/specs/. -->
"""


def agents_md(project: str) -> str:
    return f"""# Working agreement for {project}

This project is built with two companion methodologies. This file is the canonical,
tool-neutral working agreement; Codex reads it directly, and `CLAUDE.md` imports it for
Claude Code.

## The two methodologies and how they combine

- **superpowers** is the *method*: spec -> plan -> implement -> **adversarially verify**.
  It contributes durable **specs** and disposable **plans**.
- **storybloq** (`.story/`) is the *durable memory*: roadmap, tickets, handovers, lessons.

They overlap on exactly one thing -- the narrative of work (a superpowers *plan* and a
storybloq *handover* both describe what was done). Resolve it with one rule:

> **Specs are durable. Plans are disposable. Handovers are the single narrative of record.**

A plan is a working scratchpad for *one* build. When its ticket closes, distill the
plan's durable residue into the spec (if the design changed), a handover (what happened),
and a lesson (what to remember) -- then **delete the plan file**. Plans must never
accumulate on the default branch.

## The loop

For any non-trivial change, work this order:

1. **Roadmap** -- place the work in a phase (`.story/roadmap.json`). Durable.
2. **Ticket** -- open one in `.story/tickets/` with status, phase, and `blockedBy`.
   Durable; mark `complete` when done, never delete.
3. **Spec (only if the design is non-obvious)** -- write a durable design contract in
   `docs/superpowers/specs/`. Skip for mechanical changes.
4. **Plan** -- write the build scratchpad in `docs/superpowers/plans/`. **Ephemeral.**
   Name it `<date>-<ticket>-<slug>.md` and start it with `Status: In progress`.
5. **Implement + adversarially verify** (the superpowers discipline):
   - Build the **deterministic core first**, with offline tests. Reserve the model for
     genuine judgment.
   - Run the test suite; **report actual output**, don't claim green from memory.
   - Run an independent review round and address findings before declaring done.
6. **Handover + lesson** -- write the single narrative in `.story/handovers/` and any
   durable learning in `.story/lessons/`. Durable.
7. **Delete the plan** -- see the rule below. This closes the loop.

## Deleting plans once implemented (required)

When a ticket reaches `complete` **and** its change is merged to the default branch:

1. Confirm the plan's durable content now lives elsewhere:
   - design decisions -> the relevant file in `docs/superpowers/specs/`,
   - what-happened narrative -> a `.story/handovers/` entry,
   - reusable learnings -> a `.story/lessons/` entry.
2. `git rm docs/superpowers/plans/<that-plan>.md`.
3. Reference the deleted plan's filename in the handover so history stays traceable.

Do **not** keep "completed" plans around as documentation -- that is what specs,
handovers, and git history are for. A plan with `Status: Complete` sitting in
`docs/superpowers/plans/` is a bug to fix, not a state to preserve.

## Hard rules

- **Never commit a plan to the default branch as a permanent artifact.** Plans live only
  while their ticket is open; keep them in `docs/superpowers/plans/`, and delete on merge.
- **Don't vendor companion tools.** Depend on installed tools; do not copy their code in.
- **Deterministic over non-deterministic** wherever possible; closed-form logic is tested
  code, not prose.
- **Verify before declaring done.** Tests + a review, with real output shown.

## Where things live

| Artifact | Path | Lifespan |
|---|---|---|
| Roadmap / phases | `.story/roadmap.json` | durable |
| Tickets | `.story/tickets/` | durable (mark complete) |
| Handovers | `.story/handovers/` | durable |
| Lessons | `.story/lessons/` | durable |
| Specs (design contracts) | `docs/superpowers/specs/` | durable |
| Plans (build scratchpads) | `docs/superpowers/plans/` | **ephemeral -- delete on merge** |

## Tests

<!-- Replace with this project's real test/lint commands once they exist. -->
"""


def planned_files(project: str, today: str) -> dict[str, str]:
    """Map of relative-path -> file content for every file this skill writes."""
    return {
        ".story/config.json": story_config(project),
        ".story/roadmap.json": story_roadmap(project, today),
        ".story/.gitignore": STORY_GITIGNORE,
        ".story/tickets/T-001.json": seed_ticket(project, today),
        ".story/handovers/.gitkeep": "",
        ".story/lessons/.gitkeep": "",
        "docs/superpowers/specs/.gitkeep": "",
        "docs/superpowers/plans/.gitkeep": "",
        "AGENTS.md": agents_md(project),
        "CLAUDE.md": CLAUDE_MD,
    }


def _update_root_gitignore(root: Path, dry_run: bool) -> tuple[str | None, str | None]:
    """Ensure the storybloq runtime block is in root .gitignore.

    Returns (path_written, warning). Idempotent: a no-op if the block is already present.
    """
    path = root / ".gitignore"
    rel = ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if ".story/snapshots/" in existing:
        return None, None  # already wired
    new = (existing.rstrip("\n") + "\n" if existing else "") + ROOT_IGNORE_BLOCK
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return rel, None


def init_project(
    project: str,
    root: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    """Scaffold the dev workflow into ``root``. Returns (written_paths, warnings)."""
    name = project.strip()
    if not name:
        raise InitError("project name is empty")
    root_path = Path(root)
    today = _today()
    files = planned_files(name, today)

    # Collision check up front so we never write a partial scaffold.
    if not force:
        clashes = [rel for rel in files if (root_path / rel).exists()]
        if clashes:
            raise InitError(
                "refusing to overwrite existing files (use --force): "
                + ", ".join(sorted(clashes))
            )

    written: list[str] = []
    warnings: list[str] = []
    for rel, content in sorted(files.items()):
        dest = root_path / rel
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        written.append(rel)

    ignore_written, ignore_warn = _update_root_gitignore(root_path, dry_run)
    if ignore_written:
        written.append(ignore_written)
    if ignore_warn:
        warnings.append(ignore_warn)

    return sorted(written), warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Scaffold the storybloq + superpowers dev workflow into a project."
    )
    ap.add_argument("--name", required=True, help="project name (used in config/roadmap)")
    ap.add_argument("--root", default=".", help="target project root (default: cwd)")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    args = ap.parse_args(argv)

    try:
        written, warnings = init_project(
            args.name, args.root, force=args.force, dry_run=args.dry_run
        )
    except InitError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    verb = "would write" if args.dry_run else "wrote"
    for rel in written:
        print(f"{verb}: {rel}")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(f"\n{len(written)} files {verb} | project '{args.name.strip()}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
