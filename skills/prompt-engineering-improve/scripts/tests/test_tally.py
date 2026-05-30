import os
import unittest

from improve_step import diagnose_tally, load_output_json

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestTally(unittest.TestCase):
    def test_mandatory_fail_count_uses_score_le_3(self):
        out = load_output_json(os.path.join(FIXTURES, "round00_output.json"))
        tally = diagnose_tally(out["results"])
        # round00 fixture: scores 8,6,3,3 -> two cases <=3.
        self.assertEqual(tally["mandatory_fail_count"], 2)
        self.assertEqual(tally["total_cases"], 4)
        self.assertEqual(tally["mandatory_fail_pct"], 50.0)

    def test_theme_percentages_from_weakness_keywords(self):
        out = load_output_json(os.path.join(FIXTURES, "round00_output.json"))
        tally = diagnose_tally(out["results"])
        themes = tally["theme_pct"]
        # 2 cases mention 'missing required/missing ... content' -> missing_content theme.
        self.assertIn("missing_content", themes)
        self.assertEqual(themes["missing_content"], 50.0)
        # 1 case mentions 'output format inconsistent' -> format_structure theme.
        self.assertIn("format_structure", themes)
        self.assertEqual(themes["format_structure"], 25.0)

    def test_empty_results_is_zeroed(self):
        tally = diagnose_tally([])
        self.assertEqual(tally["mandatory_fail_count"], 0)
        self.assertEqual(tally["total_cases"], 0)
        self.assertEqual(tally["mandatory_fail_pct"], 0.0)
        self.assertEqual(tally["theme_pct"], {})
