"""Data contracts for the framework.

These shapes are the stable interface (see spec Â§3). The agentic types
(``Step``/``Trajectory``) are the extension layer over single-shot prompts:
a single-shot ``run_function`` returns ``str``; an agentic one returns a
``Trajectory``. The framework normalizes a bare string into a steps-less
``Trajectory`` so both paths share one grading pipeline.
"""

from dataclasses import dataclass, field
from typing import Any


# --- Agentic contract --------------------------------------------------------
@dataclass
class Step:
    """One step in an agent trajectory: an assistant turn or a tool call/result."""

    role: str  # "assistant" | "tool"
    content: str = ""
    tool_name: str | None = None
    tool_input: Any = None
    tool_output: Any = None

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
        }


@dataclass
class Trajectory:
    """The result of running the system under test for one test case."""

    final_output: str
    steps: list[Step] = field(default_factory=list)

    @property
    def is_agentic(self) -> bool:
        return bool(self.steps)

    def to_dict(self) -> dict:
        return {
            "final_output": self.final_output,
            "steps": [s.to_dict() for s in self.steps],
        }


def normalize_trajectory(result: Any) -> Trajectory:
    """Coerce a ``run_function`` return value into a ``Trajectory``."""
    if isinstance(result, Trajectory):
        return result
    if isinstance(result, str):
        return Trajectory(final_output=result, steps=[])
    raise TypeError(
        "run_function must return a str (single-shot) or a Trajectory (agentic); "
        f"got {type(result).__name__}"
    )


# --- Test-case validation ----------------------------------------------------
def validate_test_case(case: dict, allowed_keys: list[str]) -> dict:
    """Validate a generated test case against the closed key set (spec Â§3.2)."""
    if not isinstance(case, dict):
        raise ValueError(f"Test case must be an object, got {type(case).__name__}")

    inputs = case.get("prompt_inputs")
    if not isinstance(inputs, dict):
        raise ValueError("Test case missing object field 'prompt_inputs'")

    got = set(inputs.keys())
    allowed = set(allowed_keys)
    if got != allowed:
        missing = allowed - got
        extra = got - allowed
        raise ValueError(
            "prompt_inputs keys violate the closed key set. "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )

    criteria = case.get("solution_criteria")
    if not isinstance(criteria, list) or not (1 <= len(criteria) <= 4):
        raise ValueError("solution_criteria must be a list of 1-4 items")
    if not all(isinstance(c, str) and c.strip() for c in criteria):
        raise ValueError("each solution_criteria item must be a non-empty string")

    return case


def validate_verdict(verdict: dict) -> dict:
    """Validate a judge verdict and clamp the score to 1-10."""
    if not isinstance(verdict, dict):
        raise ValueError("judge verdict must be an object")
    score = verdict.get("score")
    if not isinstance(score, (int, float)):
        raise ValueError("judge verdict missing numeric 'score'")
    verdict["score"] = max(1, min(10, int(round(score))))
    verdict.setdefault("reasoning", "")
    verdict.setdefault("strengths", [])
    verdict.setdefault("weaknesses", [])
    return verdict
