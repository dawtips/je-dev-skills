"""Real entrypoint: generate a dataset once, then evaluate against it.

Prerequisites:
    pip install -r evals/requirements.txt
    export ANTHROPIC_API_KEY=sk-...

Usage:
    python -m evals.run_eval generate    # build + freeze the dataset (one-time)
    python -m evals.run_eval evaluate    # run the prompt under test + grade

Copy this file per project and edit TASK / SPEC / run_prompt / EXTRA_CRITERIA.
"""

import sys

from evals import config
from evals.evaluator import AnthropicClient, PromptEvaluator

# --- 1. Describe the task and its closed input set ---------------------------
TASK = "Write a compact 1-day meal plan for one athlete."
PROMPT_INPUTS_SPEC = {
    "height": "Athlete's height in cm",
    "weight": "Athlete's weight in kg",
    "goal": "Goal of the athlete",
}
EXTRA_CRITERIA = "Must include a caloric total and a macro breakdown (protein/carbs/fat)."
DATASET_FILE = f"{config.DATASETS_DIR}/meal_plan.json"
NUM_CASES = 20


# --- 2. Define the prompt under test -----------------------------------------
def run_prompt(prompt_inputs: dict) -> str:
    """Build the prompt, call the model, return raw text.

    For an AGENTIC system, return a Trajectory instead (see evals.evaluator.Trajectory).
    """
    executor = AnthropicClient(config.EXECUTOR_MODEL)
    prompt = (
        f"{TASK}\n\n"
        f"Height: {prompt_inputs['height']}\n"
        f"Weight: {prompt_inputs['weight']}\n"
        f"Goal: {prompt_inputs['goal']}\n"
    )
    # Reuse the JSON client only for framework calls; here we want raw text, so
    # call the SDK directly. Kept inline to keep this file copy-pasteable.
    resp = executor._client.messages.create(  # noqa: SLF001 (example convenience)
        model=executor.model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def build_evaluator() -> PromptEvaluator:
    return PromptEvaluator(
        client=AnthropicClient(config.GENERATOR_MODEL),
        judge_client=AnthropicClient(config.JUDGE_MODEL),
        max_concurrent_tasks=config.MAX_CONCURRENT_TASKS,
    )


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "evaluate"
    evaluator = build_evaluator()

    if command == "generate":
        evaluator.generate_dataset(
            task_description=TASK,
            prompt_inputs_spec=PROMPT_INPUTS_SPEC,
            num_cases=NUM_CASES,
            output_file=DATASET_FILE,
        )
        return 0

    if command == "evaluate":
        evaluator.run_evaluation(
            run_function=run_prompt,
            dataset_file=DATASET_FILE,
            extra_criteria=EXTRA_CRITERIA,
        )
        return 0

    print(f"unknown command: {command!r} (use 'generate' or 'evaluate')")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
