import json
import os
import tempfile
import unittest

from improve_step import main, extra_criteria_hash

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _loopstate_with_hash(tmpdir):
    """Copy loopstate_round01.json into tmpdir with the real EXTRA_CRITERIA hash."""
    src = os.path.join(FIXTURES, "loopstate_round01.json")
    with open(src, encoding="utf-8") as f:
        st = json.load(f)
    st["extra_criteria_hash"] = extra_criteria_hash(st["extra_criteria"])
    path = os.path.join(tmpdir, "loopstate.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f)
    return path


class TestCli(unittest.TestCase):
    def test_round01_improvement_writes_delta_and_exits_stop_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            loopstate = _loopstate_with_hash(d)
            delta_out = os.path.join(d, "delta.json")
            rc = main([
                "--output-json", os.path.join(FIXTURES, "round01_output.json"),
                "--loop-state", loopstate,
                "--delta-out", delta_out,
                "--check-freeze",
            ])
            # round01 avg 7.5 >= pass_threshold 7 -> stop:threshold -> exit 1.
            self.assertEqual(rc, 1)
            with open(delta_out, encoding="utf-8") as f:
                payload = json.load(f)
        self.assertEqual(payload["delta"], 2.5)          # 7.5 - 5.0
        self.assertEqual(payload["best"]["version"], "v2")
        self.assertEqual(payload["verdict"]["decision"], "stop")
        self.assertEqual(payload["verdict"]["rule"], "threshold")
        self.assertEqual(payload["tally"]["mandatory_fail_count"], 0)
        self.assertIn("params", payload)                 # resolved params stamped in
        self.assertIn("extra_criteria_hash", payload)

    def test_continue_exits_zero(self):
        # round00 baseline alone (avg 5.0, no prior) -> continue -> exit 0.
        with tempfile.TemporaryDirectory() as d:
            rc = main([
                "--output-json", os.path.join(FIXTURES, "round00_output.json"),
                "--loop-state", os.path.join(FIXTURES, "loopstate_round00.json"),
                "--delta-out", os.path.join(d, "delta.json"),
            ])
            self.assertEqual(rc, 0)

    def test_freeze_violation_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(FIXTURES, "loopstate_round01.json")
            with open(src, encoding="utf-8") as f:
                st = json.load(f)
            st["extra_criteria_hash"] = extra_criteria_hash("a DIFFERENT frozen value")
            loopstate = os.path.join(d, "loopstate.json")
            with open(loopstate, "w", encoding="utf-8") as f:
                json.dump(st, f)
            rc = main([
                "--output-json", os.path.join(FIXTURES, "round01_output.json"),
                "--loop-state", loopstate,
                "--delta-out", os.path.join(d, "delta.json"),
                "--check-freeze",
            ])
            self.assertEqual(rc, 2)

    def test_bad_output_json_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            rc = main([
                "--output-json", os.path.join(FIXTURES, "does_not_exist.json"),
                "--loop-state", os.path.join(FIXTURES, "loopstate_round00.json"),
                "--delta-out", os.path.join(d, "delta.json"),
            ])
            self.assertEqual(rc, 2)
