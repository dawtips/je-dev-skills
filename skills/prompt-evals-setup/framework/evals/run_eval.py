"""Real entrypoint: generate a dataset once, then evaluate against it.

Two execution modes, selected by config.EXECUTION_MODE:

  "in_claude_code" (default, NO API key): measurement is driven by the
      prompt-evals-run skill (it dispatches an execute- and a grade-subagent per
      case, writes per-case verdict JSONs, then runs `python -m evals.aggregate`).
      A synchronous Python function cannot dispatch a subagent, so the `evaluate`
      command here prints that guidance and exits non-zero in this mode.

  "anthropic_api" (keyed headless/CI fallback): the `evaluate` command runs
      PromptEvaluator.run_evaluation in-process with AnthropicClient. Requires
      ANTHROPIC_API_KEY (name in config.API_KEY_ENV) and supports agentic Trajectory.

Prerequisites for the keyed path:
    pip install -r evals/requirements.txt
    export ANTHROPIC_API_KEY=sk-...

Usage:
    python -m evals.run_eval generate                 # build + freeze the dataset (one-time)
    python -m evals.run_eval evaluate [run_label]     # keyed-mode only; see EXECUTION_MODE

Copy this file per project and edit TASK / PROMPT_INPUTS_SPEC / the prompt file /
EXTRA_CRITERIA. The prompt TEXT is a file (PROMPT_FILE), not a Python string.
"""

import sys
from pathlib import Path

from evals import config
from evals.evaluator import AnthropicClient, PromptEvaluator
from evals.evaluator.templates import render
from evals.promptprep import check_placeholders

# --- 1. Describe the task and its closed input set ---------------------------
TASK = "Write a compact 1-day meal plan for one athlete."
PROMPT_INPUTS_SPEC = {
    "height": "Athlete's height in cm",
    "weight": "Athlete's weight in kg",
    "goal": "Goal of the athlete",
}
EXTRA_CRITERIA = "Must include a caloric total and a macro breakdown (protein/carbs/fat)."
# Agentic-only: how the agent should behave (tools, recovery, no needless steps).
# Leave None for single-shot prompts. Wired through to grading in main() below.
PROCESS_CRITERIA = None
DATASET_FILE = f"{config.DATASETS_DIR}/meal_plan.json"
NUM_CASES = 20

# --- Loop parameters (prompt-engineering-improve) ----------------------------
# The loop params live HERE (not config.py) - the existing per-project edit
# surface. This substrate plan preserves them; prompt-engineering-improve owns
# their semantics.
LOOP_PARAMS = {
    "pass_threshold": config.PASS_THRESHOLD,
    "pass_rate_target": 0.80,
    "max_rounds": 3,
    "epsilon": 0.25,
    "diminishing_return_rounds": 2,
    "regression_band": 0.5,
}

# The active prompt is a FILE (Layer 1), not a Python string. Each round writes a
# candidate <name>.vN.md; the chosen candidate is copied into <name>.current.md
# before measuring. run_prompt always renders <name>.current.md.
PROMPT_FILE = f"{config.DATASETS_DIR}/../prompts_under_test/meal_plan.current.md"


# --- 2. Define the prompt under test (KEYED PATH ONLY) -----------------------
def run_prompt(prompt_inputs: dict) -> str:
    """Render the file-backed prompt with the case inputs, call the model, return text.

    Used ONLY on the keyed path (EXECUTION_MODE=anthropic_api). The no-key path
    runs the prompt by subagent dispatch from the prompt-evals-run skill instead.

    For an AGENTIC system, return a Trajectory (see evals.evaluator.Trajectory).
    """
    template = Path(PROMPT_FILE).read_text(encoding="utf-8")
    # Layer-2 glue: fail on a missing placeholder, warn on an unused input, before
    # render()'s own KeyError backstop fires.
    check_placeholders(template, prompt_inputs)
    prompt = render(template, **prompt_inputs)

    executor = AnthropicClient(config.EXECUTOR_MODEL)
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


_IN_CC_GUIDANCE = (
    "EXECUTION_MODE=in_claude_code: 'evaluate' does not run in-process here.\n"
    "A synchronous Python function cannot dispatch a subagent. Run the eval via the\n"
    "prompt-evals-run skill, which dispatches an execute- and grade-subagent per case\n"
    "(session auth, no API key), writes per-case verdict JSONs, then assembles the\n"
    "report with:\n"
    "    python -m evals.aggregate --run-label <label> --verdicts-dir <dir> --dataset "
    f"{DATASET_FILE}\n"
    "To run the keyed in-process loop instead, set EXECUTION_MODE='anthropic_api' in\n"
    "evals/config.py and export your API key."
)


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "evaluate"

    if command == "generate":
        build_evaluator().generate_dataset(
            task_description=TASK,
            prompt_inputs_spec=PROMPT_INPUTS_SPEC,
            num_cases=NUM_CASES,
            output_file=DATASET_FILE,
        )
        return 0

    if command == "evaluate":
        if config.EXECUTION_MODE != "anthropic_api":
            print(_IN_CC_GUIDANCE)
            return 3  # non-zero: not an error, but no in-process run happened
        run_label = argv[2] if len(argv) > 2 else None
        build_evaluator().run_evaluation(
            run_function=run_prompt,
            dataset_file=DATASET_FILE,
            extra_criteria=EXTRA_CRITERIA,
            process_criteria=PROCESS_CRITERIA,
            run_label=run_label,
        )
        return 0

    print(f"unknown command: {command!r} (use 'generate' or 'evaluate')")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
