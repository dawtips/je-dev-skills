import os
import unittest

from validate_blueprint import validate, main, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestValidateAndCli(unittest.TestCase):
    def test_valid_minimal_validates_clean(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        gaps, (accounted, total) = validate(bp)
        self.assertEqual(gaps, [])
        self.assertEqual((accounted, total), (12, 12))

    def test_main_returns_zero_on_valid(self):
        rc = main([os.path.join(FIXTURES, "valid_minimal.blueprint.md")])
        self.assertEqual(rc, 0)

    def test_main_returns_one_on_gaps(self):
        rc = main([os.path.join(FIXTURES, "broken_missing_rationale.blueprint.md")])
        self.assertEqual(rc, 1)

    def test_main_returns_two_on_unreadable(self):
        rc = main([os.path.join(FIXTURES, "does_not_exist.blueprint.md")])
        self.assertEqual(rc, 2)

    def test_main_returns_two_on_non_mapping_yaml(self):
        # A yaml block that parses to None/list/scalar is malformed input,
        # not a gap report — it must exit 2, not crash with AttributeError.
        rc = main([os.path.join(FIXTURES, "broken_nondict.blueprint.md")])
        self.assertEqual(rc, 2)
