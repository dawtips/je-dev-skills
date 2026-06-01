"""Deterministic Mermaid visualizer for workflow blueprints.

Reads the single fenced ```yaml block from a <name>.blueprint.md file (the schema
in docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md §4.1) and emits a sibling
<name>.diagram.md: a Mermaid flowchart of the steps in list order, colored and
shaped by kind, with approval-gate nodes and a subagents subgraph, plus per-step
and per-subagent drill-down tables. Pure transform — no model call, no network,
no timestamp (byte-stable output).
"""
import argparse
import os
import re
import sys

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)

VALID_KINDS = {"deterministic", "agentic"}
GATE_LABELS = {"notify": "notify gate", "explicit": "explicit gate"}


def extract_yaml_block(text: str) -> str:
    blocks = YAML_FENCE.findall(text)
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```yaml block, found {len(blocks)}")
    return blocks[0]


def load_blueprint(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parsed = yaml.safe_load(extract_yaml_block(text))
    if not isinstance(parsed, dict):
        raise ValueError(
            "the ```yaml block must parse to a mapping of blueprint fields, "
            f"got {type(parsed).__name__}")
    return parsed


def sanitize_node_id(raw, used) -> str:
    """Map a step/subagent id to a unique Mermaid-safe node id."""
    base = re.sub(r"[^0-9A-Za-z_]", "_", str(raw)).strip("_") or "node"
    if base[0].isdigit():
        base = "n_" + base
    candidate = base
    i = 2
    while candidate in used:
        candidate = f"{base}__{i}"
        i += 1
    used.add(candidate)
    return candidate


def escape_label(text) -> str:
    """Escape a field value for safe use inside a quoted Mermaid label."""
    s = "" if text is None else str(text)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace("[", "&#91;").replace("]", "&#93;")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _kind_tag(step) -> str:
    kind = step.get("kind")
    if kind in VALID_KINDS:
        tag = kind
    elif kind is None:
        tag = "unspecified"
    else:
        tag = str(kind)
    pattern = step.get("pattern")
    if pattern is not None and str(pattern).strip() and str(pattern) != "none":
        tag = f"{tag} · {pattern}"
    return tag


def _node(node_id, label, shape) -> str:
    open_, close = shape
    return f'    {node_id}{open_}"{label}"{close}'


def render_mermaid(bp: dict) -> str:
    steps = bp.get("steps") or []
    subagents = bp.get("subagents") or []
    if not isinstance(steps, list):
        steps = []
    if not isinstance(subagents, list):
        subagents = []

    used = set()
    node_lines, sub_lines = [], []
    det_ids, ag_ids, unspec_ids, gate_ids, sub_ids = [], [], [], [], []
    flow = []

    for step in steps:
        if not isinstance(step, dict):
            continue
        raw = step.get("id", "step")
        sid = sanitize_node_id(raw, used)
        kind = step.get("kind")
        label = escape_label(raw) + "<br/>" + escape_label(_kind_tag(step))
        if kind == "deterministic":
            node_lines.append(_node(sid, label, ("[", "]")))
            det_ids.append(sid)
        elif kind == "agentic":
            node_lines.append(_node(sid, label, ("(", ")")))
            ag_ids.append(sid)
        else:
            node_lines.append(_node(sid, label, ("[", "]")))
            unspec_ids.append(sid)
        flow.append(sid)
        gate = step.get("approval_gate")
        if gate in GATE_LABELS:
            gid = sanitize_node_id(f"{raw}__gate", used)
            node_lines.append(_node(gid, escape_label(GATE_LABELS[gate]), ("{{", "}}")))
            gate_ids.append(gid)
            flow.append(gid)

    edge_lines = [f"    {a} --> {b}" for a, b in zip(flow, flow[1:])]

    for sa in subagents:
        if not isinstance(sa, dict):
            continue
        raw = sa.get("id", "subagent")
        said = sanitize_node_id(raw, used)
        model = sa.get("model", "inherit")
        effort = sa.get("effort")
        tag = str(model) + (f"/{effort}" if effort else "")
        label = escape_label(raw) + "<br/>" + escape_label(tag)
        sub_ids.append(said)
        sub_lines.append(_node(said, label, ("([", "])")))
    if sub_lines:
        sub_lines = (['    subgraph sg_subagents["Subagents (delegated)"]']
                     + sub_lines + ["    end"])

    style_map = [
        (det_ids, "deterministic", "fill:#dbeafe,stroke:#1e3a8a,color:#0b1324"),
        (ag_ids, "agentic", "fill:#fde68a,stroke:#92400e,color:#0b1324"),
        (unspec_ids, "unspecified", "fill:#e5e7eb,stroke:#374151,color:#0b1324"),
        (gate_ids, "gate", "fill:#fecaca,stroke:#991b1b,color:#0b1324"),
        (sub_ids, "subagent", "fill:#e9d5ff,stroke:#6b21a8,color:#0b1324"),
    ]
    style_lines, class_lines = [], []
    for ids, name, style in style_map:
        if ids:
            style_lines.append(f"    classDef {name} {style};")
            class_lines.append(f"    class {','.join(ids)} {name};")

    out = ["flowchart TD"]
    if not node_lines and not sub_lines:
        out.append('    empty["(no steps defined)"]')
    out += node_lines + edge_lines + sub_lines + style_lines + class_lines
    return "\n".join(out)


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def _yn(value) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return _cell(value)


