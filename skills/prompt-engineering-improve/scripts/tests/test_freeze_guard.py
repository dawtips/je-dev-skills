import unittest

from improve_step import extra_criteria_hash, assert_freeze, FreezeViolation


class TestFreezeGuard(unittest.TestCase):
    def test_hash_is_stable_for_same_text(self):
        a = extra_criteria_hash("Must include a caloric total and a macro breakdown.")
        b = extra_criteria_hash("Must include a caloric total and a macro breakdown.")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)  # sha256 hexdigest

    def test_hash_ignores_surrounding_whitespace(self):
        a = extra_criteria_hash("  Must include X.  ")
        b = extra_criteria_hash("Must include X.")
        self.assertEqual(a, b)

    def test_hash_differs_for_different_text(self):
        self.assertNotEqual(extra_criteria_hash("A"), extra_criteria_hash("B"))

    def test_assert_freeze_passes_when_unchanged(self):
        h = extra_criteria_hash("frozen")
        # Returns the hash on success (no raise).
        self.assertEqual(assert_freeze(frozen_hash=h, current_text="frozen"), h)

    def test_assert_freeze_raises_when_changed(self):
        h = extra_criteria_hash("frozen")
        with self.assertRaises(FreezeViolation):
            assert_freeze(frozen_hash=h, current_text="tampered")
