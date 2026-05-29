"""LLM client protocol + the Anthropic reference implementation.

Every framework call returns JSON. We force clean, parseable JSON with the
assistant-prefill + stop-sequence trick (spec Â§8.2): prefill the assistant turn
with an opening ```` ```json ```` fence and stop on the closing ```` ``` ````.
The returned text is the JSON body with no markdown leakage.

The framework depends only on the ``LLMClient`` protocol, so any provider works:
implement ``complete_json`` and pass your client into ``PromptEvaluator``.
"""

from typing import Any, Protocol

from .jsonio import parse_json


class LLMClient(Protocol):
    """Minimal interface the framework needs from a model provider."""

    model: str

    def complete_json(
        self, *, system: str, user: str, temperature: float, tag: str = ""
    ) -> Any:
        """Return parsed JSON for one completion. ``tag`` labels the call site
        (e.g. "ideas", "testcase", "grade") and is ignored by real providers;
        test doubles may use it to route canned responses."""
        ...


_PREFILL = "```json\n"
_STOP = "```"


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
        self, *, system: str, user: str, temperature: float, tag: str = ""
    ) -> Any:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            system=system,
            messages=[
                {"role": "user", "content": user},
                {"role": "assistant", "content": _PREFILL},
            ],
            stop_sequences=[_STOP],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return parse_json(text)
