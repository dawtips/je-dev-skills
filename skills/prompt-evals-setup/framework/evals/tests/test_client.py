import unittest

from evals.evaluator.client import _rejects_sampling_params


class RejectsSamplingParamsTest(unittest.TestCase):
    def test_opus_4_7_plus_reject_sampling(self):
        for model in ("claude-opus-4-7", "claude-opus-4-8", "claude-opus-4-9", "claude-opus-4-10"):
            self.assertTrue(_rejects_sampling_params(model), model)

    def test_opus_4_6_and_earlier_keep_sampling(self):
        for model in ("claude-opus-4-1", "claude-opus-4-5", "claude-opus-4-6"):
            self.assertFalse(_rejects_sampling_params(model), model)

    def test_dated_suffix_uses_minor_version(self):
        self.assertTrue(_rejects_sampling_params("claude-opus-4-8-20260101"))
        self.assertFalse(_rejects_sampling_params("claude-opus-4-6-20251101"))

    def test_bare_dated_snapshot_is_opus_4_0_and_keeps_sampling(self):
        # claude-opus-4-20250514 is Opus 4.0 (no minor segment); the trailing date
        # must not be read as a minor version.
        self.assertFalse(_rejects_sampling_params("claude-opus-4-20250514"))
        self.assertFalse(_rejects_sampling_params("claude-opus-4-1-20250805"))

    def test_non_opus_and_unparseable_keep_sampling(self):
        for model in (
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            "claude-opus-4-latest",
            "gpt-4",
        ):
            self.assertFalse(_rejects_sampling_params(model), model)


if __name__ == "__main__":
    unittest.main()
