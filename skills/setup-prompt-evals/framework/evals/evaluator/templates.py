"""Tiny template renderer.

Substitutes ``{placeholder}`` tokens. Literal braces are written ``{{`` / ``}}``
so prompt templates can contain real JSON examples without breaking. Unlike
``str.format``, an unescaped ``{`` that is not a valid placeholder is left
untouched rather than raising, and only known placeholders are substituted.
"""

import re

_IDENT = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def render(template: str, /, **values: object) -> str:
    """Render ``template``, replacing ``{name}`` with ``values[name]``.

    Literal braces are written ``{{`` / ``}}``. Parsing is a single left-to-right
    pass (like ``str.format``) so doubled braces adjacent to a placeholder — e.g.
    ``{{"k": {v}}}`` — resolve correctly to ``{"k": <v>}``.

    Raises ``KeyError`` if a placeholder has no matching value. Extra values are
    ignored, so one call site can render templates that use a subset.
    """
    out: list[str] = []
    i, n = 0, len(template)
    while i < n:
        ch = template[i]
        if ch == "{":
            if i + 1 < n and template[i + 1] == "{":  # literal {
                out.append("{")
                i += 2
                continue
            match = _IDENT.match(template, i + 1)
            if match and match.end() < n and template[match.end()] == "}":
                key = match.group(0)
                if key not in values:
                    raise KeyError(f"Missing template variable: {key!r}")
                out.append(str(values[key]))
                i = match.end() + 1
                continue
            out.append(ch)  # a lone { that is not a placeholder
            i += 1
            continue
        if ch == "}":
            if i + 1 < n and template[i + 1] == "}":  # literal }
                out.append("}")
                i += 2
                continue
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)
