import json
import unittest

from document_project import (
    MAX_INPUT_CHARS,
    DocumentProjectError,
    SynthesisPayloadError,
    build_synthesis_system_prompt,
    call_anthropic_synthesis,
    parse_fenced_json,
    parse_synthesis_payload,
    synthesis_tool_schema,
)
from tests.fake_client import FakeClient, valid_synthesis_payload


class TestSynthesis(unittest.TestCase):
    def test_parse_fenced_json_accepts_one_json_block(self):
        payload = {"x": 1}
        self.assertEqual(parse_fenced_json("```json\n{\"x\": 1}\n```"), payload)

    def test_parse_fenced_json_rejects_missing_or_multiple_blocks(self):
        with self.assertRaisesRegex(SynthesisPayloadError, "expected exactly one fenced json block"):
            parse_fenced_json("{\"x\": 1}")
        with self.assertRaisesRegex(SynthesisPayloadError, "expected exactly one fenced json block"):
            parse_fenced_json("```json\n{}\n```\n```json\n{}\n```")

    def test_parse_synthesis_payload_requires_complete_shape_and_draft_status(self):
        payload = parse_synthesis_payload(valid_synthesis_payload())
        self.assertEqual(payload.blueprint_frontmatter["status"], "draft")
        self.assertEqual(payload.blueprint_yaml["steps"][0]["id"], "inventory")

        broken = valid_synthesis_payload()
        broken["blueprint_yaml"]["status"] = "validated"
        with self.assertRaisesRegex(SynthesisPayloadError, "status must be draft"):
            parse_synthesis_payload(broken)

    def test_tool_schema_and_prompt_name_required_fields(self):
        schema = synthesis_tool_schema()
        prompt = build_synthesis_system_prompt("Prompt text")
        self.assertEqual(schema["name"], "record_workflow_document_project")
        self.assertIn("blueprint_yaml", schema["input_schema"]["required"])
        self.assertIn("Prompt text", prompt)
        self.assertIn("untrusted", prompt.lower())

    def test_anthropic_transport_uses_tool_choice_and_parses_payload(self):
        client = FakeClient(valid_synthesis_payload())
        result = call_anthropic_synthesis(
            client=client,
            inventory={"workflow_name": "fixture-review", "artifacts": []},
            prompt_text="Synthesize safely.",
            model="model-x",
            max_tokens=4000,
        )

        self.assertEqual(result.blueprint_frontmatter["name"], "fixture-review")
        call = client.messages.calls[0]
        self.assertEqual(call["tool_choice"], {"type": "tool", "name": "record_workflow_document_project"})
        self.assertEqual(call["tools"][0]["name"], "record_workflow_document_project")
        self.assertIn("UNTRUSTED_INVENTORY_JSON", call["messages"][0]["content"])

    def test_parse_synthesis_payload_rejects_incomplete_substructure(self):
        broken = valid_synthesis_payload()
        broken["blueprint_prose"]["purpose"] = ""
        with self.assertRaisesRegex(SynthesisPayloadError, "blueprint_prose.purpose"):
            parse_synthesis_payload(broken)

        bad_feedback = valid_synthesis_payload()
        bad_feedback["report_sections"]["feedback"][0]["severity"] = "nope"
        with self.assertRaisesRegex(SynthesisPayloadError, "severity"):
            parse_synthesis_payload(bad_feedback)

    def test_anthropic_transport_rejects_oversize_payload(self):
        client = FakeClient(valid_synthesis_payload())
        huge = {"blob": "x" * (MAX_INPUT_CHARS + 10)}
        with self.assertRaises(DocumentProjectError):
            call_anthropic_synthesis(client=client, inventory=huge, prompt_text="p", model="m")


if __name__ == "__main__":
    unittest.main()
