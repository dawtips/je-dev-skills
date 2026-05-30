"""Offline tests for the prompt-prep glue (evals/promptprep.py). No API key."""

import logging
import unittest

from evals.promptprep import MissingPlaceholderError, check_placeholders


class TestCheckPlaceholders(unittest.TestCase):
    def test_all_declared_and_used(self):
        report = check_placeholders("Hi {name}, age {age}", {"name": "Ada", "age": "30"})
        self.assertEqual(sorted(report["declared"]), ["age", "name"])
        self.assertEqual(report["unused"], [])
        self.assertEqual(report["missing"], [])

    def test_literal_braces_are_not_placeholders(self):
        # {{ }} escapes are literal braces, not declared placeholders.
        report = check_placeholders('Use {{"k": {v}}}', {"v": "1"})
        self.assertEqual(report["declared"], ["v"])
        self.assertEqual(report["unused"], [])
        self.assertEqual(report["missing"], [])

    def test_repeated_placeholder_reported_once(self):
        report = check_placeholders("{a}-{a}-{b}", {"a": "1", "b": "2"})
        self.assertEqual(sorted(report["declared"]), ["a", "b"])

    def test_unused_input_warns_but_does_not_raise(self):
        with self.assertLogs("evals.promptprep", level="WARNING") as cm:
            report = check_placeholders("Hi {name}", {"name": "Ada", "spurious": "x"})
        self.assertEqual(report["unused"], ["spurious"])
        self.assertEqual(report["missing"], [])
        self.assertTrue(any("spurious" in line for line in cm.output))

    def test_missing_placeholder_raises(self):
        with self.assertRaises(MissingPlaceholderError) as ctx:
            check_placeholders("Hi {name}, you are {role}", {"name": "Ada"})
        self.assertIn("role", str(ctx.exception))

    def test_missing_reported_before_render_keyerror(self):
        # The structured report must surface ALL missing keys, not just the first
        # one render() would raise on.
        try:
            check_placeholders("{a} {b} {c}", {"a": "1"})
            self.fail("expected MissingPlaceholderError")
        except MissingPlaceholderError as exc:
            self.assertIn("b", str(exc))
            self.assertIn("c", str(exc))

    def test_no_auto_sync_return_is_pure_report(self):
        # The helper never mutates prompt_inputs.
        inputs = {"name": "Ada", "extra": "y"}
        with self.assertLogs("evals.promptprep", level="WARNING"):
            check_placeholders("{name}", inputs)
        self.assertEqual(inputs, {"name": "Ada", "extra": "y"})


if __name__ == "__main__":
    unittest.main()
