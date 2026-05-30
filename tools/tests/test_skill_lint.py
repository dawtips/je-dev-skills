import tempfile
import unittest
from pathlib import Path

from skill_lint import extract_plugin_root_refs, lint_skill, parse_frontmatter

GOOD = '''---
name: my-skill
description: This skill should be used when the user asks to "do X".
argument-hint: "[arg]"
allowed-tools: Bash, Read
version: 0.1.0
---
# My Skill
Body text referencing ${CLAUDE_PLUGIN_ROOT}/docs/REF.md here.
'''


class TestParseFrontmatter(unittest.TestCase):
    def test_parses_fields_and_body(self):
        fields, body = parse_frontmatter(GOOD)
        self.assertEqual(fields["name"], "my-skill")
        self.assertTrue(fields["description"].startswith("This skill"))
        self.assertIn("Body text", body)

    def test_missing_fence_raises(self):
        with self.assertRaises(ValueError):
            parse_frontmatter("# no frontmatter\n")


class TestExtractRefs(unittest.TestCase):
    def test_finds_and_cleans_trailing_chars(self):
        refs = extract_plugin_root_refs(
            'see `${CLAUDE_PLUGIN_ROOT}/docs/A.md` and ${CLAUDE_PLUGIN_ROOT}/x/y"'
        )
        self.assertIn("docs/A.md", refs)
        self.assertIn("x/y", refs)


def _make_skill(root, name, text, refs_to_create=()):
    d = Path(root) / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    for r in refs_to_create:
        p = Path(root) / r
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    return d


class TestLintSkill(unittest.TestCase):
    def test_good_skill_no_errors(self):
        with tempfile.TemporaryDirectory() as root:
            d = _make_skill(root, "my-skill", GOOD, refs_to_create=["docs/REF.md"])
            issues = lint_skill(d, root)
            self.assertEqual([i for i in issues if i.startswith("ERROR")], [])

    def test_name_mismatch_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            d = _make_skill(root, "wrong-dir", GOOD, refs_to_create=["docs/REF.md"])
            issues = lint_skill(d, root)
            self.assertTrue(any("!= directory" in i for i in issues))

    def test_broken_ref_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            d = _make_skill(root, "my-skill", GOOD)  # REF.md not created
            issues = lint_skill(d, root)
            self.assertTrue(any(i.startswith("ERROR") and "broken" in i for i in issues))

    def test_second_person_description_warns(self):
        text = GOOD.replace(
            'This skill should be used when the user asks to "do X".',
            "Use this skill to do X.",
        )
        with tempfile.TemporaryDirectory() as root:
            d = _make_skill(root, "my-skill", text, refs_to_create=["docs/REF.md"])
            issues = lint_skill(d, root)
            self.assertTrue(any(i.startswith("WARN") and "2nd-person" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
