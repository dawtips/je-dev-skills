import os
import unittest

from visualize_blueprint import load_blueprint, render_step_table, render_subagent_table

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestStepTable(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(render_step_table([]), "_No steps defined._")

    def test_header_and_rows(self):
        steps = load_blueprint(os.path.join(FIXTURES, "multi.blueprint.md"))["steps"]
        out = render_step_table(steps)
        self.assertIn("| id | kind | pattern | gate | side-effecting | reversible | termination |", out)
        self.assertIn("| validate_inputs | deterministic | none |  | no | no |  |", out)
        self.assertIn("| fan_out | agentic | parallelize |  |  |  | all done or timeout |", out)
        self.assertIn("| emit | deterministic | none | explicit | yes | yes |  |", out)

    def test_escapes_pipe_and_newline(self):
        out = render_step_table([{"id": "x", "termination": "a | b\nc"}])
        self.assertIn("a \\| b c", out)


class TestSubagentTable(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(render_subagent_table([]), "_No delegated subagents._")

    def test_joins_tools_list(self):
        subs = load_blueprint(os.path.join(FIXTURES, "multi.blueprint.md"))["subagents"]
        out = render_subagent_table(subs)
        self.assertIn("| id | model | effort | objective | output_format | tools | boundaries |", out)
        self.assertIn("| worker | haiku | low | do one item | JSON | web_search, web_fetch | one item only |", out)


if __name__ == "__main__":
    unittest.main()
