import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from evals import run_eval


class TestRunEvalCli(unittest.TestCase):
    def run_evaluate_variance(self, group_label: str, k: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with (
            patch.object(run_eval.config, "EXECUTION_MODE", "anthropic_api"),
            patch.object(run_eval, "run_k_variance") as run_k_variance,
            redirect_stdout(stdout),
        ):
            result = run_eval.main(["run_eval.py", "evaluate-variance", group_label, k])
        run_k_variance.assert_not_called()
        return result, stdout.getvalue()

    def test_evaluate_variance_rejects_non_integer_k_without_running(self):
        result, stdout = self.run_evaluate_variance("group", "nope")

        self.assertEqual(result, 2)
        self.assertIn("error: <k> must be an integer >= 2", stdout)

    def test_evaluate_variance_rejects_k_less_than_two_without_running(self):
        result, stdout = self.run_evaluate_variance("group", "1")

        self.assertEqual(result, 2)
        self.assertIn("K-run variance requires k >= 2", stdout)

    def test_evaluate_variance_rejects_path_like_group_label_without_running(self):
        result, stdout = self.run_evaluate_variance("group/path", "2")

        self.assertEqual(result, 2)
        self.assertIn("group_label must be a non-empty run label, not a path", stdout)


if __name__ == "__main__":
    unittest.main()
