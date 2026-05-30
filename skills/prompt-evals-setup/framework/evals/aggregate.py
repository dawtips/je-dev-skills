"""Deterministic, NO-model report assembler for the no-key Path A.

Vendored at the evals/ top level (beside run_eval.py) - NOT in evaluator/, which is
the frozen framework CORE. Run as a CLI by the prompt-evals-run skill AFTER it has
dispatched an execute- and a grade-subagent per case (session auth, no API key) and
written one verdict JSON per case:

    python -m evals.aggregate --run-label improve-meal-round-00 \
        --verdicts-dir evals/runs/_verdicts/improve-meal-round-00 \
        --dataset evals/datasets/meal_plan.json

It reads the per-case verdict JSON files (sorted by filename for determinism),
validates each verdict via the frozen schemas.validate_verdict, builds the
framework's standard `results` shape, and writes runs/<label>/{output.json,output.html}
via the frozen report.py writers. It prints (and returns) the run_dir. No model call.

Per-case verdict JSON file shape (what the grade-subagent emits, written by the skill):
    {
      "test_case": {... the dataset case: prompt_inputs, solution_criteria,
                    task_description, scenario ...},
      "output":   "<the execute-subagent's raw output string>",
      "verdict":  {"strengths": [...], "weaknesses": [...], "reasoning": "...",
                   "score": <int 1-10>}
    }
"""

import argparse
import json
import sys
from pathlib import Path

from evals import config
from evals.evaluator.report import summarize, write_html, write_json
from evals.evaluator.schemas import validate_verdict


def _read_verdict_files(verdicts_dir: str | Path) -> list[Path]:
    """Return the per-case JSON files in deterministic (filename-sorted) order."""
    d = Path(verdicts_dir)
    return sorted(d.glob("*.json"), key=lambda p: p.name)


def load_results(verdicts_dir: str | Path) -> list[dict]:
    """Load + validate every per-case verdict JSON into the framework result shape.

    Raises FileNotFoundError if the dir has no .json files; ValueError (from
    validate_verdict) if any verdict is malformed.
    """
    files = _read_verdict_files(verdicts_dir)
    if not files:
        raise FileNotFoundError(f"no verdict JSON files in {verdicts_dir}")

    results: list[dict] = []
    for path in files:
        record = json.loads(path.read_text(encoding="utf-8"))
        verdict = validate_verdict(record["verdict"])  # raises on bad/missing score
        test_case = record["test_case"]
        output = record.get("output", "")
        results.append(
            {
                "output": output,
                "trajectory": {"final_output": output, "steps": []},
                "test_case": test_case,
                "score": verdict["score"],
                "reasoning": verdict.get("reasoning", ""),
                "verdict": verdict,
            }
        )
    return results


def _build_meta(
    run_label: str, dataset: str | None, results: list[dict]
) -> dict:
    """Assemble report meta. Prefer the dataset's provenance; else harvest from the
    first verdict's test_case."""
    task_description = ""
    dataset_file = dataset or ""
    if dataset:
        provenance = json.loads(Path(dataset).read_text(encoding="utf-8")).get(
            "provenance", {}
        )
        task_description = provenance.get("task_description", "")
    elif results:
        task_description = results[0]["test_case"].get("task_description", "")
    return {
        "task_description": task_description,
        "dataset_file": dataset_file,
        "judge_model": config.SUBAGENT_JUDGE_MODEL,
        "run_label": run_label,
        "extra_criteria": None,
    }


def aggregate(
    *,
    run_label: str,
    verdicts_dir: str | Path,
    dataset: str | None = None,
    runs_dir: str = config.RUNS_DIR,
) -> str:
    """Assemble runs/<run_label>/{output.json,output.html}. Returns the run_dir path."""
    results = load_results(verdicts_dir)
    summary = summarize(results)
    meta = _build_meta(run_label, dataset, results)

    out_dir = Path(runs_dir) / run_label
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "output.json", results, summary, meta)
    write_html(out_dir / "output.html", results, summary, meta)
    return str(out_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble a prompt-eval report from per-case verdict JSONs (no model)."
    )
    parser.add_argument("--run-label", required=True, help="names runs/<label>/")
    parser.add_argument(
        "--verdicts-dir", required=True, help="dir of per-case verdict JSON files"
    )
    parser.add_argument(
        "--dataset", default=None, help="optional dataset JSON for report meta"
    )
    parser.add_argument(
        "--runs-dir", default=config.RUNS_DIR, help="base runs dir (default config.RUNS_DIR)"
    )
    args = parser.parse_args(argv)
    try:
        run_dir = aggregate(
            run_label=args.run_label,
            verdicts_dir=args.verdicts_dir,
            dataset=args.dataset,
            runs_dir=args.runs_dir,
        )
    except (OSError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}")
        return 2
    except (ValueError, KeyError) as exc:
        print(f"ERROR: invalid verdict data: {exc}")
        return 1
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
