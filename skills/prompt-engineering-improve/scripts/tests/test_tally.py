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

    def test_fabrication_and_filler_themes_detected(self):
        results = [
            {"score": 3, "verdict": {"weaknesses": ["fabricated a pain point not in the input"]}},
            {"score": 4, "verdict": {"weaknesses": ["invented a statistic the source does not support"]}},
            {"score": 6, "verdict": {"weaknesses": ["opens with filler boilerplate"]}},
            {"score": 8, "verdict": {"weaknesses": []}},
        ]
        tally = diagnose_tally(results)
        themes = tally["theme_pct"]
        # Two cases describe added/unsupported content -> fabrication theme.
        self.assertIn("fabrication", themes)
        self.assertEqual(themes["fabrication"], 50.0)
        # 'filler'/'boilerplate' is tallied under tone_style.
        self.assertIn("tone_style", themes)
        self.assertEqual(themes["tone_style"], 25.0)
        # 'hallucinat*' now counts as fabrication, not reasoning.
        hallu = diagnose_tally([{"score": 3, "verdict": {"weaknesses": ["hallucinated a quote"]}}])
        self.assertIn("fabrication", hallu["theme_pct"])
        self.assertNotIn("reasoning", hallu["theme_pct"])

    def test_unsupported_phrasing_is_left_to_judgment_not_auto_tallied(self):
        # Precision-over-recall: the deterministic flag fires only on added-content verbs.
        # Ambiguous 'unsupported <noun>' phrasing is NOT auto-tallied (it equally describes a
        # §1 criteria problem) - it is left to the model's judgment, the documented backstop.
        for w in ["unsupported reasoning on the hard case",
                  "unsupported formatting choice; sections out of order",
                  "unsupported claim about revenue",
                  "criteria requires unsupported content not in the input"]:
            themes = diagnose_tally([{"score": 5, "verdict": {"weaknesses": [w]}}])["theme_pct"]
            self.assertNotIn("fabrication", themes, msg=w)

    def test_fabrication_keywords_avoid_common_substring_collisions(self):
        # Composition / creative-writing phrasings must NOT tally as fabrication.
        for w in ["made up of too many bullet points",
                  "the fictional setting is inconsistent across scenes",
                  "list is made up of redundant items"]:
            themes = diagnose_tally([{"score": 6, "verdict": {"weaknesses": [w]}}])["theme_pct"]
            self.assertNotIn("fabrication", themes, msg=w)
        # genuine added-content phrasings still fire, across invent* morphology + made-up <noun>.
        for w in ["invented a statistic", "fabricated a quote", "hallucinated a citation",
                  "inventing a statistic", "invents facts", "invent a citation",
                  "made up a quote", "made-up number"]:
            themes = diagnose_tally([{"score": 3, "verdict": {"weaknesses": [w]}}])["theme_pct"]
            self.assertIn("fabrication", themes, msg=w)
        # 'inventory' shares the 'invent' stem but is not fabrication (word boundary).
        themes = diagnose_tally([{"score": 6, "verdict": {"weaknesses": ["inventory list is wrong"]}}])["theme_pct"]
        self.assertNotIn("fabrication", themes)

    def test_negated_or_guardrail_context_is_not_fabrication(self):
        # A fabrication stem in a negation / guardrail-discussion context is not an actual
        # added-content finding and must not tally (it is high-priority, so a false hit
        # misroutes the loop).
        for w in ["no evidence of fabrication in the output",
                  "missing anti-fabrication guardrail",
                  "does not forbid inventing facts",
                  "did not fabricate anything",
                  "no invented statistics"]:
            themes = diagnose_tally([{"score": 6, "verdict": {"weaknesses": [w]}}])["theme_pct"]
            self.assertNotIn("fabrication", themes, msg=w)
        # a real finding in the same sentence as the word 'not' (after the verb) still fires.
        themes = diagnose_tally([{"score": 3, "verdict": {"weaknesses": ["fabricated a quote, not paraphrased"]}}])["theme_pct"]
        self.assertIn("fabrication", themes)

    def test_criteria_problem_phrasing_is_not_fabrication(self):
        # "not in the input/source" describes an IMPOSSIBLE case (criteria problem, route to
        # dataset repair per diagnosis.md §1), NOT model-added content. Must not tally as
        # fabrication, which is high-priority and would misroute the loop to Rung 3.
        for w in ["criteria expects market-size details not in the input",
                  "requires sources not in the source documents",
                  "judge wants data not in the input case",
                  # 'unsupported <noun>' inside a criteria/rubric framing = §1 dataset problem.
                  "criteria requires unsupported content not in the input",
                  "rubric demands unsupported sources the case lacks",
                  "the judge expects an unsupported citation"]:
            themes = diagnose_tally([{"score": 3, "verdict": {"weaknesses": [w]}}])["theme_pct"]
            self.assertNotIn("fabrication", themes, msg=w)
        # but a STRONG added-content verb is fabrication even in a criteria sentence.
        themes = diagnose_tally([{"score": 3, "verdict": {"weaknesses": ["the judge says the model fabricated a quote"]}}])["theme_pct"]
        self.assertIn("fabrication", themes)

    def test_empty_results_is_zeroed(self):
        tally = diagnose_tally([])
        self.assertEqual(tally["mandatory_fail_count"], 0)
        self.assertEqual(tally["total_cases"], 0)
        self.assertEqual(tally["mandatory_fail_pct"], 0.0)
        self.assertEqual(tally["theme_pct"], {})
