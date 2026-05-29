import os
import unittest

from validate_blueprint import check_dimensions, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestDimensions(unittest.TestCase):
    def test_valid_minimal_all_accounted(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        gaps, (accounted, total) = check_dimensions(bp)
        self.assertEqual(gaps, [])
        self.assertEqual((accounted, total), (12, 12))

    def test_na_with_rationale_counts_as_accounted(self):
        bp = {"dimensions": {d: {"n/a": "reason"} for d in
                             __import__("validate_blueprint").REQUIRED_DIMENSIONS}}
        gaps, (accounted, total) = check_dimensions(bp)
        self.assertEqual(gaps, [])
        self.assertEqual(accounted, 12)

    def test_blank_dimension_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_unaccounted_dimension.blueprint.md"))
        gaps, (accounted, total) = check_dimensions(bp)
        self.assertTrue(any(g.path == "dimensions.observability" for g in gaps))
        self.assertEqual(accounted, 11)

    def test_missing_dimension_key_is_a_gap(self):
        bp = {"dimensions": {}}
        gaps, _ = check_dimensions(bp)
        self.assertEqual(len(gaps), 12)
