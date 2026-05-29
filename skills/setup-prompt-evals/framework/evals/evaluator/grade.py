"""Stage 3 — LLM-as-judge grading (single-shot and agentic)."""

import json

from evals import config

from .client import LLMClient
from .prompts import SYSTEM_JUDGE, load_prompt
from .run import format_transcript
from .schemas import Trajectory, validate_verdict

_NONE = "None (no mandatory criteria)"


def grade(
    judge: LLMClient,
    test_case: dict,
    trajectory: Trajectory,
    *,
    extra_criteria: str | None = None,
    process_criteria: str | None = None,
) -> dict:
    """Grade one ``(test_case, trajectory)`` pair. Returns the full verdict
    ``{strengths, weaknesses, reasoning, score}`` (score clamped to 1-10)."""
    common = dict(
        task_description=test_case["task_description"],
        prompt_inputs=json.dumps(test_case["prompt_inputs"], indent=2),
        solution_criteria=json.dumps(test_case["solution_criteria"], indent=2),
        extra_criteria=extra_criteria or _NONE,
        output=trajectory.final_output,
    )

    if trajectory.is_agentic:
        user = render_grading(
            "trajectory_grading",
            common,
            transcript=format_transcript(trajectory),
            process_criteria=process_criteria or "None",
        )
    else:
        user = render_grading("grading", common)

    verdict = judge.complete_json(
        system=SYSTEM_JUDGE,
        user=user,
        temperature=config.GRADING_TEMPERATURE,
        tag="grade",
    )
    return validate_verdict(verdict)


def render_grading(name: str, common: dict, **extra: object) -> str:
    from .templates import render

    return render(load_prompt(name), **common, **extra)
