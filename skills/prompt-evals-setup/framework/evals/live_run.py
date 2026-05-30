"""Live prompt-eval orchestration with deterministic assertion gating."""

from __future__ import annotations

import json
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
        trajectory = execute(run_function, case["prompt_inputs"])
        gate = evaluate_assertion_gate(
            trajectory.final_output,
            configured_assertions,
            assertion_policy,
        )
        if gate["judge_skipped"]:
            verdict = synthetic_gated_verdict(gate)
        else:
            verdict = grade(
                judge_client,
                case,
                trajectory,
                extra_criteria=extra_criteria,
                process_criteria=process_criteria,
            )
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
