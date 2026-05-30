# Workflow Design Skills v0.1 Implementation Plan

> **Status: COMPLETED (2026-05-29).** Story ticket `T-002` is complete. The scoped deliverable landed as the v0.1 `workflow-design-*` group: `workflow-design-interview` with its staged reference material and blueprint template, plus `workflow-design-validate` with the deterministic `validate_blueprint.py` checker and offline fixtures.
>
> **Verified (2026-05-30).** `cd skills/workflow-design-validate/scripts && python3 -m unittest discover -s tests -v` ran 29 tests and passed. The validator accepts the valid fixtures, rejects incomplete blueprints with gap reports, and the bundled Example 1 from `blueprint-schema.md` validates at `Coverage: 12/12` with `PASS`.
>
> **Spec location note.** The workflow design spec has since moved under `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md`; references in this plan now point at the moved location.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v0.1 `workflow-design-*` skill group — a staged discovery interview that emits a Markdown+YAML workflow blueprint, plus a deterministic completeness validator.

**Architecture:** Two skills in the existing `je-dev-skills` plugin. `workflow-design-validate` wraps a pure-Python validator (`validate_blueprint.py`) that parses the single fenced `yaml` block from a blueprint and checks structural completeness against a fixed schema, emitting gaps + a coverage score. `workflow-design-interview` is an authored markdown skill (SKILL.md + `references/` + `assets/`) that runs a 7-stage elicitation and writes `./workflows/<name>.blueprint.md`. The validator is built TDD-first; the skills and references are authored content verified by running the validator against the bundled example.

**Tech Stack:** Python 3.10+, PyYAML, stdlib `unittest`, Markdown skills with YAML frontmatter.

**Spec:** [docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md](../specs/WORKFLOW_DESIGN_SPEC.md). Tasks reference it by section (§).

---

## File Structure

```
skills/workflow-design-validate/
  SKILL.md                              # Task 9
  scripts/
    validate_blueprint.py               # Tasks 2–7 (the validator)
    requirements.txt                    # Task 2
    tests/
      __init__.py                       # Task 2
      test_extract.py                   # Task 2
      test_dimensions.py                # Task 3
      test_steps.py                     # Task 4
      test_subagents.py                 # Task 5
      test_rubrics_outcomes.py          # Task 6
      test_cli.py                        # Task 7
      fixtures/
        valid_minimal.blueprint.md      # Task 2
        valid_full.blueprint.md         # Task 5
        broken_missing_rationale.blueprint.md       # Task 4
        broken_partial_contract.blueprint.md        # Task 5
        broken_gateless_rubric.blueprint.md         # Task 6
        broken_unaccounted_dimension.blueprint.md   # Task 3
skills/workflow-design-interview/
  SKILL.md                              # Task 11
  references/
    blueprint-schema.md                 # Task 8
    dimensions.md                       # Task 8
    question-bank.md                    # Task 10
    patterns.md                         # Task 10
    model-selection.md                  # Task 10
    rubric-templates.md                 # Task 10
    citations.md                        # Task 10
  assets/
    blueprint-template.md               # Task 8
docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md            # Task 1 (reconcile schema)
README.md                              # Task 12
.claude-plugin/plugin.json             # Task 12
```

The validator splits one concern per check function so each is testable in isolation. Fixtures are small and check-focused (one fixture exercises one failure), not the big realistic examples — those live in `references/blueprint-schema.md` as documentation (Task 8).

---

## Task 1: Reconcile the schema (add `side_effecting` / `reversible`)

The spec says `retry` is "required if side-effecting" and `rollback` "required if reversible," but the YAML has no field declaring those properties, so the check is undecidable. Add two boolean step fields and update the validator-check description to match.

**Files:**
- Modify: `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md`

- [ ] **Step 1: Add the boolean fields to the §4.1 step schema**

In `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md`, find the `steps:` block in §4.1 and add two lines immediately after the `pattern:` line:

```yaml
    side_effecting: true|false               # declares external side effects → drives the retry check
    reversible: true|false                   # declares the step can be undone → drives the rollback check
```

- [ ] **Step 2: Update the §5 conditional-check bullet**

Replace this bullet in §5:

```
- Any side-effecting step has `retry` with an `idempotency_key`; any reversible step
  has `rollback`; any loop or agentic step has a non-empty `termination`.
```

with:

```
- Any step with `side_effecting: true` has `retry.idempotency_key`; any step with
  `reversible: true` has `rollback`; any `agentic` step has a non-empty `termination`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md
git commit -m "Reconcile blueprint schema: add side_effecting/reversible booleans"
```

---

## Task 2: Validator skeleton + YAML extraction (TDD)

**Files:**
- Create: `skills/workflow-design-validate/scripts/validate_blueprint.py`
- Create: `skills/workflow-design-validate/scripts/requirements.txt`
- Create: `skills/workflow-design-validate/scripts/tests/__init__.py`
- Create: `skills/workflow-design-validate/scripts/tests/test_extract.py`
- Create: `skills/workflow-design-validate/scripts/tests/fixtures/valid_minimal.blueprint.md`

