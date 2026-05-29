"""PromptEvaluator — orchestrates the three stages with a bounded worker pool."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from evals import config

from .client import LLMClient
from .generate import generate_ideas, generate_test_case
from .grade import grade
from .report import summarize, write_html, write_json
from .run import RunFunction, execute


class PromptEvaluator:
    """Generate datasets and evaluate prompts/agents against them.

    Generation is expensive and one-time; evaluation is cheap and repeated.
    Freeze a dataset once, then re-run ``run_evaluation`` against it for every
    prompt revision to compare versions apples-to-apples.
    """

    def __init__(
        self,
        client: LLMClient,
        *,
        judge_client: LLMClient | None = None,
        max_concurrent_tasks: int = config.MAX_CONCURRENT_TASKS,
    ) -> None:
        self.client = client
        # A distinct (stronger) judge reduces self-grading bias; defaults to client.
        self.judge_client = judge_client or client
        self.max_concurrent_tasks = max_concurrent_tasks

    # --- Stage 1 -------------------------------------------------------------
    def generate_dataset(
        self,
        *,
        task_description: str,
        prompt_inputs_spec: dict,
        num_cases: int = 1,
        output_file: str = f"{config.DATASETS_DIR}/dataset.json",
    ) -> dict:
        ideas = generate_ideas(self.client, task_description, prompt_inputs_spec, num_cases)
        self._log(f"generated {len(ideas)} ideas; expanding to test cases...")

        cases = self._map(
            lambda idea: generate_test_case(
                self.client, task_description, prompt_inputs_spec, idea
            ),
            ideas,
            label="test cases",
        )

        dataset = {
            "provenance": {
                "task_description": task_description,
                "prompt_inputs_spec": prompt_inputs_spec,
                "num_cases": len(cases),
                "generator_model": getattr(self.client, "model", "unknown"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "cases": cases,
        }
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
        self._log(f"wrote dataset -> {path}")
        return dataset

    # --- Stages 2 + 3 --------------------------------------------------------
    def run_evaluation(
        self,
        *,
        run_function: RunFunction,
        dataset_file: str,
        extra_criteria: str | None = None,
        process_criteria: str | None = None,
        runs_dir: str = config.RUNS_DIR,
        run_label: str | None = None,
    ) -> dict:
        dataset = json.loads(Path(dataset_file).read_text(encoding="utf-8"))
        cases = dataset["cases"]

        def work(case: dict) -> dict:
            trajectory = execute(run_function, case["prompt_inputs"])
            verdict = grade(
                self.judge_client,
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
                "verdict": verdict,  # full strengths/weaknesses retained
            }

        results = self._map(work, cases, label="run+grade")
        summary = summarize(results)

        label = run_label or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = Path(runs_dir) / label
        out_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "task_description": dataset.get("provenance", {}).get("task_description", ""),
            "dataset_file": dataset_file,
            "judge_model": getattr(self.judge_client, "model", "unknown"),
            "run_label": label,
            "extra_criteria": extra_criteria,
        }
        write_json(out_dir / "output.json", results, summary, meta)
        write_html(out_dir / "output.html", results, summary, meta)
        self._log(
            f"run '{label}': avg {summary['average_score']}/10, "
            f"pass rate {summary['pass_rate']}% -> {out_dir}"
        )
        return {"summary": summary, "run_dir": str(out_dir), "results": results}

    # --- helpers -------------------------------------------------------------
    def _map(self, fn, items, *, label: str) -> list:
        """Run ``fn`` over ``items`` in a bounded pool, preserving order, with
        milestone progress logging."""
        total = len(items)
        if total == 0:
            return []
        done = 0
        lock = threading.Lock()
        next_mark = 0.2

        results: list = [None] * total

        def wrapped(index_item):
            nonlocal done, next_mark
            index, item = index_item
            value = fn(item)
            with lock:
                results[index] = value
                done += 1
                if total and done / total >= next_mark:
                    self._log(f"{label}: {done}/{total}")
                    next_mark += 0.2
            return None

        with ThreadPoolExecutor(max_workers=self.max_concurrent_tasks) as pool:
            list(pool.map(wrapped, enumerate(items)))
        return results

    @staticmethod
    def _log(message: str) -> None:
        print(f"[eval] {message}", flush=True)
