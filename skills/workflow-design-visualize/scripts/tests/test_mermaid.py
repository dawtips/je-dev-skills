import os
import unittest

from visualize_blueprint import load_blueprint, render_mermaid

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _bp(name):
    return load_blueprint(os.path.join(FIXTURES, name))


MINIMAL_EXPECTED = """flowchart TD
    do_thing["do_thing<br/>deterministic"]
    classDef deterministic fill:#dbeafe,stroke:#1e3a8a,color:#0b1324;
    class do_thing deterministic;"""

MULTI_EXPECTED = """flowchart TD
    validate_inputs["validate_inputs<br/>deterministic"]
    plan("plan<br/>agentic")
    fan_out("fan_out<br/>agentic · parallelize")
    emit["emit<br/>deterministic"]
    emit__gate{{"explicit gate"}}
    validate_inputs --> plan
    plan --> fan_out
    fan_out --> emit
    emit --> emit__gate
    subgraph sg_subagents["Subagents (delegated)"]
    worker(["worker<br/>haiku/low"])
    end
    classDef deterministic fill:#dbeafe,stroke:#1e3a8a,color:#0b1324;
    classDef agentic fill:#fde68a,stroke:#92400e,color:#0b1324;
    classDef gate fill:#fecaca,stroke:#991b1b,color:#0b1324;
    classDef subagent fill:#e9d5ff,stroke:#6b21a8,color:#0b1324;
    class validate_inputs,emit deterministic;
    class plan,fan_out agentic;
    class emit__gate gate;
    class worker subagent;"""


class TestRenderMermaid(unittest.TestCase):
    def test_minimal_golden(self):
        self.assertEqual(render_mermaid(_bp("minimal.blueprint.md")), MINIMAL_EXPECTED)

    def test_multi_golden(self):
        self.assertEqual(render_mermaid(_bp("multi.blueprint.md")), MULTI_EXPECTED)

    def test_deterministic_same_bytes(self):
        bp = _bp("multi.blueprint.md")
        self.assertEqual(render_mermaid(bp), render_mermaid(bp))

    def test_empty_blueprint_placeholder(self):
        out = render_mermaid({})
        self.assertEqual(out, 'flowchart TD\n    empty["(no steps defined)"]')

    def test_dup_ids_deduped_and_escaped(self):
        out = render_mermaid(_bp("dup_ids.blueprint.md"))
        self.assertIn('    step["step<br/>deterministic"]', out)
        self.assertIn('    step__2("step<br/>agentic")', out)
        self.assertIn("    step --> step__2", out)
        # third step id sanitized to a unique node, label fully escaped
        self.assertIn("&#91;id&#93;", out)
        self.assertIn("&amp;", out)
        self.assertIn("&lt;stuff&gt;", out)
        # all three step nodes are distinct ids (no collision)
        self.assertIn("    step__2 --> ", out)

    def test_gate_on_non_last_step_sits_between(self):
        bp = {"steps": [
            {"id": "a", "kind": "deterministic", "pattern": "none", "approval_gate": "notify"},
            {"id": "b", "kind": "deterministic", "pattern": "none"},
        ]}
        out = render_mermaid(bp)
        self.assertIn('    a__gate{{"notify gate"}}', out)
        self.assertIn("    a --> a__gate", out)
        self.assertIn("    a__gate --> b", out)


if __name__ == "__main__":
    unittest.main()