- [ ] **Step 1: Create the requirements file and test package init**

`skills/workflow-design-validate/scripts/requirements.txt`:

```
PyYAML>=6.0
```

`skills/workflow-design-validate/scripts/tests/__init__.py`: empty file.

- [ ] **Step 2: Create the minimal valid fixture**

`skills/workflow-design-validate/scripts/tests/fixtures/valid_minimal.blueprint.md`:

````markdown
---
name: minimal
version: 0.1.0
status: draft
created: 2026-05-29
---
# Minimal blueprint

Prose for humans.

```yaml
preconditions: ["input file exists"]
inputs:
  - {key: path, description: "input path", format: "string"}
dependencies: []
outputs: ["summary"]
postconditions: ["summary written once"]
steps:
  - id: transform
    kind: deterministic
    rationale: "pure data transform; must be exact"
    pattern: none
    side_effecting: false
    reversible: false
    termination: "single pass"
subagents: []
dimensions:
  observability: specified
  cost_latency_budgets: {n/a: "trivial job"}
  guardrails_permissions: specified
  context_management: {n/a: "no LLM"}
  human_in_the_loop: {n/a: "low-risk"}
  state_artifact_passing: {n/a: "no handoff"}
  failure_handling: specified
  retry_idempotency: {n/a: "read-only"}
  rollback_compensation: {n/a: "read-only"}
  termination_conditions: specified
  tool_selection: {n/a: "no tools"}
  evaluation_success: specified
rubrics: []
outcomes:
  - {given: "a valid input", when: "the job runs", then: "one summary produced"}
budgets: {max_turns: 0, max_tool_calls: 0, latency_note: "<10s", cost_note: "~$0"}
guardrails: ["read-only input"]
```
````

- [ ] **Step 3: Write the failing test for extraction**

`skills/workflow-design-validate/scripts/tests/test_extract.py`:

```python
import os
import unittest

from validate_blueprint import extract_yaml_block, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtract(unittest.TestCase):
    def test_extracts_single_yaml_block(self):
        text = "intro\n```yaml\na: 1\n```\noutro"
        self.assertEqual(extract_yaml_block(text).strip(), "a: 1")

    def test_rejects_zero_blocks(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("no fenced yaml here")

    def test_rejects_multiple_blocks(self):
        text = "```yaml\na: 1\n```\n```yaml\nb: 2\n```"
        with self.assertRaises(ValueError):
            extract_yaml_block(text)

    def test_load_blueprint_returns_dict(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        self.assertEqual(bp["name"] if "name" in bp else bp["steps"][0]["id"], "transform")
        self.assertEqual(bp["steps"][0]["kind"], "deterministic")
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_extract -v`
Expected: FAIL — `ImportError` / `cannot import name 'extract_yaml_block'`.

- [ ] **Step 5: Implement extraction and loading**

`skills/workflow-design-validate/scripts/validate_blueprint.py`:

