# workflow-design-visualize (T-016 Tier 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: In progress

**Goal:** Ship `workflow-design-visualize` — a deterministic `yaml`→Mermaid generator that renders a validated blueprint as a sibling `<name>.diagram.md` (a `flowchart` in steps-list order + drill-down tables).

**Architecture:** A pure transform mirroring `workflow-design-validate`'s analyzer shape: `scripts/visualize_blueprint.py` extracts the single fenced `yaml` block, then renders a Mermaid flowchart whose every element maps one-to-one to a schema field (edges = `steps` list order; `kind` → color+shape+text; `pattern` → label tag; `approval_gate` → hexagon node after the step; `subagents` → a separate subgraph with **no** fabricated edges). No model call, no network, **no timestamp** → byte-stable output. A thin `SKILL.md` runs it. The design contract is `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md` §3 / §3.6.

**Tech Stack:** Python 3 stdlib + PyYAML; `unittest` offline fixtures; Mermaid flowchart syntax; Claude Code skill (`SKILL.md`).

---

## File structure

```
skills/workflow-design-visualize/
  SKILL.md                                  # procedural skill shell (Bash, Read, Glob)
  scripts/
    visualize_blueprint.py                  # deterministic core + CLI (single file)
    requirements.txt                        # PyYAML>=6.0
    tests/
      __init__.py
      test_extract.py                       # yaml-block extraction / load contract
      test_sanitize.py                      # sanitize_node_id + escape_label units
      test_mermaid.py                       # golden Mermaid over fixtures + edge cases
      test_tables.py                        # step + subagent detail tables
      test_document.py                      # full .diagram.md assembly
      test_cli.py                           # CLI write-path, --stdout, --out, exit codes
      fixtures/
        minimal.blueprint.md                # 1 deterministic step, no subagents
        multi.blueprint.md                  # det+agentic, parallelize, gate, side-effecting, subagent
        dup_ids.blueprint.md                # duplicate ids + special chars in id/label
        broken_no_yaml.blueprint.md         # zero fenced yaml blocks
        broken_two_yaml.blueprint.md        # two fenced yaml blocks
        broken_non_mapping.blueprint.md     # yaml block parses to a list
tools/tests/test_workflow_design_visualize_skill.py   # skill-shell + repo-metadata test
```

**Modified:** `README.md` (group-row invoke list + blurb), `.claude-plugin/plugin.json` (keywords), `AGENTS.md` (`## Tests` block), `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §9 (mark Tier 1 shipped), `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md` §3.6 (flip "building" → "shipped").

**Public API (locked — keep names consistent across tasks):**
`extract_yaml_block(text)->str`, `load_blueprint(path)->dict`, `sanitize_node_id(raw, used:set)->str`, `escape_label(text)->str`, `render_mermaid(bp:dict)->str`, `render_step_table(steps)->str`, `render_subagent_table(subs)->str`, `render_document(bp:dict, name:str)->str`, `default_out_path(in_path)->str`, `blueprint_name(in_path)->str`, `main(argv=None)->int`. Private helpers: `_kind_tag(step)`, `_node(node_id, label, shape)`, `_cell(value)`, `_yn(value)`.

---

## Task 1: Scaffold + YAML extraction/load

**Files:**
- Create: `skills/workflow-design-visualize/scripts/visualize_blueprint.py`
- Create: `skills/workflow-design-visualize/scripts/requirements.txt`
- Create: `skills/workflow-design-visualize/scripts/tests/__init__.py`
- Create: `skills/workflow-design-visualize/scripts/tests/test_extract.py`
- Create fixtures: `minimal.blueprint.md`, `broken_no_yaml.blueprint.md`, `broken_two_yaml.blueprint.md`, `broken_non_mapping.blueprint.md`

- [ ] **Step 1: Create `requirements.txt`**

```
PyYAML>=6.0
```

- [ ] **Step 2: Create the four extraction fixtures**

`fixtures/minimal.blueprint.md`:
````markdown
---
name: minimal
version: 0.1.0
status: validated
created: 2026-05-31
---
# Minimal

```yaml
steps:
  - id: do_thing
    kind: deterministic
    rationale: "single correct answer"
    pattern: none
subagents: []
```
````

`fixtures/broken_no_yaml.blueprint.md`:
```markdown
---
name: broken-no-yaml
---
# No yaml block here, only prose.
```

`fixtures/broken_two_yaml.blueprint.md`:
````markdown
---
name: broken-two-yaml
---
```yaml
steps: []
```

```yaml
subagents: []
```
````

`fixtures/broken_non_mapping.blueprint.md`:
````markdown
---
name: broken-non-mapping
---
```yaml
- a
- b
```
````

- [ ] **Step 3: Create `tests/__init__.py`** (empty file).

- [ ] **Step 4: Write the failing test** — `tests/test_extract.py`

```python
import os
import unittest

