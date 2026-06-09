"""LLM client protocol + the Anthropic reference implementation.

Every framework call returns JSON. We force clean, schema-conformant JSON with
**structured outputs** (``output_config.format``): the caller passes a JSON
Schema and the model is constrained to emit exactly that shape. This replaces
the older assistant-prefill + stop-sequence trick, which returns a 400 on
Claude Opus 4.7+ (prefilled last assistant turns are no longer supported).

Calls without a ``schema`` (the bare-array idea list, whose shape a structured
object can't express) fall back to plain generation plus the tolerant parser in
``jsonio``.

The framework depends only on the ``LLMClient`` protocol, so any provider works:
implement ``complete_json`` and pass your client into ``PromptEvaluator``.
"""

from typing import Any, Protocol

from .jsonio import parse_json


class LLMClient(Protocol):
    """Minimal interface the framework needs from a model provider."""

    model: str

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        tag: str = "",
        schema: dict | None = None,
    ) -> Any:
        """Return parsed JSON for one completion.

        ``schema`` (a JSON Schema object) constrains the output shape when the
        provider supports structured outputs; pass ``None`` for a free-form
        JSON response. ``tag`` labels the call site (e.g. "ideas", "testcase",
        "grade") and is ignored by real providers; test doubles may use it to
        route canned responses."""
        ...


# Claude Opus 4.7+ reject sampling params (temperature/top_p/top_k): sending
# temperature returns a 400. Opus 4.6 and earlier still accept them, so we parse
# the 4.x minor version rather than matching the whole family — that omits the
# param for 4.7/4.8 (and any future 4.9+) without stripping it from a pinned 4.6
# judge that still honours GRADING_TEMPERATURE. An unparseable/alias id keeps the
# param (a loud 400 is easier to debug than silent loss of determinism).
def _rejects_sampling_params(model: str) -> bool:
    prefix = "claude-opus-4-"
    if not model.startswith(prefix):
        return False
    minor = model[len(prefix):].split("-", 1)[0]
    # A 1-2 digit token is the .x minor (4-7, 4-8, …). A longer all-digit token is
    # a snapshot date on the bare 4.0 id (claude-opus-4-YYYYMMDD), i.e. no minor
    # segment -> Opus 4.0, which still accepts sampling.
    return minor.isdigit() and len(minor) <= 2 and int(minor) >= 7


class AnthropicClient:
    """Reference ``LLMClient`` backed by the Anthropic Python SDK.

    ``anthropic`` is imported lazily so the rest of the package (and its unit
    tests) work without the dependency installed.
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        max_tokens: int = 2048,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without SDK
            raise ImportError(
                "The 'anthropic' package is required for AnthropicClient. "
                "Install it with: pip install anthropic"
            ) from exc

        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        tag: str = "",
        schema: dict | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        # Opus 4.7+ removed sampling params; sending temperature returns 400.
        if not _rejects_sampling_params(self.model):
            kwargs["temperature"] = temperature
        # Structured outputs constrain the response to the given JSON Schema,
        # so no markdown fence or prefill is needed to get clean JSON.
        if schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": schema}
            }

        response = self._client.messages.create(**kwargs)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return parse_json(text)
