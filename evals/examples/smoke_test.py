"""Offline end-to-end smoke test.

Runs the full pipeline (generate -> run -> grade -> report) with a fake client,
exercising BOTH the single-shot and agentic grading paths. No network/API key.

    python -m evals.examples.smoke_test

Exits non-zero on failure so it can gate a local check.
"""

import sys
from pathlib import Path

from evals.evaluator import PromptEvaluator, Step, Trajectory
from evals.examples.fake_client import FakeLLMClient

TASK = "Write a compact 1-day meal plan for one athlete."
SPEC = {
    "height": "Athlete's height in cm",
    "weight": "Athlete's weight in kg",
    "goal": "Goal of the athlete",
}
EXTRA = "Must include a caloric total and a macro breakdown (protein/carbs/fat)."
NUM_CASES = 3


def run_prompt(prompt_inputs: dict) -> str:
    """Single-shot system under test (canned, offline)."""
    return (
        f"1-Day Meal Plan ({prompt_inputs['goal']})\n"
        f"Athlete: {prompt_inputs['height']}, {prompt_inputs['weight']}\n"
        "Total: 2,400 kcal | Protein 180g / Carbs 240g / Fat 70g\n"
        "- Breakfast: oats + whey + berries\n"
        "- Lunch: chicken, rice, greens\n"
        "- Dinner: salmon, potatoes, salad"
    )


def run_agent(prompt_inputs: dict) -> Trajectory:
    """Agentic system under test (canned trajectory, offline)."""
    final = run_prompt(prompt_inputs)
    return Trajectory(
        final_output=final,
        steps=[
            Step(role="assistant", content="I'll compute calorie needs, then plan meals."),
            Step(
                role="tool",
                tool_name="calorie_calculator",
                tool_input={"weight": prompt_inputs["weight"], "goal": prompt_inputs["goal"]},
                tool_output={"kcal": 2400},
            ),
            Step(role="assistant", content="Building the plan around 2,400 kcal."),
        ],
    )


def main() -> int:
    evaluator = PromptEvaluator(
        client=FakeLLMClient(num_cases=NUM_CASES),
        max_concurrent_tasks=3,
    )

    dataset_file = "evals/datasets/smoke.json"
    evaluator.generate_dataset(
        task_description=TASK,
        prompt_inputs_spec=SPEC,
        num_cases=NUM_CASES,
        output_file=dataset_file,
    )

    single = evaluator.run_evaluation(
        run_function=run_prompt,
        dataset_file=dataset_file,
        extra_criteria=EXTRA,
        run_label="smoke-single-shot",
    )
    agentic = evaluator.run_evaluation(
        run_function=run_agent,
        dataset_file=dataset_file,
        extra_criteria=EXTRA,
        process_criteria="Calls a calorie tool before producing the plan.",
        run_label="smoke-agentic",
    )

    # Assertions: the pipeline produced artifacts and well-formed summaries.
    ok = True
    for name, result in (("single-shot", single), ("agentic", agentic)):
        s = result["summary"]
        run_dir = Path(result["run_dir"])
        checks = {
            "case count": s["total"] == NUM_CASES,
            "output.json exists": (run_dir / "output.json").exists(),
            "output.html exists": (run_dir / "output.html").exists(),
            "average in range": 1 <= s["average_score"] <= 10,
            "pass rate in range": 0 <= s["pass_rate"] <= 100,
        }
        for label, passed in checks.items():
            mark = "ok " if passed else "FAIL"
            print(f"  [{mark}] {name}: {label}")
            ok = ok and passed

    print("\nSMOKE TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