def render_step_table(steps) -> str:
    steps = steps or []
    if not steps:
        return "_No steps defined._"
    rows = [
        "| id | kind | pattern | gate | side-effecting | reversible | termination |",
        "|----|------|---------|------|----------------|------------|-------------|",
    ]
    for step in steps:
        step = step if isinstance(step, dict) else {}
        rows.append(
            "| {id} | {kind} | {pattern} | {gate} | {se} | {rev} | {term} |".format(
                id=_cell(step.get("id")),
                kind=_cell(step.get("kind")),
                pattern=_cell(step.get("pattern")),
                gate=_cell(step.get("approval_gate")),
                se=_yn(step.get("side_effecting")),
                rev=_yn(step.get("reversible")),
                term=_cell(step.get("termination")),
            )
        )
    return "\n".join(rows)


def render_subagent_table(subs) -> str:
    subs = subs or []
    if not subs:
        return "_No delegated subagents._"
    rows = [
        "| id | model | effort | objective | output_format | tools | boundaries |",
        "|----|-------|--------|-----------|---------------|-------|------------|",
    ]
    for sa in subs:
        sa = sa if isinstance(sa, dict) else {}
        tools = sa.get("tools")
        tools_str = ", ".join(str(t) for t in tools) if isinstance(tools, list) else tools
        rows.append(
            "| {id} | {model} | {effort} | {obj} | {of} | {tools} | {bnd} |".format(
                id=_cell(sa.get("id")),
                model=_cell(sa.get("model")),
                effort=_cell(sa.get("effort")),
                obj=_cell(sa.get("objective")),
                of=_cell(sa.get("output_format")),
                tools=_cell(tools_str),
                bnd=_cell(sa.get("boundaries")),
            )
        )
    return "\n".join(rows)


def render_document(bp: dict, name: str) -> str:
    steps = bp.get("steps") or []
    subs = bp.get("subagents") or []
    parts = [
        f"# {name} — workflow diagram",
        "",
        f"<!-- Generated by workflow-design-visualize from {name}.blueprint.md. "
        "Do not edit by hand; regenerate from the blueprint. -->",
        "",
        "## Flow",
        "",
        "```mermaid",
        render_mermaid(bp),
        "```",
        "",
        "Nodes follow the blueprint's `steps` list order. Color and shape encode "
        "`kind` (rectangle = deterministic, rounded = agentic); a `· <pattern>` tag "
        "marks a step's `pattern`; a hexagon after a step is its `approval_gate`. "
        "Subagents are shown in a separate cluster — the v0.1 schema has no field "
        "linking a step to the subagent it delegates to, so no edges are drawn "
        "between them.",
        "",
        "## Step details",
        "",
        render_step_table(steps),
        "",
        "## Subagents",
        "",
        render_subagent_table(subs),
        "",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    sys.exit(main())
