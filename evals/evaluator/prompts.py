"""Loader for the three (plus one) framework prompt templates.

The prompts live as editable Markdown in ``evals/prompts/``. They *are* the
framework (spec Â§8.6) — tune them there, not in code.
"""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Short system prompts; the bulk of each instruction lives in the .md template.
SYSTEM_GENERATE = "You generate evaluation datasets. Follow the instructions exactly and output only the requested JSON."
SYSTEM_JUDGE = "You are a precise, consistent evaluation judge. Output only the requested JSON."


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Return the raw template text for ``name`` (without the .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")
