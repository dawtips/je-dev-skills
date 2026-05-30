"""Explicit K-run orchestration for live eval variance."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from evals.runs_util import load_json
from evals.variance import compute_variance


def variance_labels(group_label: str, k: int) -> list[str]:
    if k < 2:
        raise ValueError("K-run variance requires k >= 2")
    if not group_label or "/" in group_label or "\\" in group_label:
        raise ValueError("group_label must be a non-empty run label, not a path")
    return [f"{group_label}__k{ordinal:02d}" for ordinal in range(k)]


def output_paths_for_labels(runs_dir: str | Path, labels: list[str]) -> list[Path]:
    base = Path(runs_dir)
    return [base / label / "output.json" for label in labels]


def run_k_variance(
    *,
    group_label: str,
    k: int,
    runs_dir: str | Path,
    run_once: Callable[[str], dict],
) -> dict:
    labels = variance_labels(group_label, k)
    outputs = []
    for label in labels:
        expected_dir = Path(runs_dir) / label
        result = run_once(label)
        actual_dir = Path(result["run_dir"])
        if actual_dir.resolve() != expected_dir.resolve():
            raise ValueError(f"run_once wrote {actual_dir}, expected {expected_dir}")
        output = actual_dir / "output.json"
        if not output.exists():
            raise FileNotFoundError(output)
        outputs.append(output)
    return compute_variance([load_json(path) for path in outputs])
