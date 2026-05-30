import unittest
from types import SimpleNamespace

from review_blueprint import (
    DIMENSION_NAMES,
    JudgeResponseError,
    ReviewResult,
    call_judge,
    parse_review_payload,
    parse_tool_response,
    review_tool_schema,
)
from tests.fake_client import FakeClient, valid_payload


class TestParseJudgeResponse(unittest.TestCase):
    def test_parse_valid_payload(self):
        result = parse_review_payload(valid_payload())
        self.assertIsInstance(result, ReviewResult)
        self.assertEqual([d.name for d in result.dimensions], DIMENSION_NAMES)
        self.assertEqual(result.dimensions[0].score, 2)
        self.assertEqual(result.judge_verdict, "solid")
        self.assertEqual(result.summary, "The blueprint is usable but has one flagged dimension.")

    def test_rejects_missing_dimension(self):
        payload = valid_payload()
        payload["dimensions"] = payload["dimensions"][:-1]
        with self.assertRaisesRegex(JudgeResponseError, "missing"):
            parse_review_payload(payload)

    def test_rejects_unknown_dimension(self):
        payload = valid_payload()
        payload["dimensions"][0]["name"] = "novelty"
        with self.assertRaisesRegex(JudgeResponseError, "unexpected"):
            parse_review_payload(payload)

    def test_rejects_score_outside_range(self):
        payload = valid_payload({"simplicity": 6})
        with self.assertRaisesRegex(JudgeResponseError, "score"):
            parse_review_payload(payload)

    def test_rejects_boolean_score(self):
        payload = valid_payload()
        payload["dimensions"][0]["score"] = True
        with self.assertRaisesRegex(JudgeResponseError, "score"):
            parse_review_payload(payload)

    def test_rejects_empty_reasoning(self):
        payload = valid_payload()
        payload["dimensions"][0]["reasoning"] = " "
        with self.assertRaisesRegex(JudgeResponseError, "reasoning"):
            parse_review_payload(payload)

    def test_rejects_empty_suggestions(self):
        payload = valid_payload()
        payload["dimensions"][0]["suggestions"] = []
        with self.assertRaisesRegex(JudgeResponseError, "suggestions"):
            parse_review_payload(payload)

    def test_rejects_too_many_suggestions(self):
        payload = valid_payload()
        payload["dimensions"][0]["suggestions"] = ["a", "b", "c", "d"]
        with self.assertRaisesRegex(JudgeResponseError, "suggestions"):
            parse_review_payload(payload)

    def test_parse_tool_response_from_message_object(self):
        payload = valid_payload()
        message = SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name="record_workflow_review", input=payload)]
        )
        self.assertEqual(parse_tool_response(message), payload)

    def test_parse_tool_response_rejects_empty_content(self):
        with self.assertRaisesRegex(JudgeResponseError, "required tool"):
            parse_tool_response(SimpleNamespace(content=[]))

    def test_parse_tool_response_rejects_wrong_tool_name(self):
        message = SimpleNamespace(content=[SimpleNamespace(type="tool_use", name="wrong", input={})])
        with self.assertRaisesRegex(JudgeResponseError, "required tool"):
            parse_tool_response(message)

    def test_parse_tool_response_rejects_non_dict_input(self):
        message = SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name="record_workflow_review", input="bad")]
        )
        with self.assertRaisesRegex(JudgeResponseError, "required tool"):
            parse_tool_response(message)

    def test_tool_schema_requires_all_dimensions(self):
        schema = review_tool_schema()
        self.assertEqual(schema["name"], "record_workflow_review")
        self.assertIn("dimensions", schema["input_schema"]["required"])
        dimension_schema = schema["input_schema"]["properties"]["dimensions"]["items"]["properties"]
        self.assertLessEqual(schema["input_schema"]["properties"]["summary"]["maxLength"], 1200)
        self.assertEqual(dimension_schema["suggestions"]["maxItems"], 3)
        self.assertLessEqual(dimension_schema["reasoning"]["maxLength"], 1200)

    def test_call_judge_uses_tool_choice_and_cacheable_system(self):
        client = FakeClient(valid_payload())
        result = call_judge(client, "system prompt", "user prompt", model="model-x")
        self.assertEqual(result.summary, "The blueprint is usable but has one flagged dimension.")
        call = client.messages.calls[0]
        self.assertEqual(call["model"], "model-x")
        self.assertEqual(call["tool_choice"], {"type": "tool", "name": "record_workflow_review"})
        self.assertEqual(call["tools"][0]["name"], "record_workflow_review")
        self.assertEqual(call["system"][0]["cache_control"], {"type": "ephemeral"})


if __name__ == "__main__":
    unittest.main()
