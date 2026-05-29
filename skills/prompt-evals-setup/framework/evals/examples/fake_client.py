"""Offline ``LLMClient`` double for the smoke test.

Routes canned responses by ``tag`` so the full generate -> run -> grade ->
report pipeline executes deterministically with no network or API key. It is
intentionally hardcoded to the meal-plan smoke spec (height/weight/goal) and is
NOT a general-purpose client.
"""

from typing import Any


class FakeLLMClient:
    model = "fake-model"

    def __init__(self, *, num_cases: int = 3, fixed_score: int = 8) -> None:
        self._num_cases = num_cases
        self._fixed_score = fixed_score

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        tag: str = "",
        schema: dict | None = None,
    ) -> Any:
        if tag == "ideas":
            ideas = [
                "A wrestler cutting weight the week before a meet",
                "A vegan marathon runner in peak training",
                "A powerlifter in a lean bulk",
                "A recreational cyclist maintaining weight",
                "A swimmer fueling two-a-day sessions",
            ]
            return ideas[: self._num_cases]

        if tag == "testcase":
            return {
                "prompt_inputs": {
                    "height": "178 cm",
                    "weight": "82 kg",
                    "goal": "Lose fat while preserving muscle",
                },
                "solution_criteria": [
                    "Provides a 1-day meal plan with a caloric total and macro breakdown.",
                ],
            }

        if tag == "grade":
            return {
                "strengths": ["Includes a caloric total and macro breakdown."],
                "weaknesses": ["Per-meal timing could be more specific."],
                "reasoning": "Meets the mandatory structure and the secondary criterion with only minor gaps.",
                "score": self._fixed_score,
            }

        raise ValueError(f"FakeLLMClient received unknown tag: {tag!r}")
