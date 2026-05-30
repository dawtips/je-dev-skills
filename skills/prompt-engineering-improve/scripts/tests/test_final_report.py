import json
import os
import tempfile
import unittest

from improve_step import build_final_report, main, extra_criteria_hash, load_loop_state

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _state_with_hash(name, tmpdir):
    src = os.path.join(FIXTURES, name)
    with open(src, encoding="utf-8") as f:
        st = json.load(f)
    st["extra_criteria_hash"] = extra_criteria_hash(st["extra_criteria"])
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f)
    return path


class TestFinalReport(unittest.TestCase):
    def test_trace_best_and_held_out(self):
        state = load_loop_state(os.path.join(FIXTURES, "loopstate_final.json"))
        report = build_final_report(state=state)
        # argmax over [v1=5.0, v2=7.5] -> v2.
        self.assertEqual(report["best_version"], "v2")
        # Round-by-round trace: 2 rounds, baseline delta None, round-01 delta 2.5.
        self.assertEqual(len(report["rounds"]), 2)
        self.assertIsNone(report["rounds"][0]["delta"])
        self.assertEqual(report["rounds"][1]["delta"], 2.5)
        # Trace carries the recorded strings (NOT arithmetic) verbatim.
        self.assertEqual(report["rounds"][1]["technique"], "process steps + multishot examples")
        self.assertEqual(report["rounds"][1]["decision"], "stop:threshold")
        self.assertEqual(report["rounds"][1]["run_dir"], "evals/runs/improve-mealplan-round-01")
        # Resolved loop params stamped in.
        self.assertEqual(report["params"]["max_rounds"], 3)
        # Held-out ran exactly once and its result is recorded (not "skipped").
        self.assertEqual(report["held_out_run_count"], 1)
        self.assertEqual(report["held_out_result"]["average_score"], 7.2)

    def test_held_out_skipped_when_absent(self):
        state = load_loop_state(os.path.join(FIXTURES, "loopstate_final_noheldout.json"))
        report = build_final_report(state=state)
        self.assertEqual(report["held_out_run_count"], 0)
        self.assertEqual(report["held_out_result"], "skipped")

    def test_cli_finalize_writes_final_report(self):
        with tempfile.TemporaryDirectory() as d:
            loopstate = _state_with_hash("loopstate_final.json", d)
            out = os.path.join(d, "final-report.json")
            rc = main([
                "--loop-state", loopstate,
                "--final-report-out", out,
                "--check-freeze",
            ])
            self.assertEqual(rc, 0)  # finalize success -> exit 0
            with open(out, encoding="utf-8") as f:
                report = json.load(f)
        self.assertEqual(report["best_version"], "v2")
        self.assertEqual(report["held_out_run_count"], 1)
        self.assertIn("extra_criteria_hash", report)
        self.assertIn("params", report)

    def test_cli_finalize_freeze_violation_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(FIXTURES, "loopstate_final.json")
            with open(src, encoding="utf-8") as f:
                st = json.load(f)
            st["extra_criteria_hash"] = extra_criteria_hash("a DIFFERENT frozen value")
            loopstate = os.path.join(d, "loopstate.json")
            with open(loopstate, "w", encoding="utf-8") as f:
                json.dump(st, f)
            rc = main([
                "--loop-state", loopstate,
                "--final-report-out", os.path.join(d, "final-report.json"),
                "--check-freeze",
            ])
            self.assertEqual(rc, 2)