from visualize_blueprint import extract_yaml_block, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtract(unittest.TestCase):
    def test_extracts_single_yaml_block(self):
        text = "intro\n```yaml\na: 1\n```\noutro"
        self.assertEqual(extract_yaml_block(text).strip(), "a: 1")

    def test_rejects_zero_blocks(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("no fenced yaml here")

    def test_rejects_multiple_blocks(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("```yaml\na: 1\n```\n```yaml\nb: 2\n```")

    def test_load_returns_mapping(self):
        bp = load_blueprint(os.path.join(FIXTURES, "minimal.blueprint.md"))
        self.assertIsInstance(bp, dict)
        self.assertEqual(bp["steps"][0]["id"], "do_thing")

    def test_load_rejects_non_mapping(self):
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_non_mapping.blueprint.md"))

    def test_load_rejects_no_yaml(self):
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_no_yaml.blueprint.md"))

    def test_load_rejects_two_yaml(self):
        with self.assertRaises(ValueError):
            load_blueprint(os.path.join(FIXTURES, "broken_two_yaml.blueprint.md"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Run to verify it fails**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest discover -s tests -t . -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'visualize_blueprint'`.

- [ ] **Step 6: Create `visualize_blueprint.py` with the module header + extraction**

```python
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


if __name__ == "__main__":
    sys.exit(main())
```

> Note: `main` is added in Task 6. Leaving the `__main__` guard now is fine because the guard only runs on direct execution, not on import. If running the file directly before Task 6, it will `NameError` — that is expected and untested until Task 6.

- [ ] **Step 7: Run to verify it passes**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest discover -s tests -t . -v`
Expected: PASS (7 tests).

- [ ] **Step 8: Commit**

```bash
git add skills/workflow-design-visualize/scripts/visualize_blueprint.py \
        skills/workflow-design-visualize/scripts/requirements.txt \
        skills/workflow-design-visualize/scripts/tests/__init__.py \
        skills/workflow-design-visualize/scripts/tests/test_extract.py \
        skills/workflow-design-visualize/scripts/tests/fixtures/minimal.blueprint.md \
        skills/workflow-design-visualize/scripts/tests/fixtures/broken_no_yaml.blueprint.md \
        skills/workflow-design-visualize/scripts/tests/fixtures/broken_two_yaml.blueprint.md \
        skills/workflow-design-visualize/scripts/tests/fixtures/broken_non_mapping.blueprint.md
git commit -m "feat(T-016): blueprint yaml extraction for visualize"
```

---

## Task 2: `sanitize_node_id` + `escape_label`

**Files:**
- Modify: `skills/workflow-design-visualize/scripts/visualize_blueprint.py`
- Create: `skills/workflow-design-visualize/scripts/tests/test_sanitize.py`

- [ ] **Step 1: Write the failing test** — `tests/test_sanitize.py`

```python
import unittest

from visualize_blueprint import escape_label, sanitize_node_id


class TestSanitizeNodeId(unittest.TestCase):
    def test_passthrough_safe_id(self):
        self.assertEqual(sanitize_node_id("validate_inputs", set()), "validate_inputs")

    def test_dedupes_duplicates(self):
        used = set()
        a = sanitize_node_id("step", used)
        b = sanitize_node_id("step", used)
        c = sanitize_node_id("step", used)
        self.assertEqual((a, b, c), ("step", "step__2", "step__3"))

    def test_leading_digit_prefixed(self):
        self.assertEqual(sanitize_node_id("123abc", set()), "n_123abc")

    def test_special_chars_to_underscore(self):
        self.assertEqual(sanitize_node_id("a-b.c", set()), "a_b_c")

    def test_all_special_falls_back(self):
        self.assertEqual(sanitize_node_id("***", set()), "node")


class TestEscapeLabel(unittest.TestCase):
    def test_escapes_markup_chars(self):
        self.assertEqual(
            escape_label('a "b" <c> & [d]'),
            "a &quot;b&quot; &lt;c&gt; &amp; &#91;d&#93;",
        )

    def test_collapses_whitespace(self):
        self.assertEqual(escape_label("multi\n line\there"), "multi line here")

    def test_none_is_empty(self):
        self.assertEqual(escape_label(None), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_sanitize -v`
Expected: FAIL — `ImportError: cannot import name 'escape_label'`.

- [ ] **Step 3: Add the two functions** (insert after `load_blueprint`)

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_sanitize -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/workflow-design-visualize/scripts/visualize_blueprint.py \
        skills/workflow-design-visualize/scripts/tests/test_sanitize.py
git commit -m "feat(T-016): mermaid-safe node ids and label escaping"
```

---

## Task 3: `render_mermaid` (the core)

**Files:**
- Modify: `skills/workflow-design-visualize/scripts/visualize_blueprint.py`
- Create: `skills/workflow-design-visualize/scripts/tests/test_mermaid.py`
- Create fixtures: `multi.blueprint.md`, `dup_ids.blueprint.md`

- [ ] **Step 1: Create `fixtures/multi.blueprint.md`**

````markdown
---
name: multi
version: 0.1.0
status: validated
created: 2026-05-31
---
# Multi

```yaml
steps:
  - id: validate_inputs
    kind: deterministic
    rationale: "schema checks"
    pattern: none
    side_effecting: false
    reversible: false
  - id: plan
    kind: agentic
    rationale: "open-ended"
    pattern: none
    termination: "first valid response"
  - id: fan_out
    kind: agentic
    rationale: "independent items"
    pattern: parallelize
    termination: "all done or timeout"
  - id: emit
    kind: deterministic
    rationale: "write file"
    pattern: none
    side_effecting: true
    reversible: true
    retry: {policy: "overwrite", idempotency_key: "run_id"}
    rollback: "delete file"
    approval_gate: explicit
subagents:
  - id: worker
    objective: "do one item"
    output_format: "JSON"
    tools: [web_search, web_fetch]
    boundaries: "one item only"
    model: haiku
    effort: low
```
````

- [ ] **Step 2: Create `fixtures/dup_ids.blueprint.md`**

````markdown
---
name: dup-ids
---
# Dup ids

```yaml
steps:
  - id: step
    kind: deterministic
    rationale: "a"
    pattern: none
  - id: step
    kind: agentic
    rationale: "b"
    pattern: none
    termination: "x"
  - id: "weird [id] & <stuff>"
    kind: deterministic
    rationale: "c"
    pattern: none
subagents: []
```
````

- [ ] **Step 3: Write the failing test** — `tests/test_mermaid.py`

```python
import os
import unittest

from visualize_blueprint import load_blueprint, render_mermaid

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _bp(name):
    return load_blueprint(os.path.join(FIXTURES, name))


MINIMAL_EXPECTED = """flowchart TD
    do_thing["do_thing<br/>deterministic"]
    classDef deterministic fill:#dbeafe,stroke:#1e3a8a,color:#0b1324;
    class do_thing deterministic;"""

MULTI_EXPECTED = """flowchart TD
    validate_inputs["validate_inputs<br/>deterministic"]
    plan("plan<br/>agentic")
    fan_out("fan_out<br/>agentic · parallelize")
    emit["emit<br/>deterministic"]
    emit__gate{{"explicit gate"}}
    validate_inputs --> plan
    plan --> fan_out
    fan_out --> emit
    emit --> emit__gate
    subgraph sg_subagents["Subagents (delegated)"]
    worker(["worker<br/>haiku/low"])
    end
    classDef deterministic fill:#dbeafe,stroke:#1e3a8a,color:#0b1324;
    classDef agentic fill:#fde68a,stroke:#92400e,color:#0b1324;
    classDef gate fill:#fecaca,stroke:#991b1b,color:#0b1324;
    classDef subagent fill:#e9d5ff,stroke:#6b21a8,color:#0b1324;
    class validate_inputs,emit deterministic;
    class plan,fan_out agentic;
    class emit__gate gate;
    class worker subagent;"""


class TestRenderMermaid(unittest.TestCase):
    def test_minimal_golden(self):
        self.assertEqual(render_mermaid(_bp("minimal.blueprint.md")), MINIMAL_EXPECTED)

    def test_multi_golden(self):
        self.assertEqual(render_mermaid(_bp("multi.blueprint.md")), MULTI_EXPECTED)

    def test_deterministic_same_bytes(self):
        bp = _bp("multi.blueprint.md")
        self.assertEqual(render_mermaid(bp), render_mermaid(bp))

    def test_empty_blueprint_placeholder(self):
        out = render_mermaid({})
        self.assertEqual(out, 'flowchart TD\n    empty["(no steps defined)"]')

    def test_dup_ids_deduped_and_escaped(self):
        out = render_mermaid(_bp("dup_ids.blueprint.md"))
        self.assertIn('    step["step<br/>deterministic"]', out)
        self.assertIn('    step__2("step<br/>agentic")', out)
        self.assertIn("    step --> step__2", out)
        # third step id sanitized to a unique node, label fully escaped
        self.assertIn("&#91;id&#93;", out)
        self.assertIn("&amp;", out)
        self.assertIn("&lt;stuff&gt;", out)
        # all three step nodes are distinct ids (no collision)
        self.assertIn("    step__2 --> ", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run to verify it fails**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_mermaid -v`
Expected: FAIL — `ImportError: cannot import name 'render_mermaid'`.

- [ ] **Step 5: Add `_kind_tag`, `_node`, and `render_mermaid`** (insert after `escape_label`)

```python
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
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_mermaid -v`
Expected: PASS (5 tests). If `test_multi_golden` fails on a whitespace/character diff only, print the actual output (`python3 -c "from visualize_blueprint import *; import os; print(render_mermaid(load_blueprint('tests/fixtures/multi.blueprint.md')))"`) and reconcile `MULTI_EXPECTED` to the actual bytes — the **structure** (node shapes, edge order, gate node, subgraph, class grouping/order) is what must match; exact hex/spacing just needs test and impl to agree.

- [ ] **Step 7: Commit**

```bash
git add skills/workflow-design-visualize/scripts/visualize_blueprint.py \
        skills/workflow-design-visualize/scripts/tests/test_mermaid.py \
        skills/workflow-design-visualize/scripts/tests/fixtures/multi.blueprint.md \
        skills/workflow-design-visualize/scripts/tests/fixtures/dup_ids.blueprint.md
git commit -m "feat(T-016): deterministic yaml->Mermaid flowchart renderer"
```

---

## Task 4: Detail tables

**Files:**
- Modify: `skills/workflow-design-visualize/scripts/visualize_blueprint.py`
- Create: `skills/workflow-design-visualize/scripts/tests/test_tables.py`

- [ ] **Step 1: Write the failing test** — `tests/test_tables.py`

```python
import os
import unittest

from visualize_blueprint import load_blueprint, render_step_table, render_subagent_table

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestStepTable(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(render_step_table([]), "_No steps defined._")

    def test_header_and_rows(self):
        steps = load_blueprint(os.path.join(FIXTURES, "multi.blueprint.md"))["steps"]
        out = render_step_table(steps)
        self.assertIn("| id | kind | pattern | gate | side-effecting | reversible | termination |", out)
        self.assertIn("| validate_inputs | deterministic | none |  | no | no |  |", out)
        self.assertIn("| fan_out | agentic | parallelize |  |  |  | all done or timeout |", out)
        self.assertIn("| emit | deterministic | none | explicit | yes | yes |  |", out)

    def test_escapes_pipe_and_newline(self):
        out = render_step_table([{"id": "x", "termination": "a | b\nc"}])
        self.assertIn("a \\| b c", out)


class TestSubagentTable(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(render_subagent_table([]), "_No delegated subagents._")

    def test_joins_tools_list(self):
        subs = load_blueprint(os.path.join(FIXTURES, "multi.blueprint.md"))["subagents"]
        out = render_subagent_table(subs)
        self.assertIn("| id | model | effort | objective | output_format | tools | boundaries |", out)
        self.assertIn("| worker | haiku | low | do one item | JSON | web_search, web_fetch | one item only |", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_tables -v`
Expected: FAIL — `ImportError: cannot import name 'render_step_table'`.

- [ ] **Step 3: Add `_cell`, `_yn`, `render_step_table`, `render_subagent_table`** (insert after `render_mermaid`)

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_tables -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/workflow-design-visualize/scripts/visualize_blueprint.py \
        skills/workflow-design-visualize/scripts/tests/test_tables.py
git commit -m "feat(T-016): per-step and per-subagent drill-down tables"
```

---

## Task 5: `render_document`

**Files:**
- Modify: `skills/workflow-design-visualize/scripts/visualize_blueprint.py`
- Create: `skills/workflow-design-visualize/scripts/tests/test_document.py`

- [ ] **Step 1: Write the failing test** — `tests/test_document.py`

```python
import os
import unittest

from visualize_blueprint import load_blueprint, render_document, render_mermaid

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderDocument(unittest.TestCase):
    def setUp(self):
        self.bp = load_blueprint(os.path.join(FIXTURES, "multi.blueprint.md"))
        self.doc = render_document(self.bp, "multi")

    def test_title_and_sections(self):
        self.assertTrue(self.doc.startswith("# multi — workflow diagram\n"))
        self.assertIn("## Flow", self.doc)
        self.assertIn("## Step details", self.doc)
        self.assertIn("## Subagents", self.doc)

    def test_embeds_mermaid_block(self):
        self.assertIn("```mermaid\n" + render_mermaid(self.bp) + "\n```", self.doc)

    def test_generated_comment_and_caption(self):
        self.assertIn("<!-- Generated by workflow-design-visualize from multi.blueprint.md.", self.doc)
        self.assertIn("no edges are drawn between them", self.doc)

    def test_trailing_newline(self):
        self.assertTrue(self.doc.endswith("\n"))

    def test_deterministic(self):
        self.assertEqual(render_document(self.bp, "multi"), render_document(self.bp, "multi"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_document -v`
Expected: FAIL — `ImportError: cannot import name 'render_document'`.

- [ ] **Step 3: Add `render_document`** (insert after `render_subagent_table`)

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_document -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/workflow-design-visualize/scripts/visualize_blueprint.py \
        skills/workflow-design-visualize/scripts/tests/test_document.py
git commit -m "feat(T-016): assemble the .diagram.md document"
```

---

## Task 6: CLI (`main`, paths)

**Files:**
- Modify: `skills/workflow-design-visualize/scripts/visualize_blueprint.py`
- Create: `skills/workflow-design-visualize/scripts/tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — `tests/test_cli.py`

```python
import contextlib
import io
import os
import shutil
import tempfile
import unittest

from visualize_blueprint import (blueprint_name, default_out_path, load_blueprint,
                                 main, render_document)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MINIMAL = os.path.join(FIXTURES, "minimal.blueprint.md")


class TestPaths(unittest.TestCase):
    def test_default_out_path_blueprint(self):
        self.assertEqual(default_out_path("a/b/foo.blueprint.md"), "a/b/foo.diagram.md")

    def test_default_out_path_plain_md(self):
        self.assertEqual(default_out_path("a/bar.md"), "a/bar.diagram.md")

    def test_blueprint_name(self):
        self.assertEqual(blueprint_name("a/b/foo.blueprint.md"), "foo")


class TestCli(unittest.TestCase):
    def test_stdout_matches_render_document(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([MINIMAL, "--stdout"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), render_document(load_blueprint(MINIMAL), "minimal"))

    def test_writes_sibling_by_default(self):
        tmp = tempfile.mkdtemp()
        try:
            dst = os.path.join(tmp, "wf.blueprint.md")
            shutil.copyfile(MINIMAL, dst)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main([dst])
            out_path = os.path.join(tmp, "wf.diagram.md")
            self.assertEqual(rc, 0)
            self.assertIn("Wrote " + out_path, buf.getvalue())
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), render_document(load_blueprint(dst), "wf"))
        finally:
            shutil.rmtree(tmp)

    def test_out_flag(self):
        tmp = tempfile.mkdtemp()
        try:
            out_path = os.path.join(tmp, "custom.md")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main([MINIMAL, "--out", out_path])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(out_path))
        finally:
            shutil.rmtree(tmp)

    def test_bad_input_exits_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([os.path.join(FIXTURES, "broken_no_yaml.blueprint.md")])
        self.assertEqual(rc, 2)
        self.assertIn("ERROR", buf.getvalue())

    def test_missing_file_exits_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([os.path.join(FIXTURES, "does_not_exist.blueprint.md")])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_cli -v`
Expected: FAIL — `ImportError: cannot import name 'main'`.

- [ ] **Step 3: Add the path helpers + `main`** (insert after `render_document`, before the `__main__` guard)

```python
def default_out_path(in_path: str) -> str:
    if in_path.endswith(".blueprint.md"):
        return in_path[: -len(".blueprint.md")] + ".diagram.md"
    if in_path.endswith(".md"):
        return in_path[: -len(".md")] + ".diagram.md"
    return in_path + ".diagram.md"


def blueprint_name(in_path: str) -> str:
    base = os.path.basename(in_path)
    for suf in (".blueprint.md", ".md"):
        if base.endswith(suf):
            return base[: -len(suf)]
    return base


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a workflow blueprint to a Mermaid diagram artifact.")
    parser.add_argument("path", help="path to <name>.blueprint.md")
    parser.add_argument("--out", help="output path (default: sibling <name>.diagram.md)")
    parser.add_argument("--stdout", action="store_true",
                        help="print the artifact to stdout instead of writing a file")
    args = parser.parse_args(argv)
    try:
        bp = load_blueprint(args.path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    doc = render_document(bp, blueprint_name(args.path))
    if args.stdout:
        sys.stdout.write(doc)
        return 0
    out_path = args.out or default_out_path(args.path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"Wrote {out_path}")
    return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest tests.test_cli -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the whole script suite**

Run: `cd skills/workflow-design-visualize/scripts && python3 -m unittest discover -s tests -t . -v`
Expected: PASS (all tests across the 6 test files).

- [ ] **Step 6: Smoke-test against the real youtube blueprint** (it lives in the untracked `workflows/` of the main checkout; copy it into a temp path to avoid touching it)

Run:
```bash
cp /home/dawti/je-dev-skills/workflows/youtube-curated-playlist.blueprint.md /tmp/yt.blueprint.md 2>/dev/null && \
python3 skills/workflow-design-visualize/scripts/visualize_blueprint.py /tmp/yt.blueprint.md --stdout | head -40 || \
echo "(youtube blueprint not present — skip; not required)"
```
Expected: a `flowchart TD` with the 11 steps in order, `summarize_each` carrying a `· parallelize` tag, `emit_output`/`persist_run_history` as deterministic rectangles, no gates (all `approval_gate: none`), no subagents subgraph (`subagents: []`), followed by the two tables. Eyeball that it reads correctly. Delete `/tmp/yt.blueprint.md` afterward.

- [ ] **Step 7: Commit**

```bash
git add skills/workflow-design-visualize/scripts/visualize_blueprint.py \
        skills/workflow-design-visualize/scripts/tests/test_cli.py
git commit -m "feat(T-016): CLI writes sibling .diagram.md with exit-2 bad-input parity"
```

---

## Task 7: `SKILL.md`

**Files:**
- Create: `skills/workflow-design-visualize/SKILL.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: workflow-design-visualize
description: This skill should be used when the user asks to "visualize my workflow", "render a blueprint diagram", "show a mermaid flowchart of my workflow", "draw the workflow steps", "see the workflow design as a picture", or right after workflow-design-validate passes and they want a diagram. It runs a deterministic yaml→Mermaid generator over ./workflows/<name>.blueprint.md and writes a <name>.diagram.md sibling with a flowchart and drill-down tables.
argument-hint: "[path to the blueprint; defaults to ./workflows/*.blueprint.md]"
allowed-tools: Bash, Read, Glob
version: 0.1.0
---

# Workflow Design: Visualize

Render a workflow blueprint to a Mermaid diagram. It reads the single fenced
`yaml` block of `<name>.blueprint.md` and writes a sibling `<name>.diagram.md`
holding a `flowchart` of the steps in **list order** — colored and shaped by
`kind` (rectangle = deterministic, rounded = agentic), with a `· <pattern>` tag
on each step, a hexagon `approval_gate` node after any gated step, and a separate
cluster for `subagents` — plus per-step and per-subagent drill-down tables. It is
offline and deterministic: no API key, no model call, no timestamp, so
regenerating produces byte-identical output.

## Precondition

A blueprint must exist (written by `workflow-design-interview` to
`./workflows/<name>.blueprint.md`). If the user passed a path, use it; otherwise
Glob `./workflows/*.blueprint.md`. If none exists, stop and point the user at
`workflow-design-interview`. Run this **after** `workflow-design-validate`
passes — a picture of an incomplete blueprint can mislead.

## Procedure

1. **Install deps once** (idempotent):

   ```bash
   pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-visualize/scripts/requirements.txt
   ```

2. **Run the generator** against the blueprint path:

   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-visualize/scripts/visualize_blueprint.py <path>
   ```

   It writes a sibling `<name>.diagram.md` and prints `Wrote <path>`. Exit codes:
   `0` = written, `2` = file unreadable or the blueprint has anything other than
   exactly one fenced `yaml` block. Add `--stdout` to print the artifact instead
   of writing it, or `--out <path>` to choose the output file.

3. **Show the result.** Read the generated `<name>.diagram.md` and tell the user
   where it is and how to view the flowchart: open it on GitHub (renders
   ` ```mermaid ` blocks natively), or in VS Code's Markdown preview with a
   Mermaid preview extension, or paste the `mermaid` block into mermaid.live. The
   drill-down tables are plain Markdown and render anywhere.

4. **Regenerate after edits.** The diagram is derived from the blueprint — after
   any change to the `yaml` block, re-run step 2. Do not hand-edit
   `<name>.diagram.md`.

## Definition of done

A sibling `<name>.diagram.md` exists next to the blueprint, contains one
`mermaid` flowchart that matches the blueprint's steps/subagents in list order,
and renders in a Mermaid-aware Markdown viewer.

## Notes

- **Deterministic and additive.** Same blueprint → byte-identical diagram. The
  generator only reads the v0.1 schema
  (`docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §4.1); it never edits the
  blueprint and never changes the schema.
- **Edges follow `steps` list order.** The v0.1 schema has no explicit
  `next`/`depends_on` field, so ordering is taken from the steps list (spec §7).
  Parallel fan-out is shown as a `· parallelize` tag, not as separate branches.
- **No fabricated subagent links.** Subagents render in their own cluster; the
  schema has no field tying a step to the subagent it delegates to, so no edges
  are drawn between steps and subagents.
- **Tier 1 of the visual viewer.** Per
  `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md` §3,
  this is the static-Mermaid tier; the interactive browser viewer (Tier 2) is
  gated and intentionally not built.
```

- [ ] **Step 2: Lint the skill**

Run (from repo root): `python3 tools/skill_lint.py --root .`
Expected: `14 skills | 0 errors | 0 warnings`.

- [ ] **Step 3: Commit**

```bash
git add skills/workflow-design-visualize/SKILL.md
git commit -m "feat(T-016): workflow-design-visualize skill shell"
```

---

## Task 8: Skill-shell + repo-metadata test

**Files:**
- Create: `tools/tests/test_workflow_design_visualize_skill.py`

- [ ] **Step 1: Write the failing test** — `tools/tests/test_workflow_design_visualize_skill.py`

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "workflow-design-visualize" / "SKILL.md"
SCRIPT = ROOT / "skills" / "workflow-design-visualize" / "scripts" / "visualize_blueprint.py"
REQS = ROOT / "skills" / "workflow-design-visualize" / "scripts" / "requirements.txt"


class TestWorkflowDesignVisualizeSkill(unittest.TestCase):
    def test_skill_frontmatter_and_procedure(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: workflow-design-visualize", text)
        self.assertIn("allowed-tools: Bash, Read, Glob", text)
        self.assertIn("<name>.diagram.md", text)
        self.assertIn("mermaid", text)
        self.assertIn("list order", text)
        self.assertIn("workflow-design-validate", text)
        self.assertIn(
            "${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-visualize/scripts/visualize_blueprint.py",
            text,
        )

    def test_requirements_pins_pyyaml(self):
        self.assertIn("PyYAML", REQS.read_text(encoding="utf-8"))

    def test_script_exists(self):
        self.assertTrue(SCRIPT.is_file())

    def test_readme_and_plugin_metadata_include_visualize(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        plugin = (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        self.assertIn("visualize", readme)
        self.assertIn("mermaid", plugin)
        self.assertIn("diagram", plugin)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run (from repo root): `python3 -m unittest discover -s tools/tests -t tools -v`
Expected: FAIL — `test_readme_and_plugin_metadata_include_visualize` fails (README/plugin not yet updated). The frontmatter test should already pass from Task 7.

- [ ] **Step 3: Leave failing** — the README/plugin updates land in Task 9, which makes this test green. Do not commit yet; proceed to Task 9.

---

## Task 9: Repo integration (README, plugin.json, AGENTS.md, specs)

**Files:**
- Modify: `README.md`
- Modify: `.claude-plugin/plugin.json`
- Modify: `AGENTS.md`
- Modify: `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md`
- Modify: `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md`

- [ ] **Step 1: README — add `visualize` to the group row.** Replace the `workflow-document-project` table row's invoke + blurb:

Find:
```
| `workflow-document-project` + `workflow-design-*` | `/je-dev-skills:workflow-document-project`, `/je-dev-skills:workflow-design-{interview,validate,advise,review}` | Start from an existing project inventory or from an idea, produce a draft `./workflows/<name>.blueprint.md`, validate structure, get model/effort advice, and run advisory semantic review. |
```
Replace with:
```
| `workflow-document-project` + `workflow-design-*` | `/je-dev-skills:workflow-document-project`, `/je-dev-skills:workflow-design-{interview,validate,advise,review,visualize}` | Start from an existing project inventory or from an idea, produce a draft `./workflows/<name>.blueprint.md`, validate structure, get model/effort advice, run advisory semantic review, and render a Mermaid diagram (`workflow-design-visualize`). |
```

- [ ] **Step 2: plugin.json — add keywords.** In the `keywords` array, append `"mermaid"`, `"diagram"`, `"visualization"` (before the closing `]`). The array's tail becomes:
```
... "project-documentation", "project-inventory", "inventory", "workflow-documentation", "mermaid", "diagram", "visualization"]
```

- [ ] **Step 3: AGENTS.md — add the test suite line.** In the `## Tests` fenced block, after the `workflow-document-project` discover line, add:
```
python3 -m unittest discover -s skills/workflow-design-visualize/scripts/tests -t skills/workflow-design-visualize/scripts
```

- [ ] **Step 4: Parent spec §9 — mark Tier 1 shipped.** In `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md`, replace the `*Tier 1 — Mermaid:*` bullet:

Find:
```
  - *Tier 1 — Mermaid:* deterministically generate a Mermaid flowchart from the same
    fenced `yaml` block and emit it alongside the blueprint. Renders for free in
    GitHub / VSCode / Markdown previews, zero runtime. The likely default tier.
```
Replace with:
```
  - *Tier 1 — Mermaid (shipped as `workflow-design-visualize`, T-016):* deterministically
    generates a Mermaid flowchart from the same fenced `yaml` block and emits a sibling
    `<name>.diagram.md` (flowchart in steps-list order + drill-down tables). Renders for
    free in GitHub / VSCode / Markdown previews, zero runtime. See
    `2026-05-30-workflow-design-advanced-tooling-spec.md` §3.6.
```

- [ ] **Step 5: Advanced-tooling spec §3.6 — flip "building" → "shipped".** In `docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md`, change the §3.6 heading and lead sentence:

Find:
```
### 3.6 Status — Tier 1 building (T-016)
Tier 1 is being built now: the user requested the visual aid, and per §3.4 Tier 1 is
```
Replace with:
```
### 3.6 Status — Tier 1 shipped (T-016)
Tier 1 is shipped: the user requested the visual aid, and per §3.4 Tier 1 is
```

- [ ] **Step 6: Run the tools/tests suite**

Run (from repo root): `python3 -m unittest discover -s tools/tests -t tools -v`
Expected: PASS — including `test_workflow_design_visualize_skill` (18 tests total: the prior 17 + the new file's class). If count differs, confirm the new test class is discovered and green.

- [ ] **Step 7: Commit**

```bash
git add README.md .claude-plugin/plugin.json AGENTS.md \
        docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md \
        docs/superpowers/specs/2026-05-30-workflow-design-advanced-tooling-spec.md \
        tools/tests/test_workflow_design_visualize_skill.py
git commit -m "feat(T-016): register visualize in README/plugin/AGENTS + mark Tier 1 shipped"
```

---

## Task 10: Full verification + reviews + closeout

- [ ] **Step 1: Run the full offline suite + linter from repo root** (paste actual output into the handover):

```bash
python3 tools/skill_lint.py --root .
python3 -m unittest discover -s tools/tests -t tools
(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)
python3 -m unittest discover -s skills/workflow-design-validate/scripts/tests -t skills/workflow-design-validate/scripts
python3 -m unittest discover -s skills/workflow-design-review/scripts/tests -t skills/workflow-design-review/scripts
python3 -m unittest discover -s skills/workflow-design-advise/scripts/tests -t skills/workflow-design-advise/scripts
python3 -m unittest discover -s skills/workflow-document-project/scripts/tests -t skills/workflow-document-project/scripts
python3 -m unittest discover -s skills/workflow-design-visualize/scripts/tests -t skills/workflow-design-visualize/scripts
```
Expected: linter `14 skills | 0 errors | 0 warnings`; every suite ends `OK`; the new visualize suite green.

- [ ] **Step 2: Two independent adversarial review rounds** (AGENTS.md). Use `superpowers:requesting-code-review` and/or a Workflow fan-out with these lenses, then address findings with `superpowers:receiving-code-review`:
  - **Correctness / spec-compliance** — does the encoding match §3.6 (list-order edges, kind→color+shape, pattern tag, gate-after, no subagent edges)? Any schema field mis-read?
  - **Mermaid validity / escaping** — can any blueprint value produce syntactically invalid Mermaid or break out of a label/quoted string? Node-id collisions?
  - **Tests / robustness** — are goldens meaningful? Edge cases (empty steps, non-dict entries, missing `kind`, gate on last step, duplicate ids across steps+subagents) covered?
  - **Determinism / drift** — is output byte-stable across runs and Python hash seeds? Any nondeterministic ordering (e.g. set iteration leaking into output)?
- [ ] **Step 3:** Fix valid findings; re-run the full suite + linter; record what was fixed/declined (with reasons) for the handover.
- [ ] **Step 4: Handover + lesson** — write `.story/handovers/` narrative (reference this plan filename) and any durable `.story/lessons/`. Mark ticket T-016 `complete`.
- [ ] **Step 5: Delete this plan** — `git rm docs/superpowers/plans/2026-05-31-T-016-workflow-design-visualize.md` on the branch before merge (AGENTS.md hard rule); reference it in the handover.
- [ ] **Step 6: Integrate** — merge the branch to `main` locally, re-run the full verification on `main`, remove the worktree, delete the local branch (AGENTS.md "Integrating and cleaning up").

---

## Self-review (against the spec)

**Spec coverage (advanced-tooling §3 / §3.6):**
- Deterministic `yaml`→Mermaid, offline fixture tests → Tasks 3, 6 (goldens, determinism tests). ✓
- Sibling `<name>.diagram.md` → Tasks 5, 6. ✓
- List-order edges → Task 3 (`flow`/`edge_lines`). ✓
- `kind` → color+shape+text → Task 3. ✓
- `pattern` → label tag → Task 3 (`_kind_tag`). ✓
- `approval_gate` → hexagon after step → Task 3 (gate node). ✓
- subagents → separate subgraph, no fabricated edges → Task 3 (`sub_lines`, no edges). ✓
- Drill-down tables → Task 4. ✓
- No timestamp / byte-stable → Tasks 5, 6 (determinism tests). ✓
- Exit-2 bad-input parity with validator → Tasks 1, 6. ✓
- Mermaid-safe ids + escaping + empty/missing handling → Tasks 2, 3. ✓
- Skill shell, run-after-validate precondition → Task 7. ✓
- README / plugin / AGENTS / parent-spec §9 / §3.6 updates → Task 9. ✓
- Tier 2 NOT built → enforced by omission; called out in SKILL.md + §3.6. ✓

**Placeholder scan:** none — every code/test step contains full content. ✓

**Type/name consistency:** the locked API list at the top matches every call site (`render_mermaid`, `render_step_table`, `render_subagent_table`, `render_document`, `default_out_path`, `blueprint_name`, `main`, `sanitize_node_id`, `escape_label`, `_kind_tag`, `_node`, `_cell`, `_yn`). ✓
