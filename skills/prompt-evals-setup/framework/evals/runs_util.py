"""Shared helpers for reading evaluation run files (evals/runs/<label>/output.json)."""

import json
from pathlib import Path


def load_json(path: str | Path) -> dict:
    """Read and parse a JSON file (a run's output.json or a dataset)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def case_key(result: dict, index: int) -> str:
    """A stable key for matching a result across runs of the same dataset.

    Prefer the human-readable ``scenario`` (stable across runs); fall back to the
    positional ``#<index>`` when a case has no scenario.
    """
    scenario = result.get("test_case", {}).get("scenario")
    return scenario if scenario else f"#{index}"
