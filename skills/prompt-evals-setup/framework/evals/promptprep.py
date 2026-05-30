"""Deterministic prompt-prep glue (vendored evals/ top level - NOT in evaluator/).

Pairs with the framework's render() to check a prompt template's {placeholders}
against a case's prompt_inputs BEFORE rendering:
  - FAILS (raises MissingPlaceholderError) on any placeholder with no value,
    producing a structured report listing ALL missing keys (render() would only
    raise on the first one it hits).
  - WARNS (logging) on inputs that the template never references - so a human can
    reconcile them against create-dataset's PROMPT_INPUTS_SPEC. It NEVER auto-syncs.
  - REPORTS the detected placeholders for manual reconciliation.

Intentionally redundant with render()'s KeyError backstop so the warn/report path
runs first. Used by BOTH execution paths (the keyed run_prompt imports it; the
no-key skill conceptually performs the same check before dispatch).
"""

import logging
import re

log = logging.getLogger(__name__)

# Mirror evaluator/templates.py render(): a placeholder is {identifier}, and a
# doubled brace ({{ or }}) is a literal brace. Parsing must be left-to-right so
# doubled braces adjacent to a placeholder work: {{"k": {v}}} declares v.
_IDENT = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


class MissingPlaceholderError(KeyError):
    """A template placeholder has no matching value in prompt_inputs."""


def declared_placeholders(template: str) -> list[str]:
    """Return the unique {placeholder} names in declaration order.

    Literal {{/}} braces are skipped so they are never read as placeholders.
    """
    seen: list[str] = []
    i, n = 0, len(template)
    while i < n:
        ch = template[i]
        if ch == "{":
            if i + 1 < n and template[i + 1] == "{":
                i += 2
                continue
            match = _IDENT.match(template, i + 1)
            if match and match.end() < n and template[match.end()] == "}":
                name = match.group(0)
                if name not in seen:
                    seen.append(name)
                i = match.end() + 1
                continue
        if ch == "}" and i + 1 < n and template[i + 1] == "}":
            i += 2
            continue
        i += 1
    return seen


def check_placeholders(template: str, prompt_inputs: dict) -> dict:
    """Reconcile a template's placeholders against prompt_inputs.

    Returns {"declared": [...], "unused": [...], "missing": [...]} (each a list of
    names). Raises MissingPlaceholderError if any declared placeholder is missing
    a value. Logs a WARNING for any prompt_inputs key the template never uses.
    Never mutates prompt_inputs and never auto-syncs anything.
    """
    declared = declared_placeholders(template)
    provided = list(prompt_inputs.keys())
    missing = [name for name in declared if name not in prompt_inputs]
    unused = [name for name in provided if name not in declared]

    if unused:
        log.warning(
            "prompt_inputs has %d field(s) the template never references: %s "
            "(reconcile against create-dataset's PROMPT_INPUTS_SPEC; no auto-sync)",
            len(unused),
            ", ".join(unused),
        )

    if missing:
        raise MissingPlaceholderError(
            "template requires placeholder value(s) not in prompt_inputs: "
            + ", ".join(missing)
        )

    return {"declared": declared, "unused": unused, "missing": missing}