```python
"""Deterministic completeness validator for workflow blueprints.

Parses the single fenced ```yaml block from a <name>.blueprint.md file and
checks it against the schema in docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md §4.1.
"""
import argparse
import re
import sys
from dataclasses import dataclass

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)

REQUIRED_DIMENSIONS = [
    "observability", "cost_latency_budgets", "guardrails_permissions",
    "context_management", "human_in_the_loop", "state_artifact_passing",
    "failure_handling", "retry_idempotency", "rollback_compensation",
    "termination_conditions", "tool_selection", "evaluation_success",
]
VALID_KINDS = {"deterministic", "agentic"}
CONTRACT_FIELDS = ["objective", "output_format", "tools", "boundaries", "model", "effort"]


@dataclass
class Gap:
    path: str
    message: str

    def __str__(self):
        return f"{self.path}: {self.message}"


def extract_yaml_block(text: str) -> str:
    blocks = YAML_FENCE.findall(text)
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```yaml block, found {len(blocks)}")
    return blocks[0]


def load_blueprint(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return yaml.safe_load(extract_yaml_block(text))


def _nonempty(value) -> bool:
    return value is not None and str(value).strip() != ""
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd skills/workflow-design-validate/scripts && pip install -r requirements.txt && python -m unittest tests.test_extract -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add skills/workflow-design-validate/scripts/
git commit -m "Add blueprint validator: YAML extraction + loading (TDD)"
```

---

## Task 3: Dimension coverage check (TDD)

**Files:**
- Modify: `skills/workflow-design-validate/scripts/validate_blueprint.py`
- Create: `skills/workflow-design-validate/scripts/tests/test_dimensions.py`
- Create: `skills/workflow-design-validate/scripts/tests/fixtures/broken_unaccounted_dimension.blueprint.md`

- [ ] **Step 1: Create the broken fixture (one dimension left blank)**

Copy `valid_minimal.blueprint.md` to `broken_unaccounted_dimension.blueprint.md` and change the `observability:` line inside the yaml block from `observability: specified` to:

```yaml
  observability:
```

(an empty value — neither `specified` nor an `n/a` mapping).

- [ ] **Step 2: Write the failing test**

`skills/workflow-design-validate/scripts/tests/test_dimensions.py`:

```python
import os
import unittest

from validate_blueprint import check_dimensions, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestDimensions(unittest.TestCase):
    def test_valid_minimal_all_accounted(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        gaps, (accounted, total) = check_dimensions(bp)
        self.assertEqual(gaps, [])
        self.assertEqual((accounted, total), (12, 12))

    def test_na_with_rationale_counts_as_accounted(self):
        bp = {"dimensions": {d: {"n/a": "reason"} for d in
                             __import__("validate_blueprint").REQUIRED_DIMENSIONS}}
        gaps, (accounted, total) = check_dimensions(bp)
        self.assertEqual(gaps, [])
        self.assertEqual(accounted, 12)

    def test_blank_dimension_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_unaccounted_dimension.blueprint.md"))
        gaps, (accounted, total) = check_dimensions(bp)
        self.assertTrue(any(g.path == "dimensions.observability" for g in gaps))
        self.assertEqual(accounted, 11)

    def test_missing_dimension_key_is_a_gap(self):
        bp = {"dimensions": {}}
        gaps, _ = check_dimensions(bp)
        self.assertEqual(len(gaps), 12)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_dimensions -v`
Expected: FAIL — `cannot import name 'check_dimensions'`.

- [ ] **Step 4: Implement `check_dimensions`**

Append to `validate_blueprint.py`:

```python
def check_dimensions(bp: dict):
    gaps = []
    dims = bp.get("dimensions") or {}
    accounted = 0
    for name in REQUIRED_DIMENSIONS:
        if name not in dims:
            gaps.append(Gap(f"dimensions.{name}",
                            "missing — must be 'specified' or {n/a: <rationale>}"))
            continue
        val = dims[name]
        if val == "specified":
            accounted += 1
        elif isinstance(val, dict) and _nonempty(val.get("n/a")):
            accounted += 1
        else:
            gaps.append(Gap(f"dimensions.{name}",
                            "must be 'specified' or {n/a: <non-empty rationale>}"))
    return gaps, (accounted, len(REQUIRED_DIMENSIONS))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_dimensions -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add skills/workflow-design-validate/scripts/
git commit -m "Add dimension coverage check + score (TDD)"
```

---

## Task 4: Steps check (TDD)

**Files:**
- Modify: `skills/workflow-design-validate/scripts/validate_blueprint.py`
- Create: `skills/workflow-design-validate/scripts/tests/test_steps.py`
- Create: `skills/workflow-design-validate/scripts/tests/fixtures/broken_missing_rationale.blueprint.md`

- [ ] **Step 1: Create the broken fixture (step missing rationale)**

Copy `valid_minimal.blueprint.md` to `broken_missing_rationale.blueprint.md` and delete the `rationale:` line of the `transform` step inside the yaml block.

- [ ] **Step 2: Write the failing test**

`skills/workflow-design-validate/scripts/tests/test_steps.py`:

```python
import os
import unittest

from validate_blueprint import check_steps, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestSteps(unittest.TestCase):
    def test_valid_minimal_has_no_step_gaps(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        self.assertEqual(check_steps(bp), [])

    def test_missing_rationale_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_missing_rationale.blueprint.md"))
        gaps = check_steps(bp)
        self.assertTrue(any("rationale" in g.path for g in gaps))

    def test_invalid_kind_is_a_gap(self):
        bp = {"steps": [{"id": "x", "kind": "magic", "rationale": "r"}]}
        gaps = check_steps(bp)
        self.assertTrue(any(g.path == "steps[0].kind" for g in gaps))

    def test_agentic_step_requires_termination(self):
        bp = {"steps": [{"id": "x", "kind": "agentic", "rationale": "judgment"}]}
        gaps = check_steps(bp)
        self.assertTrue(any(g.path == "steps[0].termination" for g in gaps))

    def test_side_effecting_requires_idempotency_key(self):
        bp = {"steps": [{"id": "x", "kind": "deterministic", "rationale": "r",
                         "side_effecting": True, "retry": {"policy": "x3"}}]}
        gaps = check_steps(bp)
        self.assertTrue(any("idempotency_key" in g.path for g in gaps))

    def test_reversible_requires_rollback(self):
        bp = {"steps": [{"id": "x", "kind": "deterministic", "rationale": "r",
                         "reversible": True}]}
        gaps = check_steps(bp)
        self.assertTrue(any(g.path == "steps[0].rollback" for g in gaps))
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_steps -v`
Expected: FAIL — `cannot import name 'check_steps'`.

- [ ] **Step 4: Implement `check_steps`**

Append to `validate_blueprint.py`:

```python
def check_steps(bp: dict):
    gaps = []
    for i, step in enumerate(bp.get("steps") or []):
        p = f"steps[{i}]"
        if step.get("kind") not in VALID_KINDS:
            gaps.append(Gap(f"{p}.kind", f"must be one of {sorted(VALID_KINDS)}"))
        if not _nonempty(step.get("rationale")):
            gaps.append(Gap(f"{p}.rationale", "missing — required for every step"))
        if step.get("kind") == "agentic" and not _nonempty(step.get("termination")):
            gaps.append(Gap(f"{p}.termination", "required for agentic steps"))
        if step.get("side_effecting"):
            retry = step.get("retry") or {}
            if not _nonempty(retry.get("idempotency_key")):
                gaps.append(Gap(f"{p}.retry.idempotency_key",
                                "required for side_effecting steps"))
        if step.get("reversible") and not _nonempty(step.get("rollback")):
            gaps.append(Gap(f"{p}.rollback", "required for reversible steps"))
    return gaps
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_steps -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add skills/workflow-design-validate/scripts/
git commit -m "Add steps check: kind, rationale, termination, retry, rollback (TDD)"
```

---

## Task 5: Subagents contract check (TDD)

**Files:**
- Modify: `skills/workflow-design-validate/scripts/validate_blueprint.py`
- Create: `skills/workflow-design-validate/scripts/tests/test_subagents.py`
- Create: `skills/workflow-design-validate/scripts/tests/fixtures/valid_full.blueprint.md`
- Create: `skills/workflow-design-validate/scripts/tests/fixtures/broken_partial_contract.blueprint.md`

- [ ] **Step 1: Create `valid_full.blueprint.md` (agentic step + complete subagent)**

`skills/workflow-design-validate/scripts/tests/fixtures/valid_full.blueprint.md`:

````markdown
---
name: full
version: 0.1.0
status: draft
created: 2026-05-29
---
# Full blueprint

```yaml
preconditions: ["a question and competitor list"]
inputs:
  - {key: question, description: "what to answer", format: "string"}
dependencies: ["web search"]
outputs: ["cited brief"]
postconditions: ["every claim cited"]
steps:
  - id: research
    kind: agentic
    rationale: "open-ended; needs judgment"
    pattern: parallelize
    side_effecting: false
    reversible: false
    termination: "all workers return or 2 dry rounds"
subagents:
  - id: researcher
    objective: "research one competitor"
    output_format: "JSON {competitor, findings[], sources[]}"
    tools: [web_search, web_fetch]
    boundaries: "only the assigned competitor; do not synthesize"
    model: sonnet
    effort: medium
dimensions:
  observability: specified
  cost_latency_budgets: specified
  guardrails_permissions: specified
  context_management: specified
  human_in_the_loop: specified
  state_artifact_passing: specified
  failure_handling: specified
  retry_idempotency: specified
  rollback_compensation: {n/a: "read-only research"}
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: specified
rubrics:
  - name: completeness
    scale: 1-5
    levels: {1: "missing competitors", 3: "shallow", 5: "deep, all covered"}
    gate: 4
    reference_based: false
    judge: llm
outcomes:
  - {given: "a question + 4 competitors", when: "the workflow runs", then: "a cited brief covering all 4"}
budgets: {max_turns: 30, max_tool_calls: 60, latency_note: "<5m", cost_note: "~15x a chat"}
guardrails: ["subagents read-only"]
```
````

- [ ] **Step 2: Create `broken_partial_contract.blueprint.md`**

Copy `valid_full.blueprint.md` to `broken_partial_contract.blueprint.md` and delete the `boundaries:` line from the `researcher` subagent.

- [ ] **Step 3: Write the failing test**

`skills/workflow-design-validate/scripts/tests/test_subagents.py`:

```python
import os
import unittest

from validate_blueprint import check_subagents, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestSubagents(unittest.TestCase):
    def test_complete_contract_passes(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_full.blueprint.md"))
        self.assertEqual(check_subagents(bp), [])

    def test_partial_contract_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_partial_contract.blueprint.md"))
        gaps = check_subagents(bp)
        self.assertTrue(any(g.path == "subagents[0].boundaries" for g in gaps))

    def test_empty_tools_is_a_gap(self):
        bp = {"steps": [{"id": "a", "kind": "agentic", "rationale": "r", "termination": "x"}],
              "subagents": [{"objective": "o", "output_format": "f", "tools": [],
                             "boundaries": "b", "model": "sonnet", "effort": "low"}]}
        gaps = check_subagents(bp)
        self.assertTrue(any(g.path == "subagents[0].tools" for g in gaps))

    def test_subagents_without_agentic_step_is_a_gap(self):
        bp = {"steps": [{"id": "a", "kind": "deterministic", "rationale": "r"}],
              "subagents": [{"objective": "o", "output_format": "f", "tools": ["x"],
                             "boundaries": "b", "model": "sonnet", "effort": "low"}]}
        gaps = check_subagents(bp)
        self.assertTrue(any(g.path == "subagents" for g in gaps))
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_subagents -v`
Expected: FAIL — `cannot import name 'check_subagents'`.

- [ ] **Step 5: Implement `check_subagents`**

Append to `validate_blueprint.py`:

```python
def check_subagents(bp: dict):
    gaps = []
    subs = bp.get("subagents") or []
    steps = bp.get("steps") or []
    if subs and not any(s.get("kind") == "agentic" for s in steps):
        gaps.append(Gap("subagents", "present but no agentic step justifies them"))
    for i, sa in enumerate(subs):
        p = f"subagents[{i}]"
        for field in CONTRACT_FIELDS:
            val = sa.get(field)
            if field == "tools":
                if not (isinstance(val, list) and len(val) > 0):
                    gaps.append(Gap(f"{p}.tools",
                                    "must be a non-empty list (least-privilege allowlist)"))
            elif not _nonempty(val):
                gaps.append(Gap(f"{p}.{field}", "missing — part of the required contract"))
    return gaps
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_subagents -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add skills/workflow-design-validate/scripts/
git commit -m "Add subagent four-part contract check (TDD)"
```

---

## Task 6: Rubrics + outcomes checks (TDD)

**Files:**
- Modify: `skills/workflow-design-validate/scripts/validate_blueprint.py`
- Create: `skills/workflow-design-validate/scripts/tests/test_rubrics_outcomes.py`
- Create: `skills/workflow-design-validate/scripts/tests/fixtures/broken_gateless_rubric.blueprint.md`

- [ ] **Step 1: Create `broken_gateless_rubric.blueprint.md`**

Copy `valid_full.blueprint.md` to `broken_gateless_rubric.blueprint.md` and delete the `gate: 4` line from the `completeness` rubric.

- [ ] **Step 2: Write the failing test**

`skills/workflow-design-validate/scripts/tests/test_rubrics_outcomes.py`:

```python
import os
import unittest

from validate_blueprint import check_rubrics, check_outcomes, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRubricsOutcomes(unittest.TestCase):
    def test_valid_full_rubrics_pass(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_full.blueprint.md"))
        self.assertEqual(check_rubrics(bp), [])

    def test_gateless_rubric_is_a_gap(self):
        bp = load_blueprint(os.path.join(FIXTURES, "broken_gateless_rubric.blueprint.md"))
        gaps = check_rubrics(bp)
        self.assertTrue(any(g.path == "rubrics[0].gate" for g in gaps))

    def test_rubric_without_levels_is_a_gap(self):
        bp = {"rubrics": [{"name": "x", "scale": "1-5", "gate": 3}]}
        gaps = check_rubrics(bp)
        self.assertTrue(any(g.path == "rubrics[0].levels" for g in gaps))

    def test_valid_full_outcomes_pass(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_full.blueprint.md"))
        self.assertEqual(check_outcomes(bp), [])

    def test_outcome_missing_then_is_a_gap(self):
        bp = {"outcomes": [{"given": "g", "when": "w"}]}
        gaps = check_outcomes(bp)
        self.assertTrue(any(g.path == "outcomes[0].then" for g in gaps))
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_rubrics_outcomes -v`
Expected: FAIL — `cannot import name 'check_rubrics'`.

- [ ] **Step 4: Implement `check_rubrics` and `check_outcomes`**

Append to `validate_blueprint.py`:

```python
def check_rubrics(bp: dict):
    gaps = []
    for i, r in enumerate(bp.get("rubrics") or []):
        p = f"rubrics[{i}]"
        if not _nonempty(r.get("scale")):
            gaps.append(Gap(f"{p}.scale", "missing categorical scale"))
        levels = r.get("levels")
        if not (isinstance(levels, dict) and len(levels) > 0):
            gaps.append(Gap(f"{p}.levels", "must define at least one level"))
        if r.get("gate") is None:
            gaps.append(Gap(f"{p}.gate", "missing pass/fail threshold"))
    return gaps


def check_outcomes(bp: dict):
    gaps = []
    for i, o in enumerate(bp.get("outcomes") or []):
        p = f"outcomes[{i}]"
        for field in ("given", "when", "then"):
            if not _nonempty(o.get(field)):
                gaps.append(Gap(f"{p}.{field}", "missing — outcomes must be Given-When-Then"))
    return gaps
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_rubrics_outcomes -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add skills/workflow-design-validate/scripts/
git commit -m "Add rubric and outcome checks (TDD)"
```

---

## Task 7: Aggregate `validate` + CLI (TDD)

**Files:**
- Modify: `skills/workflow-design-validate/scripts/validate_blueprint.py`
- Create: `skills/workflow-design-validate/scripts/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`skills/workflow-design-validate/scripts/tests/test_cli.py`:

```python
import os
import unittest

from validate_blueprint import validate, main, load_blueprint

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestValidateAndCli(unittest.TestCase):
    def test_valid_minimal_validates_clean(self):
        bp = load_blueprint(os.path.join(FIXTURES, "valid_minimal.blueprint.md"))
        gaps, (accounted, total) = validate(bp)
        self.assertEqual(gaps, [])
        self.assertEqual((accounted, total), (12, 12))

    def test_main_returns_zero_on_valid(self):
        rc = main([os.path.join(FIXTURES, "valid_minimal.blueprint.md")])
        self.assertEqual(rc, 0)

    def test_main_returns_one_on_gaps(self):
        rc = main([os.path.join(FIXTURES, "broken_missing_rationale.blueprint.md")])
        self.assertEqual(rc, 1)

    def test_main_returns_two_on_unreadable(self):
        rc = main([os.path.join(FIXTURES, "does_not_exist.blueprint.md")])
        self.assertEqual(rc, 2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest tests.test_cli -v`
Expected: FAIL — `cannot import name 'validate'` / `main`.

- [ ] **Step 3: Implement `validate` and `main`**

Append to `validate_blueprint.py`:

```python
def validate(bp: dict):
    gaps = []
    dim_gaps, coverage = check_dimensions(bp)
    gaps += dim_gaps
    gaps += check_steps(bp)
    gaps += check_subagents(bp)
    gaps += check_rubrics(bp)
    gaps += check_outcomes(bp)
    return gaps, coverage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a workflow blueprint for completeness.")
    parser.add_argument("path", help="path to <name>.blueprint.md")
    args = parser.parse_args(argv)
    try:
        bp = load_blueprint(args.path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    gaps, (accounted, total) = validate(bp)
    print(f"Coverage: {accounted}/{total} dimensions accounted for")
    if gaps:
        print(f"\n{len(gaps)} gap(s):")
        for gap in gaps:
            print(f"  - {gap}")
        print("\nFAIL")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest discover -s tests -v`
Expected: PASS (all tests across all modules).

- [ ] **Step 5: Smoke-run the CLI by hand**

Run: `cd skills/workflow-design-validate/scripts && python validate_blueprint.py tests/fixtures/valid_minimal.blueprint.md`
Expected: prints `Coverage: 12/12 dimensions accounted for` then `PASS`, exit 0.

Run: `cd skills/workflow-design-validate/scripts && python validate_blueprint.py tests/fixtures/broken_missing_rationale.blueprint.md; echo "exit=$?"`
Expected: lists a `steps[0].rationale` gap, prints `FAIL`, `exit=1`.

- [ ] **Step 6: Commit**

```bash
git add skills/workflow-design-validate/scripts/
git commit -m "Add aggregate validate() + CLI with exit codes (TDD)"
```

---

## Task 8: Interview `blueprint-schema.md`, `dimensions.md`, and the blueprint template

These are authored reference content. The schema reference embeds the three worked examples from spec §4.2; the template is the skeleton the interview fills.

**Files:**
- Create: `skills/workflow-design-interview/references/blueprint-schema.md`
- Create: `skills/workflow-design-interview/references/dimensions.md`
- Create: `skills/workflow-design-interview/assets/blueprint-template.md`

- [ ] **Step 1: Write `blueprint-schema.md`**

Content: (a) a prose explanation of the three-layer artifact (frontmatter / prose / single fenced `yaml` block) from spec §4; (b) the full annotated `yaml` schema copied from spec §4.1 **including** the `side_effecting`/`reversible` fields added in Task 1; (c) the three complete worked-example blueprints. Use spec §4.2 Examples 1–3 — author the full YAML for each (Example 1 = the deterministic CSV→Slack job, Example 2 = the email-routing single-agent workflow, Example 3 = the orchestrator-workers research brief). Start the file with a table of contents (the file exceeds 100 lines).

- [ ] **Step 2: Write `dimensions.md` (the normative checklist)**

One section per dimension in `REQUIRED_DIMENSIONS` (the 12 in spec §4.1), each with: a one-line definition, what "specified" requires, and when `n/a` is legitimate. Order matches the schema. End with the rule: *a blueprint is complete only when every dimension is `specified` or `{n/a: <rationale>}`.* Cross-reference the grounding in spec §10 (failure modes, retry/idempotency, HITL, artifact pattern, observability, guardrails, budgets, termination, rollback, tool selection, evaluation).

- [ ] **Step 3: Write `blueprint-template.md` (the skeleton)**

A copy of the schema with empty/`<placeholder>` values and the three layers in place (frontmatter, the prose section headings: Purpose / Stakeholders & context / Rationale, and the single fenced `yaml` block with every top-level key present and all 12 dimensions listed). This is a starting skeleton, so it is *expected to fail* validation until filled — note that at the top of the file in an HTML comment.

- [ ] **Step 4: Verify Example 1 from the schema passes the validator**

Extract Example 1's blueprint from `blueprint-schema.md` into a temp file and validate it:

```bash
cd skills/workflow-design-interview
# manually copy Example 1's full markdown (frontmatter + yaml block) into /tmp/example1.blueprint.md
python ../workflow-design-validate/scripts/validate_blueprint.py /tmp/example1.blueprint.md; echo "exit=$?"
```

Expected: `Coverage: 12/12`, `PASS`, `exit=0`. If it fails, fix the example in `blueprint-schema.md` until green, then delete `/tmp/example1.blueprint.md`.

- [ ] **Step 5: Commit**

```bash
git add skills/workflow-design-interview/references/blueprint-schema.md \
        skills/workflow-design-interview/references/dimensions.md \
        skills/workflow-design-interview/assets/blueprint-template.md
git commit -m "Add blueprint schema reference, dimensions checklist, and template"
```

---

## Task 9: `workflow-design-validate` SKILL.md

**Files:**
- Create: `skills/workflow-design-validate/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

Frontmatter (verbatim):

```yaml
---
name: workflow-design-validate
description: This skill should be used when the user asks to "validate a workflow blueprint", "check a blueprint", "is my workflow design complete", "lint a workflow blueprint", or right after workflow-design-interview produces one. It runs a deterministic completeness check over ./workflows/<name>.blueprint.md and reports the gaps to fix.
argument-hint: "[path to the blueprint; defaults to ./workflows/*.blueprint.md]"
allowed-tools: Bash, Read, Edit, Glob
version: 0.1.0
---
```

Body sections:
- **Precondition** — a blueprint file exists (from `workflow-design-interview`). If none, point the user there.
- **Procedure**: (1) install deps once: `pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-validate/scripts/requirements.txt`; (2) run `python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-validate/scripts/validate_blueprint.py <path>`; (3) read the coverage score + gap report; (4) fix each gap by editing the blueprint's `yaml` block; (5) re-run until `PASS` / exit 0.
- **Definition of done** — exit code 0 and `12/12 dimensions accounted for`.
- **Notes** — the check is structural only (offline, no API key); semantic quality review is a planned v0.2 layer (link spec §9).

Keep the body under ~120 lines.

- [ ] **Step 2: Verify the skill runs end-to-end**

Run: `python skills/workflow-design-validate/scripts/validate_blueprint.py skills/workflow-design-validate/scripts/tests/fixtures/valid_full.blueprint.md; echo "exit=$?"`
Expected: `Coverage: 12/12`, `PASS`, `exit=0`.

- [ ] **Step 3: Commit**

```bash
git add skills/workflow-design-validate/SKILL.md
git commit -m "Add workflow-design-validate SKILL.md"
```

---

## Task 10: Interview reference content (question bank, patterns, model-selection, rubric templates, citations)

**Files:**
- Create: `skills/workflow-design-interview/references/question-bank.md`
- Create: `skills/workflow-design-interview/references/patterns.md`
- Create: `skills/workflow-design-interview/references/model-selection.md`
- Create: `skills/workflow-design-interview/references/rubric-templates.md`
- Create: `skills/workflow-design-interview/references/citations.md`

- [ ] **Step 1: Write `question-bank.md`**

One section per interview stage (spec §6 stages 1–7). For each stage list concrete open questions then closed confirmations. Include the "5 Whys" prompt (stage 1), MoSCoW prompts (stage 2), the closed-input-set elicitation with units/format (stage 3), the determinism-classification questions (stage 4), the per-dimension prompts (stage 5, cross-referencing `dimensions.md`), and the rubric/outcome prompts (stage 6). End with the saturation-check question (stage 7).

- [ ] **Step 2: Write `patterns.md`**

The five Building-Effective-Agents patterns (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer) + the augmented-LLM building block, each with: one-line definition, when to use, and the matching `pattern:` value. Add the **simplicity-first escalation rules**: prefer deterministic code; an inline LLM call is not a subagent; only escalate to subagents for genuinely independent, breadth-first work (cite the ~15× token cost); the four-part subagent contract; the one-level-deep nesting constraint; every loop needs a termination condition. Ground in spec §10.

- [ ] **Step 3: Write `model-selection.md`**

Guidelines to pick a Claude `model` + `effort` per agentic step/subagent from: desired output (structure/fidelity), task complexity, and cost/token minimization. Include the routing heuristic (easy → Haiku, harder → Sonnet/Opus) and the effort-scaling heuristics (simple fact-finding → 1 agent / few tool calls; comparisons → 2–4 subagents; complex → 10+). State **Claude models only for now**, and that concrete model IDs live in `citations.md` so they update with the lineup.

- [ ] **Step 4: Write `rubric-templates.md`**

Reusable rubric shapes: categorical integer scale (not floats), explicit per-level definitions, a pass/fail `gate`, `reference_based` vs reference-free, and `judge: human|llm`. Provide 2–3 filled templates (e.g. correctness, completeness, citation-fidelity) matching the schema's `rubrics` shape. Note the link to the existing `prompt-evals-*` lifecycle (spec §8).

- [ ] **Step 5: Write `citations.md`**

Dated source list from spec §10 (Agent Skills best practices, Claude Code sub-agents doc, Building Effective Agents, the multi-agent research post, requirements-engineering and evaluation sources). Add a **volatile-values** subsection: current Claude model IDs, the Task→Agent tool rename note, and the caveat that "max parallel subagents" is community lore. Mark each with a "as of" date.

- [ ] **Step 6: Commit**

```bash
git add skills/workflow-design-interview/references/
git commit -m "Add interview reference content: questions, patterns, model selection, rubrics, citations"
```

---

## Task 11: `workflow-design-interview` SKILL.md

**Files:**
- Create: `skills/workflow-design-interview/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

Frontmatter (verbatim):

```yaml
---
name: workflow-design-interview
description: This skill should be used when the user wants to "design a workflow", "scope an automation, agent, or pipeline before building", "turn an idea into a workflow blueprint", "plan an agentic workflow", or needs a structured discovery interview before implementation. It runs a staged elicitation and writes a checked ./workflows/<name>.blueprint.md.
argument-hint: "[short name for the workflow, e.g. order-refund]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---
```

Body (acts as a table of contents, ≤500 lines): the 7 stages from spec §6, each as a numbered section that names the questions to ask (deferring detail to `references/question-bank.md`), the reference file to load at that stage (progressive disclosure), and the blueprint fields it fills. Stage 4 must state the simplicity-first rule and load `references/patterns.md` + `references/model-selection.md`. Stage 5 loads `references/dimensions.md` and requires every dimension be `specified` or `{n/a: rationale}`. Stage 7 writes the blueprint from `assets/blueprint-template.md` to `./workflows/<name>.blueprint.md`, runs the saturation check, and hands off to `workflow-design-validate`. Include a "Style" note: open questions then closed confirmations, explain-the-why over all-caps, cite volatile details from `references/citations.md`. Include a "Definition of done" section: a blueprint file written that passes `workflow-design-validate`.

- [ ] **Step 2: Verify the SKILL.md body length and frontmatter**

Run: `wc -l < skills/workflow-design-interview/SKILL.md`
Expected: under 500.
Then confirm by eye that `name` and `description` are present in the frontmatter and the description is under 1024 characters.

- [ ] **Step 3: Commit**

```bash
git add skills/workflow-design-interview/SKILL.md
git commit -m "Add workflow-design-interview SKILL.md"
```

---

## Task 12: Wire into the plugin (README + plugin.json) and final verification

**Files:**
- Modify: `README.md`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Update `plugin.json`**

Edit the `description` to mention both skill groups, and extend `keywords` with `"workflow"`, `"orchestration"`, `"blueprint"`, `"agent-design"`. Example new description:

```json
  "description": "A personal collection of Claude Code skills. Includes a prompt/agent evaluation lifecycle (prompt-evals-*) and a workflow-design lifecycle (workflow-design-interview, -validate) that turns an idea into a checked workflow blueprint.",
```

- [ ] **Step 2: Add a Workflow Design section to `README.md`**

Add a table mirroring the existing Skills table, listing `workflow-design-interview` and `workflow-design-validate` with their invoke commands and one-line descriptions, plus a line noting the lifecycle **interview → validate (repeat)** and a link to [docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md](docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md).

- [ ] **Step 3: Run the full validator test suite one last time**

Run: `cd skills/workflow-design-validate/scripts && python -m unittest discover -s tests -v`
Expected: PASS, all tests green.

- [ ] **Step 4: Dogfood — validate the bundled Example 1 and the template**

Run the validator against Example 1 (extracted to a temp file as in Task 8 Step 4): expect `PASS`.
Run it against `assets/blueprint-template.md`: expect `FAIL` (the empty skeleton is intentionally incomplete) — this confirms the validator catches incompleteness.

- [ ] **Step 5: Commit**

```bash
git add README.md .claude-plugin/plugin.json
git commit -m "Wire workflow-design-* group into plugin README and manifest"
```

---

## Self-Review Notes (for the implementer)

- **Spec coverage:** §2 lifecycle → Tasks 9, 11; §3 layout → all tasks; §4 artifact → Tasks 2, 8; §5 validator → Tasks 2–7, 9; §6 interview → Tasks 8, 10, 11; §8 testing → Tasks 2–7, 12; §11 definition of done → Task 12. v0.2 items (§9) are intentionally out of scope.
- **Type consistency:** function names used across tasks — `extract_yaml_block`, `load_blueprint`, `check_dimensions`, `check_steps`, `check_subagents`, `check_rubrics`, `check_outcomes`, `validate`, `main`; module-level `REQUIRED_DIMENSIONS` (12 entries), `VALID_KINDS`, `CONTRACT_FIELDS`, `Gap(path, message)`. Exit codes: 0 pass / 1 gaps / 2 unreadable.
- **PyYAML:** tests import `yaml`; `pip install -r requirements.txt` is required before running the suite (Task 2 Step 6).
- **Tests run from `skills/workflow-design-validate/scripts/`** so `validate_blueprint` is importable as a top-level module (mirrors how the eval framework runs from its package root).
```
