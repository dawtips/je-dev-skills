"""Robust-ish JSON extraction for LLM output.

The framework forces clean JSON with the assistant-prefill + stop-sequence trick
(see client.py), but model output is never fully trusted. ``parse_json`` strips
stray markdown fences and, on failure, attempts a single bracket-slice repair
before raising a descriptive error.
"""

import json
from typing import Any


class JSONParseError(ValueError):
    """Raised when LLM output cannot be parsed as JSON."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # drop the opening fence line (``` or ```json)
        newline = text.find("\n")
        text = text[newline + 1 :] if newline != -1 else ""
    if text.endswith("```"):
        text = text[: -3]
    return text.strip()


def _bracket_slice(text: str) -> str | None:
    """Return the substring from the first opening bracket to its matching last."""
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    end = text.rfind(closer)
    if end == -1 or end < start:
        return None
    return text[start : end + 1]


def parse_json(text: str) -> Any:
    """Parse ``text`` as JSON, repairing common LLM artifacts first."""
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    sliced = _bracket_slice(cleaned)
    if sliced is not None:
        try:
            return json.loads(sliced)
        except json.JSONDecodeError:
            pass
    raise JSONParseError(
        "Could not parse model output as JSON. First 200 chars:\n"
        + text[:200]
    )
