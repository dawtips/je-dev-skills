"""Stage 1 — dataset generation (ideas + test cases)."""

import json

from evals import config

from .client import LLMClient
from .prompts import SYSTEM_GENERATE, load_prompt
from .schemas import validate_test_case
from .templates import render


def generate_ideas(
    client: LLMClient,
    task_description: str,
    prompt_inputs_spec: dict,
    num_cases: int,
) -> list[str]:
    """Stage 1a — one call returning ``num_cases`` distinct scenario ideas."""
    user = render(
        load_prompt("idea_generation"),
        task_description=task_description,
        prompt_inputs_spec=json.dumps(prompt_inputs_spec, indent=2),
        num_cases=num_cases,
    )
    ideas = client.complete_json(
        system=SYSTEM_GENERATE,
        user=user,
        temperature=config.IDEA_TEMPERATURE,
        tag="ideas",
    )
    if not isinstance(ideas, list) or not all(isinstance(i, str) for i in ideas):
        raise ValueError("idea generation must return a JSON array of strings")
    return ideas


def generate_test_case(
    client: LLMClient,
    task_description: str,
    prompt_inputs_spec: dict,
    scenario: str,
    *,
    retries: int = 1,
) -> dict:
    """Stage 1b — expand one scenario into a full, validated test case."""
    allowed_keys = list(prompt_inputs_spec.keys())
    user = render(
        load_prompt("test_case_generation"),
        task_description=task_description,
        scenario=scenario,
        allowed_keys=json.dumps(allowed_keys),
        prompt_inputs_spec=json.dumps(prompt_inputs_spec, indent=2),
    )

    last_error: Exception | None = None
    for _ in range(retries + 1):
        raw = client.complete_json(
            system=SYSTEM_GENERATE,
            user=user,
            temperature=config.TESTCASE_TEMPERATURE,
            tag="testcase",
        )
        try:
            case = validate_test_case(raw, allowed_keys)
        except ValueError as exc:
            last_error = exc
            continue
        # Framework-injected fields so grading is self-contained (spec Â§3.2).
        case["task_description"] = task_description
        case["scenario"] = scenario
        return case

    raise ValueError(f"test case failed validation after retries: {last_error}")
