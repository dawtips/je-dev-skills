from types import SimpleNamespace


def valid_payload(score_overrides=None):
    scores = {
        "determinism_classification": 2,
        "simplicity": 4,
        "subagent_contracts": 3,
        "rubric_quality": 4,
        "outcome_testability": 5,
        "na_honesty": 3,
        "internal_consistency": 4,
    }
    scores.update(score_overrides or {})
    return {
        "dimensions": [
            {
                "name": name,
                "score": score,
                "reasoning": f"Reasoning for {name} cites steps[0].",
                "suggestions": [f"Improve {name}."],
            }
            for name, score in scores.items()
        ],
        "summary": "The blueprint is usable but has one flagged dimension.",
        "overall_verdict": "solid",
    }


class FakeMessages:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="tool_use", name="record_workflow_review", input=self.payload)
        return SimpleNamespace(content=[block])


class FakeClient:
    def __init__(self, payload=None):
        self.messages = FakeMessages(payload if payload is not None else valid_payload())


class RaisingMessages:
    def create(self, **kwargs):
        raise RuntimeError("rate limit")


class RaisingClient:
    def __init__(self):
        self.messages = RaisingMessages()
