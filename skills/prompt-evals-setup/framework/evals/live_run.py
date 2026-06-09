"""Live prompt-eval orchestration with deterministic assertion gating."""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from evals import config
from evals.assertion_gate import evaluate_assertion_gate, synthetic_gated_verdict
from evals.evaluator.grade import grade
from evals.evaluator.report import summarize, write_html, write_json
from evals.evaluator.run import RunFunction, execute
from evals.report_analyst import build_report_analysis


def run_evaluation(
    *,
    judge_client,
    run_function: RunFunction,
    dataset_file: str,
    extra_criteria: str | None = None,
    process_criteria: str | None = None,
    assertions: list[dict] | None = None,
    assertion_policy: str = "gate_mandatory",
    runs_dir: str = config.RUNS_DIR,
    run_label: str | None = None,
    max_concurrent_tasks: int = config.MAX_CONCURRENT_TASKS,
    baseline: dict | None = None,
    variance_runs: list[dict] | None = None,
) -> dict:
    """Run a frozen dataset against a prompt/agent, applying assertions before judging."""
    dataset = json.loads(Path(dataset_file).read_text(encoding="utf-8"))
    cases = dataset["cases"]
    configured_assertions = assertions or []

    def work(case: dict) -> dict:
        # Execute (executor) and grade (judge API) are the flaky, network-bound
        # steps; isolate each so one case's failure becomes a scored failure rather
        # than aborting the whole run with no artifacts. Assertion-gate evaluation is
        # deterministic config validation and stays outside the guard so a genuine
        # misconfiguration still fails loudly for every case.
        try:
            trajectory = execute(run_function, case["prompt_inputs"])
        except Exception as exc:  # noqa: BLE001 - any executor failure is per-case
            return _execution_error_result(case, exc)
        gate = evaluate_assertion_gate(
            trajectory.final_output,
            configured_assertions,
            assertion_policy,
        )
        if gate["judge_skipped"]:
            verdict = synthetic_gated_verdict(gate)
        else:
            try:
                verdict = grade(
                    judge_client,
                    case,
                    trajectory,
                    extra_criteria=extra_criteria,
                    process_criteria=process_criteria,
                )
            except Exception as exc:  # noqa: BLE001 - any judge failure is per-case
                return _execution_error_result(case, exc, trajectory=trajectory, gate=gate)
        return {
            "output": trajectory.final_output,
            "trajectory": trajectory.to_dict(),
            "test_case": case,
            "score": verdict["score"],
            "reasoning": verdict.get("reasoning", ""),
            "verdict": verdict,
            "assertion_gate": gate,
        }

    results = _map(work, cases, max_workers=max_concurrent_tasks)
    summary = summarize(results)
    errors = [r for r in results if r.get("error")]
    if errors:
        print(
            f"WARNING: {len(errors)} of {len(cases)} cases failed to execute; "
            "they are scored 1 and tagged with an 'error' field.",
            file=sys.stderr,
        )

    label = run_label or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(runs_dir) / label
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "task_description": dataset.get("provenance", {}).get("task_description", ""),
        "dataset_file": dataset_file,
        "judge_model": getattr(judge_client, "model", "unknown"),
        "run_label": label,
        "extra_criteria": extra_criteria,
        "assertion_policy": assertion_policy,
        "errors": [
            {"scenario": r["test_case"].get("scenario", ""), "error": r["error"]}
            for r in errors
        ],
    }
    current = {"meta": meta, "summary": summary, "results": results}
    analysis = build_report_analysis(current, baseline=baseline, variance_runs=variance_runs)

    write_json(out_dir / "output.json", results, summary, meta, analysis=analysis)
    write_html(out_dir / "output.html", results, summary, meta, analysis=analysis)
    return {
        "summary": summary,
        "run_dir": str(out_dir),
        "results": results,
        "analysis": analysis,
        "errors": errors,
    }


def _execution_error_result(
    case: dict, exc: Exception, *, trajectory=None, gate: dict | None = None
) -> dict:
    """Build a scored failure result for a case whose executor or judge raised.

    Keeps the normal result shape (so ``summarize`` and the report writers work) and
    adds an ``error`` field so callers can tell an execution error apart from a
    genuine low-quality grade. Scored 1, mirroring the assertion-gate score floor.
    """
    message = f"{type(exc).__name__}: {exc}"
    output = trajectory.final_output if trajectory is not None else ""
    trajectory_dict = trajectory.to_dict() if trajectory is not None else {"final_output": "", "steps": []}
    verdict = {
        "score": 1,
        "strengths": [],
        "weaknesses": [f"execution error: {message}"],
        "reasoning": f"EXECUTION ERROR (not a quality judgment): {message}",
    }
    return {
        "output": output,
        "trajectory": trajectory_dict,
        "test_case": case,
        "score": verdict["score"],
        "reasoning": verdict["reasoning"],
        "verdict": verdict,
        "assertion_gate": gate,
        "error": message,
    }


def _map(fn, items: list[dict], *, max_workers: int) -> list:
    """Run ``fn`` over ``items`` concurrently while preserving input order."""
    if not items:
        return []
    results: list = [None] * len(items)
    lock = threading.Lock()

    def wrapped(index_item):
        index, item = index_item
        value = fn(item)
        with lock:
            results[index] = value

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(wrapped, enumerate(items)))
    return results
