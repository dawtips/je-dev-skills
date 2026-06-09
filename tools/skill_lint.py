"""Deterministic linter for this repo's own skills (dev tooling, offline, zero-dep).

Dogfoods the skill conventions the repo expects (see CONTRIBUTING.md) and guards
against regressions a human review would miss — most valuably, a broken
``${CLAUDE_PLUGIN_ROOT}`` reference (the cross-skill coupling risk flagged in the
prompt-engineering spec §7). Mirrors workflow-design-validate's structure: small,
one-concern-per-function, unit-tested.

Checks per skill (ERROR fails the lint; WARN is advisory):
- ERROR: no SKILL.md / unparseable frontmatter / missing ``name`` or ``description``.
- ERROR: ``name`` frontmatter != the skill directory name.
- ERROR: a ``${CLAUDE_PLUGIN_ROOT}/...`` reference that does not exist on disk.
- WARN:  ``description`` opens 2nd-person ("Use this skill...") instead of the repo's
         third-person "This skill should be used when..." convention.
- WARN:  a recommended frontmatter field (argument-hint, allowed-tools, version) is absent.
- WARN:  SKILL.md body exceeds ~2000 words (progressive-disclosure smell).

Note: body 2nd-person prose is intentionally NOT linted — Anthropic's own skill-creator
endorses the conversational "explain the why" voice, so a hard rule there would be wrong.

Usage: ``python3 tools/skill_lint.py [--root .]``  (exit 0 = no errors, 1 = errors).
"""

import argparse
import re
import sys
from pathlib import Path

RECOMMENDED_FIELDS = ("argument-hint", "allowed-tools", "version")
SECOND_PERSON_OPENERS = ("use this", "load ", "load this")
BODY_WORD_WARN = 2000

_REF_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s)`\"']*)")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md into (frontmatter fields, body). Flat ``key: value`` only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter (file must start with '---')")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("unterminated YAML frontmatter (no closing '---')")
    fields = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields, "\n".join(lines[end + 1:])


def extract_plugin_root_refs(text: str) -> list[str]:
    """Return the relative paths referenced via ``${CLAUDE_PLUGIN_ROOT}/<path>``."""
    refs = []
    for m in _REF_RE.finditer(text):
        path = m.group(1).rstrip(".,;:\"'`)")
        if path:
            refs.append(path)
    return refs


def lint_skill(skill_dir, plugin_root) -> list[str]:
    """Lint one skill directory; return a list of ``ERROR:``/``WARN:`` strings."""
    skill_dir, plugin_root = Path(skill_dir), Path(plugin_root)
    name_tag = skill_dir.name
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return [f"ERROR: {name_tag}: no SKILL.md"]
    text = md.read_text(encoding="utf-8")
    try:
        fields, body = parse_frontmatter(text)
    except ValueError as e:
        return [f"ERROR: {name_tag}: {e}"]

    issues = []
    name = fields.get("name")
    if not name:
        issues.append(f"ERROR: {name_tag}: frontmatter missing 'name'")
    elif name != skill_dir.name:
        issues.append(f"ERROR: {name_tag}: name '{name}' != directory '{skill_dir.name}'")

    desc = fields.get("description")
    if not desc:
        issues.append(f"ERROR: {name_tag}: frontmatter missing 'description'")
    elif desc.lower().lstrip("\"'").startswith(SECOND_PERSON_OPENERS):
        issues.append(
            f"WARN: {name_tag}: description opens 2nd-person; prefer "
            "'This skill should be used when...'"
        )

    for field in RECOMMENDED_FIELDS:
        if field not in fields:
            issues.append(f"WARN: {name_tag}: frontmatter missing recommended '{field}'")

    for ref in extract_plugin_root_refs(text):
        if not (plugin_root / ref).exists():
            issues.append(f"ERROR: {name_tag}: broken ${{CLAUDE_PLUGIN_ROOT}} ref: {ref}")

    words = len(body.split())
    if words > BODY_WORD_WARN:
        issues.append(
            f"WARN: {name_tag}: SKILL.md body is {words} words "
            f"(>{BODY_WORD_WARN}; consider progressive disclosure)"
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint this repo's skills/*/SKILL.md.")
    ap.add_argument("--root", default=".", help="plugin root (default: current dir)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    skill_dirs = sorted(p.parent for p in root.glob("skills/*/SKILL.md"))
    if not skill_dirs:
        print(f"no skills found under {root}/skills/*/SKILL.md", file=sys.stderr)
        return 2

    all_issues = []
    for d in skill_dirs:
        issues = lint_skill(d, root)
        all_issues.extend(issues)
        for i in issues:
            print(i)

    errors = sum(1 for i in all_issues if i.startswith("ERROR"))
    warns = sum(1 for i in all_issues if i.startswith("WARN"))
    print(f"\n{len(skill_dirs)} skills | {errors} errors | {warns} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
