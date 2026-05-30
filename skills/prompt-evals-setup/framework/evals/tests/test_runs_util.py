import json
import tempfile
import unittest
from pathlib import Path

from evals.runs_util import case_key, load_json


class TestLoadJson(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            p.write_text(json.dumps({"a": 1}), encoding="utf-8")
            self.assertEqual(load_json(p), {"a": 1})


class TestCaseKey(unittest.TestCase):
    def test_prefers_scenario(self):
        r = {"test_case": {"scenario": "wrestler cutting weight"}}
        self.assertEqual(case_key(r, 0), "wrestler cutting weight")

    def test_falls_back_to_index(self):
        self.assertEqual(case_key({"test_case": {}}, 4), "#4")
        self.assertEqual(case_key({}, 2), "#2")


if __name__ == "__main__":
    unittest.main()
