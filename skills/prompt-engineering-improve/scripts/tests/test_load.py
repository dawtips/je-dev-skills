import json
import os
import unittest

from improve_step import load_output_json, load_loop_state

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestLoad(unittest.TestCase):
    def test_load_output_json_returns_summary_and_results(self):
        out = load_output_json(os.path.join(FIXTURES, "round00_output.json"))
        self.assertEqual(out["summary"]["average_score"], 5.0)
        self.assertEqual(len(out["results"]), 4)

    def test_load_output_json_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_output_json(os.path.join(FIXTURES, "nope.json"))

    def test_load_output_json_missing_summary_raises_valueerror(self):
        path = os.path.join(FIXTURES, "_bad.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"results": []}, f)
        try:
            with self.assertRaises(ValueError):
                load_output_json(path)
        finally:
            os.remove(path)

    def test_load_loop_state_returns_params_and_rounds(self):
        st = load_loop_state(os.path.join(FIXTURES, "loopstate_round00.json"))
        self.assertEqual(st["params"]["max_rounds"], 3)
        self.assertEqual(st["rounds"], [])
