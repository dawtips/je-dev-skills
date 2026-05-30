import unittest

from evals.criteria_audit import audit_dataset, has_issues


def dataset(cases):
    # cases: list of (scenario, [criteria...])
    return {
        "cases": [
            {"test_case": {}, "scenario": s, "solution_criteria": cr} for s, cr in cases
        ]
    }


class TestAuditDataset(unittest.TestCase):
    def test_subjective_criterion_flagged(self):
        ds = dataset([("a", ["Is engaging and creative"]), ("b", ["Lists three steps"])])
        rep = audit_dataset(ds)
        self.assertEqual(len(rep["subjective"]), 1)
        self.assertIn("engaging", rep["subjective"][0]["criterion"].lower())
        self.assertTrue(has_issues(rep))

    def test_non_discriminating_criterion_flagged(self):
        shared = "Includes a caloric total and macro breakdown"
        ds = dataset([("a", [shared]), ("b", [shared]), ("c", [shared])])
        rep = audit_dataset(ds)
        self.assertEqual(len(rep["non_discriminating"]), 1)
        self.assertEqual(rep["non_discriminating"][0]["count"], 3)

    def test_duplicate_scenarios_flagged(self):
        ds = dataset([("same", ["Lists steps"]), ("same", ["Names a tool"])])
        rep = audit_dataset(ds)
        self.assertIn("same", rep["duplicate_scenarios"])

    def test_clean_dataset_has_no_issues(self):
        ds = dataset([("a", ["Lists three steps"]), ("b", ["Names the API endpoint"])])
        rep = audit_dataset(ds)
        self.assertFalse(has_issues(rep))


if __name__ == "__main__":
    unittest.main()
