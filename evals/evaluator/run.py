"""Stage 2 — execute the prompt/agent under test for one test case."""

from typing import Callable

from .schemas import Trajectory, normalize_trajectory

# A run_function maps one case's prompt_inputs to either raw text (single-shot)
# or a Trajectory (agentic). See spec Â§3.4 and the agentic extension.
RunFunction = Callable[[dict], object]


def execute(run_function: RunFunction, prompt_inputs: dict) -> Trajectory:
    """Call the system under test and normalize its result to a Trajectory."""
    return normalize_trajectory(run_function(prompt_inputs))


def format_transcript(trajectory: Trajectory) -> str:
    """Render an agent trajectory into plain text for the judge."""
    lines: list[str] = []
    for i, step in enumerate(trajectory.steps, start=1):
        if step.role == "tool" or step.tool_name:
            lines.append(
                f"[{i}] TOOL CALL {step.tool_name}\n"
                f"    input:  {step.tool_input!r}\n"
                f"    output: {step.tool_output!r}"
            )
        else:
            lines.append(f"[{i}] {step.role.upper()}: {step.content}")
    return "\n".join(lines) if lines else "(no intermediate steps)"
