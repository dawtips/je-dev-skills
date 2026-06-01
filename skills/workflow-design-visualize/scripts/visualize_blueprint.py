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


if __name__ == "__main__":
    sys.exit(main())
