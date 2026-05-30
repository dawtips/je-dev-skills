import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "prompt-evals-create-dataset" / "SKILL.md"


class TestPromptEvalsCreateDatasetSkill(unittest.TestCase):
    def test_criteria_audit_is_wired_into_dataset_creation(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("python3 -m evals.criteria_audit", text)
        self.assertIn("exit `0`", text)
        self.assertIn("exit `1`", text)
        self.assertIn("exit `2`", text)
        self.assertIn("Do not hand off to `prompt-evals-run`", text)


if __name__ == "__main__":
    unittest.main()
