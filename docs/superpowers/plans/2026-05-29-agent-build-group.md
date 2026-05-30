# agent-build-* Group + Plugin Composition Implementation Plan

**Status:** Complete (2026-05-30)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `agent-build-*` skill group — deterministic renderers (TDD) that turn a validated workflow blueprint + authored prompts into Claude-Code-native artifacts (subagents, hooks, scripts, an entry-point command), a `agent-build-run` skill that drives them in-session one level deep, and unify the plugin's README/manifest/roadmap into a single design→author→build→measure→improve story.

**Architecture:** Two skills in the existing `je-dev-skills` plugin. `agent-build-scaffold` wraps a pure-Python renderer package (`scaffold.py` + small modules) that parses the single fenced `yaml` block of a `workflow-design-validate`-shaped blueprint and emits `.claude/agents/<id>.md` subagents (four-part contract: objective·output_format·tools·boundaries — output_format as a BODY section, tools→frontmatter), `.claude/hooks/*.sh` + `hooks.json` for rubric gates, plain Bash/Python scripts for deterministic steps, and a single entry-point command. The renderer is built TDD-first against good/bad blueprint fixtures (mirroring `workflow-design-validate/scripts/tests/`) and WARNS (never silently expands) when a blueprint uses a subagent where a deterministic script would do. `agent-build-run` is an authored markdown skill that dispatches the scaffolded steps in order, honoring gates/loops/termination, one level deep on session auth (no API key). Plugin composition edits are authored-markdown + JSON edits verified by structural greps.

**Tech Stack:** Python 3.10+ (stdlib only — `argparse`, `re`, `json`, `pathlib`, `dataclasses`; PyYAML for parsing the fenced block, matching `workflow-design-validate`), stdlib `unittest` offline fixtures, Markdown skills with YAML frontmatter, Claude Code subagent/hook/command file formats.

**Specs:**
- [docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md](../specs/2026-05-29-agent-build-and-execution-spec.md) — §3 (the `agent-build-*` group + rendering map), §4 (plugin composition), §5 (DoD), §6 (non-goals).
- [docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md](../specs/2026-05-29-prompt-engineering-skills-design.md) — the lifecycle this group sits inside.
- [docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md](../specs/WORKFLOW_DESIGN_SPEC.md) §4 (the blueprint schema this group consumes; §4 four-part contract = objective·output_format·tools·boundaries), §9 (roadmap entry relocated by Task 16).

**Shared interface contract (do NOT redefine here — owned by sibling plans):** `evals/aggregate.py`, `config.EXECUTION_MODE`, `run_eval.py` mode-awareness + loop-param constants, `check_placeholders`, and `skills/prompt-engineering-improve/scripts/improve_step.py` are built by the **substrate** and **prompt-engineering-improve** plans. This plan COMPOSES the resulting lifecycle (README/manifest/roadmap) but creates none of those files. The framework CORE (`evals/evaluator/*.py`, `evals/prompts/`) is untouched.

---

## File Structure

```
skills/agent-build-scaffold/
  SKILL.md                                   # Task 14 — the scaffold skill (TOC + procedure)
  references/
    rendering-map.md                         # Task 11 — blueprint element → CC construct (canonical mapping table)
    patterns.md                              # Task 12 — emitted-artifact patterns (subagent body layout, hook exit-code contract, idempotency wrapper, entry-point command shape)
    citations.md                             # Task 13 — dated volatile CC specifics (frontmatter fields, model aliases, hook event names, Task→Agent rename)
  scripts/
    requirements.txt                         # Task 2 — PyYAML>=6.0
    scaffold.py                              # Tasks 2–10 — the deterministic renderer CLI + all render functions
    tests/
      __init__.py                            # Task 2
      fixtures/
        refund-triage.blueprint.md           # Task 2 — agentic + deterministic + rubric gate + side_effecting step (stem == workflow name)
        csv-to-slack.blueprint.md            # Task 4 — no subagents (all deterministic steps) (stem == workflow name)
        overpowered.blueprint.md             # Task 9 — agentic step whose rationale/objective is mechanical → WARN (stem == workflow name)
        broken_no_yaml.blueprint.md          # Task 3 — zero fenced yaml blocks
        broken_partial_contract.blueprint.md # Task 6 — subagent missing boundaries
      test_extract.py                        # Task 3 — load_blueprint / extract_yaml_block / slugify
      test_render_subagent.py                # Task 6 — render_subagent (frontmatter + body sections)
      test_render_script.py                  # Task 5 — render_step_script (deterministic + side_effecting wrapper)
      test_render_hook.py                    # Task 7 — render_hook + render_hooks_json
      test_render_command.py                 # Task 8 — render_entry_command
      test_warnings.py                       # Task 9 — subagent-where-script-would-do warning
      test_cli.py                            # Task 10 — main(): writes files, exit codes, --dry-run
skills/agent-build-run/
  SKILL.md                                   # Task 15 — the run skill (drive scaffolded app in-session)
README.md                                    # Task 16 — unified lifecycle narrative + agent-build row + cost note
.claude-plugin/plugin.json                   # Task 17 — one-journey description + keywords (keep scoped 'orchestration')
docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md                 # Task 18 — §9 relocate scaffold roadmap entry → agent-build-*
```

The renderer splits one render concern per function (`render_subagent`, `render_step_script`, `render_hook`, `render_hooks_json`, `render_entry_command`, `warn_overpowered_steps`) so each is unit-testable in isolation — mirroring `workflow-design-validate/scripts/validate_blueprint.py`'s one-check-per-function structure. Fixtures are small and concern-focused.

---

## Conventions reused (read before starting)

- **Blueprint shape** is `workflow-design-validate`'s: one fenced ```` ```yaml ```` block; `steps[].{id,kind,rationale,pattern,side_effecting,reversible,termination,retry,rollback}`; `subagents[].{id,objective,output_format,tools,boundaries,model,effort}`; `rubrics[].{name,scale,levels,gate,judge}`; `dimensions`, `outcomes`, `budgets`, `guardrails`. See `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §4.1 and the existing fixture `skills/workflow-design-validate/scripts/tests/fixtures/valid_full.blueprint.md`.
- **Parsing idiom** (copied from `validate_blueprint.py:13,34-49`): `YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)`; `extract_yaml_block` raises `ValueError` unless exactly one block; `load_blueprint` raises `ValueError` if the block is not a mapping. Reuse this verbatim so scaffold and validate agree on what a blueprint is.
- **Test idiom** (copied from `workflow-design-validate/scripts/tests/test_subagents.py:1-7`): tests import the module directly (`from scaffold import ...`); `FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")`; run with `python3 -m unittest discover` from the `scripts/` dir so `scaffold` is importable as a top-level module.
- **Skill frontmatter idiom** (copied from `workflow-design-validate/SKILL.md:1-7`): `name`, third-person `description` (what + when, with quoted trigger phrases), `argument-hint`, `allowed-tools`, `version: 0.1.0`. Reference plugin files by `${CLAUDE_PLUGIN_ROOT}/...` path.
- **Volatility containment** (spec §3.4): every CC-version-volatile specific (subagent frontmatter field names, model aliases, effort levels, hook event names, Task→Agent tool name) is cited from `references/citations.md` with an *as of 2026-05-29* date and a `verify-against-runtime` step — never hardcoded in skill prose. Mirror `skills/workflow-design-interview/references/citations.md`.
- **Companion plugins, not vendoring** (`CONTRIBUTING.md`; spec §3.5): the rendered subagents reuse `plugin-dev/agent-development`'s authoring guidance and its `validate-agent.sh` / `plugin-validator` / `skill-reviewer` (a dev-time companion plugin) rather than restating agent-authoring rules here. This skill owns the blueprint→artifact *mapping* + deterministic renderers only — read `CONTRIBUTING.md` before starting Tasks 12–14.

---

## Task 1: Branch + plan-acknowledgement commit

**Files:** none (git only).

- [ ] **Step 1: Confirm the working branch.** The repo is already on `prompt-engineering-skills`. Verify and stay on it (this group ships alongside the prompt-engineering work):

```bash
cd /home/dawti/je-dev-skills && git branch --show-current
```

Expected output:
```
prompt-engineering-skills
```

If the output is `main`, create the branch first: `git checkout -b agent-build-group`.

- [ ] **Step 2: Create the scaffold scripts directory tree.**

```bash
mkdir -p /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts/tests/fixtures \
         /home/dawti/je-dev-skills/skills/agent-build-scaffold/references \
         /home/dawti/je-dev-skills/skills/agent-build-run
```

Expected output: none (success is silent).

- [ ] **Step 3: Commit the empty structure marker.** Create the test package init now so commits are coherent:

```bash
touch /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts/tests/__init__.py
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/tests/__init__.py
git commit -m "Scaffold agent-build-* directory tree

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Expected output: a commit confirmation naming `1 file changed`.

---

## Task 2: Renderer skeleton + blueprint parsing (TDD)

Build the `scaffold.py` skeleton: the shared parsing helpers (`extract_yaml_block`, `load_blueprint`, `slugify`) plus the `requirements.txt` and the first valid fixture. Tests first.

**Files:**
- Create: `skills/agent-build-scaffold/scripts/requirements.txt`
- Create: `skills/agent-build-scaffold/scripts/tests/fixtures/refund-triage.blueprint.md`
- Create: `skills/agent-build-scaffold/scripts/tests/test_extract.py`
- Create: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Create the requirements file.**

`skills/agent-build-scaffold/scripts/requirements.txt`:
```
PyYAML>=6.0
```

- [ ] **Step 2: Create the valid_full fixture** (one agentic step backed by a subagent, one deterministic step, one side_effecting step, one rubric gate). This is the workhorse fixture every render test reads.

`skills/agent-build-scaffold/scripts/tests/fixtures/refund-triage.blueprint.md` (the filename stem `refund-triage` is what `_workflow_name` derives the workflow name from — the frontmatter `name` below lives OUTSIDE the fenced ```yaml block and is NOT parsed by `load_blueprint`, so the stem is the source of truth for the command/workflow name):
```markdown
---
name: refund-triage
version: 0.1.0
status: validated
created: 2026-05-29
---
# Refund triage workflow

```yaml
preconditions: ["an inbound refund request with order id"]
inputs:
  - {key: order_id, description: "the order to refund", format: "string"}
  - {key: reason, description: "customer-stated reason", format: "string"}
dependencies: ["orders API"]
outputs: ["a refund decision + audit record"]
postconditions: ["every approved refund has an idempotency key"]
steps:
  - id: classify-reason
    kind: agentic
    rationale: "free-text reason needs open-ended judgment to categorize"
    pattern: route
    side_effecting: false
    reversible: false
    termination: "a single category is chosen"
  - id: fetch-order
    kind: deterministic
    rationale: "a plain API read; no judgment"
    pattern: none
    side_effecting: false
    reversible: false
  - id: issue-refund
    kind: deterministic
    rationale: "a deterministic API write guarded by an idempotency key"
    pattern: none
    side_effecting: true
    reversible: true
    retry: {policy: "exponential", idempotency_key: "order_id"}
    rollback: "void the refund via the orders API"
subagents:
  - id: reason-classifier
    objective: "classify the customer's refund reason into one category"
    output_format: "JSON {category: string, confidence: number}"
    tools: [Read]
    boundaries: "classify only; never issue a refund or fetch external data"
    model: haiku
    effort: low
rubrics:
  - name: classification-accuracy
    scale: 1-5
    levels: {1: "wrong category", 3: "plausible", 5: "exactly right"}
    gate: 4
    reference_based: true
    judge: llm
dimensions:
  observability: specified
  cost_latency_budgets: specified
  guardrails_permissions: specified
  context_management: specified
  human_in_the_loop: specified
  state_artifact_passing: specified
  failure_handling: specified
  retry_idempotency: specified
  rollback_compensation: specified
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: specified
outcomes:
  - {given: "a refund request", when: "the workflow runs", then: "a categorized, audited decision"}
budgets: {max_turns: 10, max_tool_calls: 20, latency_note: "<1m", cost_note: "~3x a chat"}
guardrails: ["classifier is read-only", "refund write is idempotent"]
```
```

(Note: the inner ```` ```yaml ```` fence is the block the renderer parses; the outer fence is just this plan's code block.)

- [ ] **Step 3: Write the failing parsing tests.**

`skills/agent-build-scaffold/scripts/tests/test_extract.py`:
```python
import os
import unittest

from scaffold import extract_yaml_block, load_blueprint, slugify

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtract(unittest.TestCase):
    def test_loads_full_blueprint_as_mapping(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.assertIsInstance(bp, dict)
        self.assertEqual(len(bp["steps"]), 3)
        self.assertEqual(bp["subagents"][0]["id"], "reason-classifier")

    def test_extract_requires_exactly_one_block(self):
        with self.assertRaises(ValueError):
            extract_yaml_block("no fenced block here")

    def test_slugify_normalizes(self):
        self.assertEqual(slugify("Reason Classifier!"), "reason-classifier")
        self.assertEqual(slugify("fetch_order"), "fetch-order")
        self.assertEqual(slugify("  A  B  "), "a-b")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests — expect FAIL** (no `scaffold` module yet):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest discover -s tests -t . 2>&1 | tail -5
```

Expected output (the import fails):
```
ModuleNotFoundError: No module named 'scaffold'
```

- [ ] **Step 5: Create `scaffold.py` with the parsing helpers.** This first version defines only the parsing layer.

`skills/agent-build-scaffold/scripts/scaffold.py`:
```python
"""Deterministic renderer: a validated workflow blueprint -> Claude-Code-native artifacts.

Parses the single fenced ```yaml block from a <name>.blueprint.md file (the same
artifact workflow-design-validate gates on, docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md §4) and
renders:
  - agentic steps      -> .claude/agents/<id>.md subagents (four-part contract:
                          objective, output_format, tools, boundaries; tools ->
                          frontmatter, output_format/objective/boundaries -> body)
  - deterministic steps -> .claude/scripts/<id>.sh placeholder scripts (idempotency
                          wrapper when side_effecting)
  - rubric gates        -> .claude/hooks/<name>.sh + .claude/hooks.json (exit-code gate)
  - the whole workflow  -> .claude/commands/<workflow>.md entry-point command

Volatile Claude-Code specifics (frontmatter field names, model aliases, effort
levels, hook event names, the Task->Agent tool name) are documented in
references/citations.md and re-verified against the live runtime before relying on
them — they are NOT hardcoded as load-bearing constants here.
"""
import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

YAML_FENCE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)

# Steps that are deterministic by classification need a script, not a subagent.
DETERMINISTIC = "deterministic"
AGENTIC = "agentic"


def extract_yaml_block(text: str) -> str:
    """Return the single fenced ```yaml block; raise if there isn't exactly one."""
    blocks = YAML_FENCE.findall(text)
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```yaml block, found {len(blocks)}")
    return blocks[0]


def load_blueprint(path: str) -> dict:
    """Load and parse the fenced yaml block of a blueprint file into a mapping."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parsed = yaml.safe_load(extract_yaml_block(text))
    if not isinstance(parsed, dict):
        raise ValueError(
            "the ```yaml block must parse to a mapping of blueprint fields, "
            f"got {type(parsed).__name__}")
    return parsed


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, replace non-alphanumeric runs with single hyphens, trim hyphens."""
    return _SLUG_STRIP.sub("-", str(value).lower()).strip("-")
```

- [ ] **Step 6: Run the tests — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest discover -s tests -t . 2>&1 | tail -4
```

Expected output:
```
Ran 3 tests in 0.0XXs

OK
```

- [ ] **Step 7: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: blueprint parsing + slugify (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Expected output: commit confirmation.

---

## Task 3: Bad-input fixtures + error handling (TDD)

Add the two malformed fixtures and assert the parser raises the right `ValueError`.

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/fixtures/broken_no_yaml.blueprint.md`
- Modify: `skills/agent-build-scaffold/scripts/tests/test_extract.py`

- [ ] **Step 1: Create the no-yaml fixture** (zero fenced yaml blocks):

`skills/agent-build-scaffold/scripts/tests/fixtures/broken_no_yaml.blueprint.md`:
```markdown
---
name: empty
version: 0.1.0
---
# A blueprint with prose but no fenced yaml block

There is no structured core here.
```

- [ ] **Step 2: Add a failing test** for the no-yaml fixture. Append this method to `TestExtract` in `test_extract.py` (immediately after `test_slugify_normalizes`, before the closing `if __name__`):

```python
    def test_no_yaml_block_raises(self):
        path = os.path.join(FIXTURES, "broken_no_yaml.blueprint.md")
        with self.assertRaises(ValueError):
            load_blueprint(path)
```

- [ ] **Step 3: Run the tests — expect PASS** (the existing `extract_yaml_block` already raises on zero blocks):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest discover -s tests -t . 2>&1 | tail -4
```

Expected output:
```
Ran 4 tests in 0.0XXs

OK
```

- [ ] **Step 4: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/tests/
git commit -m "agent-build-scaffold: assert parser rejects blueprints with no yaml block

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Render deterministic step scripts (TDD)

A `deterministic` step renders to a placeholder shell script the orchestrator calls. The script is a stub (the human fills in the real command) but its scaffolding is deterministic: shebang, `set -euo pipefail`, a header echoing the step id + rationale, and — when `side_effecting: true` — an idempotency-key guard around the body (spec §3.2 "side_effecting → idempotency-key / rollback handling").

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/fixtures/csv-to-slack.blueprint.md`
- Create: `skills/agent-build-scaffold/scripts/tests/test_render_script.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Create the deterministic-only fixture** (no subagents — exercises the "all scripts" path and the no-agentic-step branch):

`skills/agent-build-scaffold/scripts/tests/fixtures/csv-to-slack.blueprint.md` (filename stem `csv-to-slack` is the workflow name `_workflow_name` derives; the frontmatter `name` is outside the parsed ```yaml block):
```markdown
---
name: csv-to-slack
version: 0.1.0
status: validated
created: 2026-05-29
---
# Scheduled CSV-to-Slack summary

```yaml
preconditions: ["a sales CSV at a known path"]
inputs:
  - {key: csv_path, description: "path to today's sales CSV", format: "string"}
dependencies: ["Slack API"]
outputs: ["a Slack summary message"]
postconditions: ["the summary posted exactly once"]
steps:
  - id: parse-csv
    kind: deterministic
    rationale: "structured parsing; no judgment"
    pattern: none
    side_effecting: false
    reversible: false
  - id: post-slack
    kind: deterministic
    rationale: "a deterministic API write, guarded for exactly-once"
    pattern: none
    side_effecting: true
    reversible: false
    retry: {policy: "fixed", idempotency_key: "csv_path"}
subagents: []
dimensions:
  observability: specified
  cost_latency_budgets: specified
  guardrails_permissions: specified
  context_management: {n/a: "no model in the loop"}
  human_in_the_loop: {n/a: "fully automated"}
  state_artifact_passing: specified
  failure_handling: specified
  retry_idempotency: specified
  rollback_compensation: {n/a: "post is not reversible; guarded exactly-once instead"}
  termination_conditions: specified
  tool_selection: specified
  evaluation_success: {n/a: "nothing generative to grade"}
rubrics: []
outcomes:
  - {given: "a CSV", when: "the job runs", then: "one Slack summary"}
budgets: {max_turns: 1, max_tool_calls: 4, latency_note: "<10s", cost_note: "~1x a chat"}
guardrails: ["post is idempotent on csv_path"]
```
```

- [ ] **Step 2: Write the failing render-script tests.**

`skills/agent-build-scaffold/scripts/tests/test_render_script.py`:
```python
import os
import unittest

from scaffold import load_blueprint, render_step_script

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderScript(unittest.TestCase):
    def setUp(self):
        self.bp = load_blueprint(os.path.join(FIXTURES, "csv-to-slack.blueprint.md"))
        self.steps = {s["id"]: s for s in self.bp["steps"]}

    def test_plain_script_has_shebang_and_strict_mode(self):
        out = render_step_script(self.steps["parse-csv"])
        self.assertTrue(out.startswith("#!/usr/bin/env bash\n"))
        self.assertIn("set -euo pipefail", out)
        self.assertIn("# step: parse-csv", out)
        self.assertIn("structured parsing; no judgment", out)

    def test_non_side_effecting_has_no_idempotency_guard(self):
        out = render_step_script(self.steps["parse-csv"])
        self.assertNotIn("IDEMPOTENCY_KEY", out)

    def test_side_effecting_emits_idempotency_guard(self):
        out = render_step_script(self.steps["post-slack"])
        self.assertIn("IDEMPOTENCY_KEY", out)
        # the declared key name from retry.idempotency_key is surfaced as a marker
        self.assertIn("csv_path", out)
        self.assertIn("already done", out.lower())

    def test_filename_uses_step_id_slug(self):
        from scaffold import step_script_filename
        self.assertEqual(step_script_filename(self.steps["post-slack"]), "post-slack.sh")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run — expect FAIL** (no `render_step_script`):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_script 2>&1 | tail -5
```

Expected output ends with:
```
ImportError: cannot import name 'render_step_script' from 'scaffold'
```

- [ ] **Step 4: Implement `render_step_script` + `step_script_filename`.** Append to `scaffold.py` (after `slugify`):

```python
def step_script_filename(step: dict) -> str:
    """The .sh filename for a deterministic step, slugged from its id."""
    return f"{slugify(step['id'])}.sh"


def render_step_script(step: dict) -> str:
    """Render a deterministic step into a placeholder Bash script.

    side_effecting steps get an idempotency-key guard skeleton (spec §3.2): the
    body runs only once per resolved key, so a retried orchestration is exactly-once.
    """
    sid = step["id"]
    rationale = step.get("rationale", "")
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# step: {sid}",
        f"# rationale: {rationale}",
        "# AUTO-GENERATED placeholder by agent-build-scaffold. Fill in the real command below.",
        "",
    ]
    if step.get("side_effecting"):
        key = (step.get("retry") or {}).get("idempotency_key", "STEP_ID")
        lines += [
            f'# This step is side_effecting; guard it on the declared idempotency key: {key}',
            f'IDEMPOTENCY_KEY="${{{key.upper()}:-{sid}}}"',
            'MARKER=".agent-build-state/${IDEMPOTENCY_KEY}.done"',
            'mkdir -p .agent-build-state',
            'if [ -f "$MARKER" ]; then',
            '  echo "step already done for $IDEMPOTENCY_KEY; skipping (idempotent)"',
            '  exit 0',
            'fi',
            "",
            "# --- side-effecting work goes here ---",
            "echo 'TODO: implement the side-effecting command'",
            "",
            'touch "$MARKER"',
        ]
        if step.get("reversible"):
            rollback = step.get("rollback", "")
            lines += [
                "",
                f"# rollback (reversible step): {rollback}",
                "# On failure downstream, the orchestrator invokes the compensating action above.",
            ]
    else:
        lines += [
            "# --- deterministic work goes here ---",
            "echo 'TODO: implement this deterministic step'",
        ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Run — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_script 2>&1 | tail -4
```

Expected output:
```
Ran 4 tests in 0.0XXs

OK
```

- [ ] **Step 6: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: render deterministic step scripts + idempotency guard (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Render the subagent four-part contract (TDD)

The headline rendering rule (spec §3.2): an `agentic` step's subagent becomes a `.claude/agents/<id>.md` file. **`tools` → frontmatter `tools`; `model` (non-contract) → frontmatter `model`.** **`objective`, `output_format`, and `boundaries` → BODY sections — `output_format` is NEVER a frontmatter key** (subagent frontmatter has no `output_format`). `effort` is non-contract and goes in the body as a note (it is not a confirmed frontmatter key — see citations).

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/test_render_subagent.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Write the failing subagent-render tests.**

`skills/agent-build-scaffold/scripts/tests/test_render_subagent.py`:
```python
import os
import unittest

from scaffold import load_blueprint, render_subagent, subagent_filename

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderSubagent(unittest.TestCase):
    def setUp(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.sa = bp["subagents"][0]  # reason-classifier
        self.out = render_subagent(self.sa)

    def test_has_frontmatter_with_name_tools_model(self):
        # frontmatter is the first --- ... --- block
        self.assertTrue(self.out.startswith("---\n"))
        head = self.out.split("---\n")[1]
        self.assertIn("name: reason-classifier", head)
        self.assertIn("tools: Read", head)          # tools -> frontmatter
        self.assertIn("model: haiku", head)          # model (non-contract) -> frontmatter

    def test_output_format_is_a_body_section_not_frontmatter(self):
        head = self.out.split("---\n")[1]
        self.assertNotIn("output_format", head)      # NEVER a frontmatter key
        body = self.out.split("---\n", 2)[2]
        self.assertIn("## Output format", body)
        self.assertIn("JSON {category: string, confidence: number}", body)

    def test_objective_and_boundaries_are_body_sections(self):
        body = self.out.split("---\n", 2)[2]
        self.assertIn("## Objective", body)
        self.assertIn("classify the customer's refund reason", body)
        self.assertIn("## Boundaries", body)
        self.assertIn("never issue a refund", body)

    def test_effort_is_a_body_note_not_frontmatter(self):
        head = self.out.split("---\n")[1]
        self.assertNotIn("effort:", head)
        body = self.out.split("---\n", 2)[2]
        self.assertIn("effort", body.lower())

    def test_tools_list_renders_comma_separated(self):
        sa = {"id": "multi", "objective": "o", "output_format": "f",
              "tools": ["Read", "Grep", "Glob"], "boundaries": "b",
              "model": "sonnet", "effort": "medium"}
        head = render_subagent(sa).split("---\n")[1]
        self.assertIn("tools: Read, Grep, Glob", head)

    def test_filename_uses_id_slug(self):
        self.assertEqual(subagent_filename(self.sa), "reason-classifier.md")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_subagent 2>&1 | tail -5
```

Expected: `ImportError: cannot import name 'render_subagent' from 'scaffold'`.

- [ ] **Step 3: Implement `render_subagent` + `subagent_filename`.** Append to `scaffold.py`:

```python
def subagent_filename(subagent: dict) -> str:
    """The .claude/agents/ filename for a subagent, slugged from its id."""
    return f"{slugify(subagent['id'])}.md"


def render_subagent(subagent: dict) -> str:
    """Render a subagent's four-part contract into a .claude/agents/<id>.md file.

    Contract rendering (spec §3.2, the canonical rule):
      - tools             -> frontmatter `tools` (comma-separated allowlist)
      - model             -> frontmatter `model` (NON-contract field)
      - objective         -> body section
      - output_format     -> body section (NEVER a frontmatter key; subagent
                             frontmatter has no output_format)
      - boundaries        -> body section
      - effort            -> body note (NON-contract; not a confirmed frontmatter
                             field — see references/citations.md)
    """
    name = slugify(subagent["id"])
    tools = subagent.get("tools") or []
    tools_csv = ", ".join(str(t) for t in tools)
    model = subagent.get("model", "inherit")
    effort = subagent.get("effort", "")

    frontmatter = [
        "---",
        f"name: {name}",
        f"description: {subagent['objective']}",
        f"tools: {tools_csv}",
        f"model: {model}",
        "---",
    ]
    body = [
        f"# {name}",
        "",
        "## Objective",
        subagent["objective"],
        "",
        "## Output format",
        subagent["output_format"],
        "",
        "## Boundaries",
        subagent["boundaries"],
        "",
        "## Notes",
        f"- Recommended effort: {effort} (non-contract; tune per the live runtime — see citations).",
        "- Emit ONLY the output described above; deterministic glue parses + validates it.",
    ]
    return "\n".join(frontmatter) + "\n\n" + "\n".join(body) + "\n"
```

- [ ] **Step 4: Run — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_subagent 2>&1 | tail -4
```

Expected output:
```
Ran 6 tests in 0.0XXs

OK
```

- [ ] **Step 5: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: render subagent four-part contract (output_format as body) (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Reject partial subagent contracts (TDD)

Mirroring `workflow-design-validate`'s contract enforcement, the renderer must refuse to emit a subagent whose four-part contract is incomplete (a missing field would produce a broken `.md`). It raises `ScaffoldError` with the offending field.

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/fixtures/broken_partial_contract.blueprint.md`
- Modify: `skills/agent-build-scaffold/scripts/tests/test_render_subagent.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Create the partial-contract fixture** (subagent missing `boundaries`):

`skills/agent-build-scaffold/scripts/tests/fixtures/broken_partial_contract.blueprint.md`:
```markdown
---
name: broken
version: 0.1.0
---
# Subagent missing boundaries

```yaml
steps:
  - id: classify
    kind: agentic
    rationale: "needs judgment"
    pattern: route
    termination: "one category chosen"
subagents:
  - id: classifier
    objective: "classify"
    output_format: "JSON {category}"
    tools: [Read]
    model: haiku
    effort: low
dimensions: {}
rubrics: []
outcomes: []
```
```

- [ ] **Step 2: Add failing tests.** Append to `test_render_subagent.py`, inside `TestRenderSubagent` (before `if __name__`):

```python
    def test_missing_boundaries_raises_scaffold_error(self):
        from scaffold import ScaffoldError, load_blueprint
        bp = load_blueprint(os.path.join(FIXTURES, "broken_partial_contract.blueprint.md"))
        with self.assertRaises(ScaffoldError) as ctx:
            render_subagent(bp["subagents"][0])
        self.assertIn("boundaries", str(ctx.exception))

    def test_empty_tools_raises_scaffold_error(self):
        from scaffold import ScaffoldError
        sa = {"id": "x", "objective": "o", "output_format": "f", "tools": [],
              "boundaries": "b", "model": "haiku", "effort": "low"}
        with self.assertRaises(ScaffoldError) as ctx:
            render_subagent(sa)
        self.assertIn("tools", str(ctx.exception))
```

- [ ] **Step 3: Run — expect FAIL** (`render_subagent` currently `KeyError`s or emits a broken file rather than raising `ScaffoldError`):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_subagent 2>&1 | tail -6
```

- [ ] **Step 4: Add `ScaffoldError` + a guard.** In `scaffold.py`, add the exception class near the top (right after the `AGENTIC = "agentic"` line):

```python


class ScaffoldError(ValueError):
    """Raised when a blueprint element cannot be rendered (incomplete contract)."""
```

Then add a validation guard at the **start** of `render_subagent` (immediately after the docstring, before `name = slugify(...)`):

```python
    _CONTRACT = ["objective", "output_format", "boundaries"]
    for f in _CONTRACT:
        if not (subagent.get(f) and str(subagent[f]).strip()):
            raise ScaffoldError(
                f"subagent {subagent.get('id', '?')!r} missing contract field {f!r}")
    if not (isinstance(subagent.get("tools"), list) and len(subagent["tools"]) > 0):
        raise ScaffoldError(
            f"subagent {subagent.get('id', '?')!r} needs a non-empty tools allowlist")
```

- [ ] **Step 5: Run — expect PASS** (all 8 tests now):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_subagent 2>&1 | tail -4
```

Expected output:
```
Ran 8 tests in 0.0XXs

OK
```

- [ ] **Step 6: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: reject incomplete subagent contracts (ScaffoldError) (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Render rubric gates as hooks (TDD)

Spec §3.2: a `rubric` gate becomes a hook (`Stop`/`SubagentStop`) enforced by an exit-code script. The renderer emits one `.claude/hooks/<name>-gate.sh` per rubric plus a single `.claude/hooks.json` wiring them. The script is a deterministic exit-code gate skeleton: it reads a score file and exits non-zero when the score is below the rubric `gate`. Hook **event names are volatile** (cited, not hardcoded as a guarantee) — default to `SubagentStop`, documented in `references/citations.md`.

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/test_render_hook.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Write the failing hook tests.**

`skills/agent-build-scaffold/scripts/tests/test_render_hook.py`:
```python
import json
import os
import unittest

from scaffold import load_blueprint, render_hook, render_hooks_json, hook_filename

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderHook(unittest.TestCase):
    def setUp(self):
        self.bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.rubric = self.bp["rubrics"][0]  # classification-accuracy, gate 4

    def test_hook_script_is_exit_code_gate(self):
        out = render_hook(self.rubric)
        self.assertTrue(out.startswith("#!/usr/bin/env bash\n"))
        self.assertIn("set -euo pipefail", out)
        self.assertIn("# rubric gate: classification-accuracy", out)
        self.assertIn("GATE=4", out)
        self.assertIn("exit 1", out)   # blocks when below gate
        self.assertIn("exit 0", out)   # passes at/above gate

    def test_hook_filename_slugged(self):
        self.assertEqual(hook_filename(self.rubric), "classification-accuracy-gate.sh")

    def test_hooks_json_wires_each_rubric(self):
        doc = render_hooks_json(self.bp["rubrics"], workflow_name="refund-triage")
        parsed = json.loads(doc)
        self.assertIn("hooks", parsed)
        # one SubagentStop entry referencing the gate script via ${CLAUDE_PROJECT_DIR}
        entries = parsed["hooks"]["SubagentStop"]
        self.assertEqual(len(entries), 1)
        cmd = entries[0]["hooks"][0]["command"]
        self.assertIn("classification-accuracy-gate.sh", cmd)
        self.assertIn("${CLAUDE_PROJECT_DIR}", cmd)

    def test_no_rubrics_yields_empty_hooks(self):
        doc = render_hooks_json([], workflow_name="x")
        self.assertEqual(json.loads(doc), {"hooks": {}})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_hook 2>&1 | tail -5
```

Expected: `ImportError: cannot import name 'render_hook' from 'scaffold'`.

- [ ] **Step 3: Implement the hook renderers.** Append to `scaffold.py`:

```python
# Hook event names are version-volatile (see references/citations.md). SubagentStop
# is the default gate point for grading a delegated subagent's output; re-verify the
# current event name against the live runtime before relying on it.
DEFAULT_HOOK_EVENT = "SubagentStop"


def hook_filename(rubric: dict) -> str:
    """The .claude/hooks/ filename for a rubric gate."""
    return f"{slugify(rubric['name'])}-gate.sh"


def render_hook(rubric: dict) -> str:
    """Render a rubric gate into an exit-code Bash hook.

    The skeleton reads a score from .agent-build-state/<rubric>.score and exits
    non-zero (blocking) when it is below the rubric's `gate`. The human wires the
    real score source; the exit-code contract is fixed and deterministic.
    """
    name = slugify(rubric["name"])
    gate = rubric.get("gate")
    if gate is None:
        raise ScaffoldError(f"rubric {rubric.get('name', '?')!r} has no gate threshold")
    return "\n".join([
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# rubric gate: {rubric['name']}",
        f"# AUTO-GENERATED by agent-build-scaffold. Exit 0 = pass, exit 1 = block.",
        f"GATE={gate}",
        f'SCORE_FILE=".agent-build-state/{name}.score"',
        'if [ ! -f "$SCORE_FILE" ]; then',
        '  echo "no score recorded for gate; blocking" >&2',
        "  exit 1",
        "fi",
        'SCORE="$(cat "$SCORE_FILE")"',
        'if [ "$SCORE" -lt "$GATE" ]; then',
        f'  echo "score $SCORE below gate {gate}; blocking" >&2',
        "  exit 1",
        "fi",
        'echo "score $SCORE meets gate; passing"',
        "exit 0",
    ]) + "\n"


def render_hooks_json(rubrics: list, *, workflow_name: str) -> str:
    """Wire each rubric gate into a .claude/hooks.json document.

    Each gate is a DEFAULT_HOOK_EVENT entry whose command invokes the gate script
    by ${CLAUDE_PROJECT_DIR}-relative path. No rubrics -> {"hooks": {}}.
    """
    import json as _json
    if not rubrics:
        return _json.dumps({"hooks": {}}, indent=2) + "\n"
    entries = []
    for r in rubrics:
        script = hook_filename(r)
        entries.append({
            "hooks": [{
                "type": "command",
                "command": f"${{CLAUDE_PROJECT_DIR}}/.claude/hooks/{script}",
            }]
        })
    return _json.dumps({"hooks": {DEFAULT_HOOK_EVENT: entries}}, indent=2) + "\n"
```

- [ ] **Step 4: Run — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_hook 2>&1 | tail -4
```

Expected output:
```
Ran 4 tests in 0.0XXs

OK
```

- [ ] **Step 5: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: render rubric gates as exit-code hooks + hooks.json (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Render the orchestration entry-point command (TDD)

Spec §3.2: the whole workflow renders to a slash command / skill that dispatches the steps **one level deep** (interactive, session auth, no key). The renderer emits `.claude/commands/<workflow>.md`: frontmatter (`description`, `argument-hint` derived from `inputs`) + a body that lists the ordered steps, marking each `deterministic` step "run script `<id>.sh`" and each `agentic` step "dispatch subagent `<subagent-id>`", and explicitly states the one-level-deep + termination rules.

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/test_render_command.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Write the failing command tests.**

`skills/agent-build-scaffold/scripts/tests/test_render_command.py`:
```python
import os
import unittest

from scaffold import load_blueprint, render_entry_command

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestRenderCommand(unittest.TestCase):
    def setUp(self):
        self.bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.out = render_entry_command(self.bp, workflow_name="refund-triage")

    def test_has_frontmatter_description_and_arg_hint(self):
        self.assertTrue(self.out.startswith("---\n"))
        head = self.out.split("---\n")[1]
        self.assertIn("description:", head)
        self.assertIn("argument-hint:", head)
        self.assertIn("order_id", head)   # derived from inputs
        self.assertIn("reason", head)

    def test_body_lists_steps_in_order_with_construct(self):
        body = self.out.split("---\n", 2)[2]
        # ordered: classify-reason (agentic), fetch-order (det), issue-refund (det)
        i_classify = body.index("classify-reason")
        i_fetch = body.index("fetch-order")
        i_issue = body.index("issue-refund")
        self.assertLess(i_classify, i_fetch)
        self.assertLess(i_fetch, i_issue)
        # agentic step dispatches the subagent; deterministic steps run scripts
        self.assertIn("dispatch subagent `reason-classifier`", body)
        self.assertIn("run script `fetch-order.sh`", body)
        self.assertIn("run script `issue-refund.sh`", body)

    def test_body_states_one_level_and_termination(self):
        body = self.out.split("---\n", 2)[2]
        self.assertIn("one level", body.lower())
        self.assertIn("a single category is chosen", body)  # the agentic step's termination

    def test_no_inputs_yields_generic_arg_hint(self):
        bp = {"steps": [], "inputs": []}
        out = render_entry_command(bp, workflow_name="empty")
        self.assertIn("argument-hint:", out.split("---\n")[1])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_command 2>&1 | tail -5
```

Expected: `ImportError: cannot import name 'render_entry_command' from 'scaffold'`.

- [ ] **Step 3: Implement `render_entry_command`.** It needs a step→subagent association: in the blueprint schema a subagent backs an agentic step but there is no explicit foreign key, so the renderer pairs the i-th `agentic` step with the i-th `subagents` entry (the same positional convention `workflow-design-validate` assumes — `subagents` are justified by agentic steps). Append to `scaffold.py`:

```python
def _agentic_subagent_map(bp: dict) -> dict:
    """Pair each agentic step id with a subagent id, positionally.

    The blueprint schema (WORKFLOW_DESIGN_SPEC §4.1) lists subagents alongside the
    agentic steps that justify them but carries no explicit step->subagent key, so
    the i-th agentic step maps to the i-th declared subagent. Extra agentic steps
    (no matching subagent) map to None and the command notes an inline dispatch.
    """
    agentic_ids = [s["id"] for s in (bp.get("steps") or []) if s.get("kind") == AGENTIC]
    sub_ids = [sa["id"] for sa in (bp.get("subagents") or [])]
    mapping = {}
    for i, sid in enumerate(agentic_ids):
        mapping[sid] = sub_ids[i] if i < len(sub_ids) else None
    return mapping


def render_entry_command(bp: dict, *, workflow_name: str) -> str:
    """Render the one-level-deep orchestration entry-point slash command."""
    name = slugify(workflow_name)
    inputs = [i.get("key") for i in (bp.get("inputs") or []) if i.get("key")]
    arg_hint = " ".join(f"<{k}>" for k in inputs) if inputs else "[workflow inputs]"
    sub_map = _agentic_subagent_map(bp)

    frontmatter = [
        "---",
        f"description: Run the {name} workflow end to end, dispatching steps one level deep.",
        f'argument-hint: "{arg_hint}"',
        "---",
    ]
    body = [
        f"# Run the {name} workflow",
        "",
        "Drive the scaffolded steps **in order, one level deep** (this command is the",
        "top-level orchestrator; subagents are leaves and never dispatch their own",
        "subagents). Honor each step's gate, loop, and termination condition.",
        "",
        "## Steps",
    ]
    for i, step in enumerate(bp.get("steps") or [], start=1):
        sid = step["id"]
        if step.get("kind") == AGENTIC:
            sub = sub_map.get(sid)
            target = (f"dispatch subagent `{sub}`" if sub
                      else "dispatch an inline subagent for this step")
            term = step.get("termination", "")
            line = f"{i}. **{sid}** (agentic) — {target}."
            if term:
                line += f" Terminate when: {term}."
        else:
            line = f"{i}. **{sid}** (deterministic) — run script `{step_script_filename(step)}`."
        body.append(line)
    body += [
        "",
        "## Gates",
        "After any graded step, the rubric-gate hook blocks on a sub-threshold score.",
        "Do not proceed past a blocked gate; report it and stop.",
    ]
    return "\n".join(frontmatter) + "\n\n" + "\n".join(body) + "\n"
```

- [ ] **Step 4: Run — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_render_command 2>&1 | tail -4
```

Expected output:
```
Ran 4 tests in 0.0XXs

OK
```

- [ ] **Step 5: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: render one-level orchestration entry command (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: WARN when a subagent is used where a script would do (TDD)

Spec §3.3: scaffold must **warn (not silently expand)** when a blueprint uses a subagent where a deterministic script would do. The signal is an `agentic` step whose `rationale` or backing subagent `objective` reads as mechanical (extraction/formatting/lookup/parse/transform — no genuine open-ended judgment). `warn_overpowered_steps(bp) -> list[str]` returns one human-readable warning per suspect step. It is heuristic and conservative (warns, never blocks).

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/fixtures/overpowered.blueprint.md`
- Create: `skills/agent-build-scaffold/scripts/tests/test_warnings.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Create the over-powered fixture** (an agentic step whose work is mechanical extraction):

`skills/agent-build-scaffold/scripts/tests/fixtures/overpowered.blueprint.md` (filename stem `overpowered` is the workflow name `_workflow_name` derives — hence the entry command is `.claude/commands/overpowered.md`; the frontmatter `name` is outside the parsed ```yaml block):
```markdown
---
name: overpowered
version: 0.1.0
status: validated
created: 2026-05-29
---
# A subagent doing a script's job

```yaml
preconditions: ["a JSON record"]
inputs:
  - {key: record, description: "a JSON record", format: "string"}
outputs: ["the extracted id"]
postconditions: ["id extracted"]
steps:
  - id: extract-id
    kind: agentic
    rationale: "extract the id field from the record and format it"
    pattern: none
    side_effecting: false
    reversible: false
    termination: "id returned"
  - id: classify-intent
    kind: agentic
    rationale: "open-ended judgment about ambiguous user intent"
    pattern: route
    side_effecting: false
    reversible: false
    termination: "one intent chosen"
subagents:
  - id: id-extractor
    objective: "parse the record and extract the id field"
    output_format: "JSON {id: string}"
    tools: [Read]
    boundaries: "extract only"
    model: haiku
    effort: low
  - id: intent-judge
    objective: "decide the user's intent from ambiguous phrasing"
    output_format: "JSON {intent: string}"
    tools: [Read]
    boundaries: "classify only"
    model: sonnet
    effort: medium
dimensions: {}
rubrics: []
outcomes: []
budgets: {}
guardrails: []
```
```

- [ ] **Step 2: Write the failing warning tests.**

`skills/agent-build-scaffold/scripts/tests/test_warnings.py`:
```python
import os
import unittest

from scaffold import load_blueprint, warn_overpowered_steps

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestWarnings(unittest.TestCase):
    def test_flags_mechanical_agentic_step(self):
        bp = load_blueprint(os.path.join(FIXTURES, "overpowered.blueprint.md"))
        warnings = warn_overpowered_steps(bp)
        joined = "\n".join(warnings)
        self.assertIn("extract-id", joined)
        # the genuinely open-ended step is NOT flagged
        self.assertNotIn("classify-intent", joined)

    def test_clean_blueprint_has_no_warnings(self):
        bp = load_blueprint(os.path.join(FIXTURES, "refund-triage.blueprint.md"))
        self.assertEqual(warn_overpowered_steps(bp), [])

    def test_deterministic_only_has_no_warnings(self):
        bp = load_blueprint(os.path.join(FIXTURES, "csv-to-slack.blueprint.md"))
        self.assertEqual(warn_overpowered_steps(bp), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run — expect FAIL:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_warnings 2>&1 | tail -5
```

Expected: `ImportError: cannot import name 'warn_overpowered_steps' from 'scaffold'`.

- [ ] **Step 4: Implement `warn_overpowered_steps`.** Append to `scaffold.py`:

```python
# Mechanical-work signals: an agentic step whose rationale/objective is dominated by
# these verbs is doing a script's job (spec §3.3). Conservative — a "judgment"/
# "ambiguous"/"open-ended" signal in the same text suppresses the warning.
_MECHANICAL = ("extract", "format", "parse", "lookup", "look up", "transform",
               "concatenate", "rename", "copy", "sort", "filter", "count")
_JUDGMENT = ("judgment", "judge", "ambiguous", "open-ended", "open ended",
             "decide", "reason", "interpret", "nuance", "subjective")


def warn_overpowered_steps(bp: dict) -> list:
    """Return warnings for agentic steps that look like deterministic scripts.

    Heuristic + conservative: flags an agentic step when its rationale (and, if
    present, its positionally-paired subagent's objective) reads as mechanical work
    AND carries no genuine-judgment signal. Warns; never blocks (spec §3.3).
    """
    sub_map = _agentic_subagent_map(bp)
    sub_by_id = {sa["id"]: sa for sa in (bp.get("subagents") or [])}
    warnings = []
    for step in (bp.get("steps") or []):
        if step.get("kind") != AGENTIC:
            continue
        text = str(step.get("rationale", "")).lower()
        sub_id = sub_map.get(step["id"])
        if sub_id and sub_id in sub_by_id:
            text += " " + str(sub_by_id[sub_id].get("objective", "")).lower()
        if any(j in text for j in _JUDGMENT):
            continue
        if any(m in text for m in _MECHANICAL):
            warnings.append(
                f"step {step['id']!r} is agentic but reads as mechanical work "
                f"({step.get('rationale', '')!r}); consider a deterministic script "
                f"instead of a subagent (simplicity-first)."
            )
    return warnings
```

- [ ] **Step 5: Run — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_warnings 2>&1 | tail -4
```

Expected output:
```
Ran 3 tests in 0.0XXs

OK
```

- [ ] **Step 6: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: warn (never expand) on subagent-where-script-would-do (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: The CLI — write files, exit codes, --dry-run (TDD)

Wire the renderers into `main()`. CLI: `python scaffold.py <blueprint.md> --out <dir> [--dry-run]`. It loads the blueprint, prints warnings, and writes the artifact tree under `<dir>/.claude/`:
- `.claude/agents/<id>.md` per subagent
- `.claude/scripts/<id>.sh` per deterministic step (mode 0o755)
- `.claude/hooks/<name>-gate.sh` per rubric + `.claude/hooks.json` (0o755 on scripts)
- `.claude/commands/<workflow>.md` entry point

Exit codes: `0` = wrote (or dry-ran) cleanly; `1` = a `ScaffoldError` (incomplete contract); `2` = file unreadable / no yaml block. `--dry-run` prints the planned files + warnings and writes nothing.

**Files:**
- Create: `skills/agent-build-scaffold/scripts/tests/test_cli.py`
- Modify: `skills/agent-build-scaffold/scripts/scaffold.py`

- [ ] **Step 1: Write the failing CLI tests.** They use `tempfile.TemporaryDirectory` so nothing touches the repo.

`skills/agent-build-scaffold/scripts/tests/test_cli.py`:
```python
import os
import tempfile
import unittest

from scaffold import main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestCli(unittest.TestCase):
    def _run(self, fixture, *extra):
        path = os.path.join(FIXTURES, fixture)
        with tempfile.TemporaryDirectory() as out:
            rc = main([path, "--out", out, *extra])
            tree = sorted(
                os.path.relpath(os.path.join(r, f), out)
                for r, _, fs in os.walk(out) for f in fs
            )
            return rc, out, tree

    def test_full_blueprint_writes_all_constructs(self):
        rc, _out, tree = self._run("refund-triage.blueprint.md")
        self.assertEqual(rc, 0)
        self.assertIn(os.path.join(".claude", "agents", "reason-classifier.md"), tree)
        self.assertIn(os.path.join(".claude", "scripts", "fetch-order.sh"), tree)
        self.assertIn(os.path.join(".claude", "scripts", "issue-refund.sh"), tree)
        self.assertIn(os.path.join(".claude", "hooks", "classification-accuracy-gate.sh"), tree)
        self.assertIn(os.path.join(".claude", "hooks.json"), tree)
        self.assertIn(os.path.join(".claude", "commands", "refund-triage.md"), tree)

    def test_scripts_are_executable(self):
        rc, out, _tree = self._run("refund-triage.blueprint.md")
        self.assertEqual(rc, 0)
        script = os.path.join(out, ".claude", "scripts", "fetch-order.sh")
        self.assertTrue(os.access(script, os.X_OK))

    def test_deterministic_only_writes_no_agents_and_no_hooks_json(self):
        rc, _out, tree = self._run("csv-to-slack.blueprint.md")
        self.assertEqual(rc, 0)
        self.assertFalse(any(p.startswith(os.path.join(".claude", "agents")) for p in tree))
        # no rubric gates -> no hooks.json is written (gateless workflow)
        self.assertNotIn(os.path.join(".claude", "hooks.json"), tree)

    def test_dry_run_writes_nothing(self):
        rc, _out, tree = self._run("refund-triage.blueprint.md", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(tree, [])

    def test_partial_contract_exits_one(self):
        rc, _out, _tree = self._run("broken_partial_contract.blueprint.md")
        self.assertEqual(rc, 1)

    def test_no_yaml_block_exits_two(self):
        rc, _out, _tree = self._run("broken_no_yaml.blueprint.md")
        self.assertEqual(rc, 2)

    def test_missing_file_exits_two(self):
        rc = main([os.path.join(FIXTURES, "does_not_exist.blueprint.md"), "--out", "/tmp/x"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL** (no `main` yet):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest tests.test_cli 2>&1 | tail -5
```

Expected: `ImportError: cannot import name 'main' from 'scaffold'`.

- [ ] **Step 3: Implement `_workflow_name`, `scaffold_blueprint`, and `main`.** Append to `scaffold.py`:

```python
def _workflow_name(bp: dict, path: str) -> str:
    """Derive the workflow slug: blueprint frontmatter `name` is not in the yaml
    block, so fall back to the filename stem (<name>.blueprint.md -> <name>)."""
    stem = Path(path).name
    for suffix in (".blueprint.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return slugify(stem)


@dataclass
class Plan:
    """The set of files a scaffold run will write (relative path -> contents)."""
    files: dict = field(default_factory=dict)
    executable: set = field(default_factory=set)
    warnings: list = field(default_factory=list)


def scaffold_blueprint(bp: dict, workflow_name: str) -> Plan:
    """Build the in-memory file plan for a blueprint. Raises ScaffoldError on an
    incomplete contract. Pure: writes nothing."""
    plan = Plan()
    plan.warnings = warn_overpowered_steps(bp)

    for sa in (bp.get("subagents") or []):
        rel = os.path.join(".claude", "agents", subagent_filename(sa))
        plan.files[rel] = render_subagent(sa)

    for step in (bp.get("steps") or []):
        if step.get("kind") == DETERMINISTIC:
            rel = os.path.join(".claude", "scripts", step_script_filename(step))
            plan.files[rel] = render_step_script(step)
            plan.executable.add(rel)

    rubrics = bp.get("rubrics") or []
    for r in rubrics:
        rel = os.path.join(".claude", "hooks", hook_filename(r))
        plan.files[rel] = render_hook(r)
        plan.executable.add(rel)
    # Only emit hooks.json when there is at least one rubric gate to wire — an empty
    # hooks.json for a gateless workflow is wrong (nothing to enforce).
    if rubrics:
        plan.files[os.path.join(".claude", "hooks.json")] = render_hooks_json(
            rubrics, workflow_name=workflow_name)

    cmd_rel = os.path.join(".claude", "commands", f"{workflow_name}.md")
    plan.files[cmd_rel] = render_entry_command(bp, workflow_name=workflow_name)
    return plan


def _write_plan(plan: Plan, out_dir: str) -> None:
    for rel, contents in sorted(plan.files.items()):
        dest = Path(out_dir) / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        if rel in plan.executable:
            dest.chmod(0o755)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a validated workflow blueprint into Claude-Code-native artifacts.")
    parser.add_argument("path", help="path to <name>.blueprint.md")
    parser.add_argument("--out", default=".", help="output root (default: current dir)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the planned files + warnings; write nothing")
    args = parser.parse_args(argv)

    try:
        bp = load_blueprint(args.path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    name = _workflow_name(bp, args.path)
    try:
        plan = scaffold_blueprint(bp, name)
    except ScaffoldError as exc:
        print(f"SCAFFOLD ERROR: {exc}")
        return 1

    for w in plan.warnings:
        print(f"WARNING: {w}")

    if args.dry_run:
        print(f"\nDRY RUN — would write {len(plan.files)} file(s) under {args.out}/:")
        for rel in sorted(plan.files):
            print(f"  {rel}")
        return 0

    _write_plan(plan, args.out)
    print(f"\nWrote {len(plan.files)} file(s) under {args.out}/.claude/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: `os` is needed for `os.path.join` in `scaffold_blueprint`/`scaffold_blueprint`. Add `import os` to the top imports block (right after `import argparse`):

```python
import os
```

- [ ] **Step 4: Run the FULL suite — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest discover -s tests -t . 2>&1 | tail -4
```

Expected output (all tests across all test files: 4+8+4+4+4+3+7 = 34, but counts may vary slightly — what matters is the final `OK`):
```
Ran 34 tests in 0.0XXs

OK
```

- [ ] **Step 5: Smoke-test the CLI by hand against the full fixture** (confirms the renderer runs end-to-end from the command line, like the skill will invoke it):

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && \
python3 scaffold.py tests/fixtures/refund-triage.blueprint.md --out /tmp/agentbuild-smoke && \
find /tmp/agentbuild-smoke/.claude -type f | sort && \
rm -rf /tmp/agentbuild-smoke
```

Expected output (no WARNING lines for this fixture; the `find` lines follow the "Wrote" line, order may vary, then the dir is removed):
```
Wrote 6 file(s) under /tmp/agentbuild-smoke/.claude/
/tmp/agentbuild-smoke/.claude/agents/reason-classifier.md
/tmp/agentbuild-smoke/.claude/commands/refund-triage.md
/tmp/agentbuild-smoke/.claude/hooks.json
/tmp/agentbuild-smoke/.claude/hooks/classification-accuracy-gate.sh
/tmp/agentbuild-smoke/.claude/scripts/fetch-order.sh
/tmp/agentbuild-smoke/.claude/scripts/issue-refund.sh
```
(6 files: 1 agent + 2 scripts + 1 hook + 1 hooks.json + 1 command — the command filename `refund-triage.md` is the fixture's filename stem, which is what `_workflow_name` derives. The "Wrote N" count reads `6` because this fixture HAS a rubric gate, so hooks.json is written.)

- [ ] **Step 6: Verify the dry-run of the over-powered fixture prints the WARNING and writes nothing:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && \
python3 scaffold.py tests/fixtures/overpowered.blueprint.md --out /tmp/agentbuild-dry --dry-run
test -d /tmp/agentbuild-dry && echo "UNEXPECTED: dir created" || echo "OK: nothing written"
```

Expected output includes:
```
WARNING: step 'extract-id' is agentic but reads as mechanical work ...
DRY RUN — would write 3 file(s) under /tmp/agentbuild-dry/:
  .claude/agents/id-extractor.md
  .claude/agents/intent-judge.md
  .claude/commands/overpowered.md
OK: nothing written
```
(3 files: 2 agents + 1 command — NO hooks.json, because this fixture has `rubrics: []` (a gateless workflow gets no hooks.json under the FIX-E rule). The command filename `overpowered.md` is the fixture's filename stem.)

- [ ] **Step 7: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/scripts/
git commit -m "agent-build-scaffold: CLI writes artifact tree + exit codes + --dry-run (TDD)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: `references/rendering-map.md` (the canonical mapping table)

Spec §3.2 deliverable (c): the rendering map (blueprint element → CC construct). This file is the human-readable companion to `scaffold.py` and the authority the SKILL.md cites. The "test" for a prose reference is a structural grep (per the writing-plans rule).

**Files:**
- Create: `skills/agent-build-scaffold/references/rendering-map.md`

- [ ] **Step 1: Write the rendering map.**

`skills/agent-build-scaffold/references/rendering-map.md`:
```markdown
# Blueprint element → Claude-Code construct (the rendering map)

The canonical mapping `agent-build-scaffold` applies. Every row is implemented by a
function in `../scripts/scaffold.py` and exercised by `../scripts/tests/`. Volatile
Claude-Code specifics (frontmatter field names, model aliases, effort levels, hook
event names, the Task→Agent tool name) are cited from `citations.md`, never hardcoded
as guarantees here.

## Mapping table

| Blueprint element | Rendered to | Renderer | Determinism |
|---|---|---|---|
| **deterministic step** | a plain Bash script `.claude/scripts/<id>.sh` the orchestrator calls | `render_step_script` | deterministic |
| **agentic step** | a subagent `.claude/agents/<id>.md` carrying the full four-part contract + a non-contract `model` in frontmatter | `render_subagent` | non-deterministic, contained |
| **subagent four-part contract = objective · output_format · tools · boundaries** | `tools` → frontmatter `tools`; **objective**, **output_format**, **boundaries** → BODY sections (`output_format` is NEVER a frontmatter key — subagent frontmatter has no `output_format`). `model` → frontmatter `model`; `effort` → body note. Both `model` and `effort` are **non-contract**. | `render_subagent` | — |
| **rubric gate / guardrail** | a hook `.claude/hooks/<name>-gate.sh` (exit 0 = pass, exit 1 = block) wired in `.claude/hooks.json` (default event `SubagentStop`) | `render_hook` + `render_hooks_json` | deterministic |
| **loop + termination** | orchestrator control flow in the entry command, with the explicit `termination` surfaced as a deterministic check | `render_entry_command` | deterministic control, agentic body |
| **side_effecting / reversible step** | the step script wrapped with an idempotency-key guard (`side_effecting`) and a rollback note (`reversible`) | `render_step_script` | deterministic |
| **authored prompt** (`<name>.current.md`) | the prompt text the step's subagent runs (referenced; the human pastes it into the agent body or wires it) | — | — |
| **orchestration entry point** | a slash command `.claude/commands/<workflow>.md` that dispatches steps **one level deep** (interactive, session auth, no key) | `render_entry_command` | deterministic sequencing |

## The two load-bearing rules

1. **`output_format` is a body section, never frontmatter.** Subagent frontmatter has
   no `output_format` field. Structured output from a subagent is achieved by
   instructing it (in the body) to emit JSON, then parsing + validating that JSON in
   deterministic glue downstream — not by a frontmatter schema.
2. **Simplicity-first, enforced by a warning.** When an `agentic` step reads as
   mechanical work (extraction, formatting, lookup, parse, transform) with no
   genuine-judgment signal, the scaffolder **warns** (`warn_overpowered_steps`) — it
   never silently expands a subagent where a deterministic script would do. The human
   decides; the scaffolder never blocks on this heuristic.

## What is NOT rendered (out of scope, v1)

- A keyed Agent-SDK headless entry-point wrapper (the entry point is a slash command on
  session auth; see the architecture spec §6 non-goals).
- Multi-level subagent nesting (the runtime forbids it; orchestration stays one level).
- Auto-tuning `model`/`effort` per step (the blueprint recommends; the human approves).
```

- [ ] **Step 2: Structural check (the "test" for this prose file):**

```bash
cd /home/dawti/je-dev-skills && grep -c "render_subagent\|render_step_script\|render_hook\|render_entry_command\|warn_overpowered_steps" skills/agent-build-scaffold/references/rendering-map.md && \
grep -q "NEVER a frontmatter key\|never frontmatter" skills/agent-build-scaffold/references/rendering-map.md && echo "OK: output_format rule present" && \
grep -q "one level deep" skills/agent-build-scaffold/references/rendering-map.md && echo "OK: one-level rule present"
```

Expected output:
```
6
OK: output_format rule present
OK: one-level rule present
```
(The count must be ≥ 5 — every renderer named.)

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/references/rendering-map.md
git commit -m "agent-build-scaffold: add rendering-map reference

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: `references/patterns.md` (emitted-artifact patterns)

The shapes the renderer emits, documented so a human reviewing/editing a generated file knows the contract each artifact must keep.

**Files:**
- Create: `skills/agent-build-scaffold/references/patterns.md`

- [ ] **Step 1: Write the patterns reference.**

`skills/agent-build-scaffold/references/patterns.md`:
```markdown
# Emitted-artifact patterns

The structural contract each scaffolded file keeps. Edit a generated file freely, but
keep these invariants — the entry-point command and the gates depend on them.

## Subagent (`.claude/agents/<id>.md`)

```
---
name: <slug>
description: <objective>
tools: <comma-separated allowlist>     # least-privilege; from blueprint subagent.tools
model: <haiku|sonnet|opus|inherit>     # non-contract; from subagent.model
---
# <slug>

## Objective
<objective>

## Output format
<output_format>          # the contract field — a BODY section, never frontmatter

## Boundaries
<boundaries>

## Notes
- Recommended effort: <effort> (non-contract; tune per the live runtime).
- Emit ONLY the output described above; deterministic glue parses + validates it.
```

The subagent emits text/JSON only; it never dispatches its own subagent (one-level rule).

## Deterministic step script (`.claude/scripts/<id>.sh`)

- `#!/usr/bin/env bash` + `set -euo pipefail`.
- A header comment with the step id and its rationale.
- **side_effecting** → an idempotency guard: resolve a key from
  `retry.idempotency_key`, skip with exit 0 if `.agent-build-state/<key>.done`
  exists, run the body, then `touch` the marker — making a retried orchestration
  exactly-once.
- **reversible** → a rollback note carrying the compensating action.

## Rubric gate hook (`.claude/hooks/<name>-gate.sh` + `.claude/hooks.json`)

- Exit-code contract: **0 = pass, 1 = block.** The skeleton reads
  `.agent-build-state/<rubric>.score` and blocks when it is below the rubric `gate`.
- `hooks.json` wires each gate under the `SubagentStop` event (volatile — see
  `citations.md`), invoking the script by `${CLAUDE_PROJECT_DIR}`-relative path.
- The human wires the real score source; the exit-code contract stays fixed.

## Entry-point command (`.claude/commands/<workflow>.md`)

- Frontmatter: `description` + an `argument-hint` derived from the blueprint `inputs`.
- Body: the ordered step list. Each **deterministic** step says "run script `<id>.sh`";
  each **agentic** step says "dispatch subagent `<subagent-id>`" with its termination.
- States the **one-level-deep** rule and a **Gates** section: do not proceed past a
  blocked gate.

## State directory (`.agent-build-state/`)

Idempotency markers (`<key>.done`) and rubric scores (`<rubric>.score`) live here. It is
runtime state — add it to the project `.gitignore`.
```

- [ ] **Step 2: Structural check:**

```bash
cd /home/dawti/je-dev-skills && \
grep -q "never frontmatter" skills/agent-build-scaffold/references/patterns.md && echo "OK: output_format invariant" && \
grep -q "0 = pass, 1 = block" skills/agent-build-scaffold/references/patterns.md && echo "OK: exit-code contract" && \
grep -q "idempotency guard" skills/agent-build-scaffold/references/patterns.md && echo "OK: idempotency pattern"
```

Expected output:
```
OK: output_format invariant
OK: exit-code contract
OK: idempotency pattern
```

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/references/patterns.md
git commit -m "agent-build-scaffold: add emitted-artifact patterns reference

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: `references/citations.md` (dated volatile CC specifics)

Spec §3.4: a dated `references/citations.md` for all volatile specifics, mirroring `workflow-design-interview/references/citations.md`. This is the single home for everything the SKILL.md must `verify-against-runtime` before emitting files.

**Files:**
- Create: `skills/agent-build-scaffold/references/citations.md`

- [ ] **Step 1: Write the citations reference.**

`skills/agent-build-scaffold/references/citations.md`:
```markdown
# Citations — agent-build-* (dated, volatile)

Dated sources grounding the `agent-build-*` skills, plus a **volatile-values** section
for Claude-Code specifics that change faster than the design. Source grounding:
`docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md` §7.

**Convention.** Primary Anthropic sources first. Everything liable to change carries an
explicit *as of* date and a `verify-against-runtime` instruction. Skill prose and the
renderer cite *this* file rather than hardcoding volatile specifics.

## Primary sources (Anthropic)

- **Claude Code sub-agents.** `.claude/agents/<name>.md` markdown agents, the Agent/Task
  tool, one-level-deep delegation, context isolation, the four-part subagent contract.
  <https://docs.anthropic.com/en/docs/claude-code/sub-agents>. *As of 2026-05-29.*
- **Claude Code hooks.** Hook events (`PreToolUse`, `PostToolUse`, `Stop`,
  `SubagentStop`, `SessionStart`/`End`, `UserPromptSubmit`, `PreCompact`,
  `Notification`), `hooks.json` shape, the exit-code blocking contract,
  `${CLAUDE_PROJECT_DIR}`. *As of 2026-05-29.*
- **Claude Code slash commands.** `.claude/commands/<name>.md`, frontmatter
  (`description`, `argument-hint`), `$ARGUMENTS`. *As of 2026-05-29.*
- **Agent Skills — overview & best practices.** SKILL.md frontmatter, progressive
  disclosure, scripts-vs-instructions. *As of 2026-05-29.*
- **Building Effective Agents** — Schluntz & Zhang, 19 Dec 2024. "Start simple; add
  complexity only when it improves outcomes" — grounds the warn-on-over-powered rule.
- **`plugin-dev/agent-development`** (companion plugin — see `CONTRIBUTING.md`; install
  `plugin-dev@claude-plugins-official`). The canonical **authoring** guidance for the
  subagents this skill renders — system-prompt structure, discovery-optimized
  `description`s, least-privilege `tools`: `references/system-prompt-design.md`,
  `triggering-examples.md`, `agent-creation-system-prompt.md`. This skill owns the
  blueprint→artifact *mapping* and the deterministic renderers, **not** a fresh
  agent-authoring manual — reuse plugin-dev rather than duplicate it (spec §3.5).
  Validate emitted `.claude/agents/*.md` with plugin-dev's `scripts/validate-agent.sh`
  and the `skill-reviewer` / `plugin-validator` agents. *As of 2026-05-29.*

## Volatile values (re-check on each use — verify-against-runtime)

Do NOT hardcode these as load-bearing constants. The renderer emits them from the
blueprint and this file documents the *expected* shape; re-verify against the live
runtime (`~/.claude`, current docs) before relying on a field.

### Subagent frontmatter fields

Expected keys: `name`, `description`, `tools` (comma-separated allowlist), `model`.
**There is NO `output_format` frontmatter key** — the contract's output spec is rendered
as a body section. `effort` is **not** a confirmed frontmatter field; the renderer puts
it in a body note. Confirm the exact frontmatter field set against the sub-agents doc
before emitting. *As of 2026-05-29.*

### Model aliases & effort levels

The blueprint stores a **tier** (`haiku|sonnet|opus|inherit`), never a pinned ID. Map
tier → current alias against the
[models overview](https://docs.anthropic.com/en/docs/about-claude/models/overview).
Effort levels (`low|medium|high|max`) and whether they are a frontmatter field at all
are version-volatile — verify before relying on them. *As of 2026-05-29.*

### Hook event names

The renderer defaults rubric gates to the `SubagentStop` event. Event names have churned
across versions; confirm the current event set in the hooks doc before wiring a gate.
*As of 2026-05-29.*

### The Task → Agent tool rename

The tool that dispatches a subagent has been called both **Task** and **Agent**. Treat
the *capability* (one-level delegation) as stable and the exact tool name as volatile —
verify the current name in the sub-agents doc. *As of 2026-05-29.*

### Open runtime questions (architecture spec §6 — confirm before relying)

1. Does a skill-dispatched subagent inherit the parent session's permission mode, or must
   each declare its own `tools`/permissions?
2. Does a skill-dispatched subagent's context include the working directory/repo?
3. Do hooks (`PreToolUse`/`SubagentStop`) fire for subagents dispatched within a skill,
   or only at the parent session level?
4. Can a skill pass inline agent definitions, or must they be on-disk in `.claude/agents/`?

*As of 2026-05-29 — all four are unverified-pending-runtime.*
```

- [ ] **Step 2: Structural check:**

```bash
cd /home/dawti/je-dev-skills && \
grep -q "NO .output_format. frontmatter key\|NO \`output_format\` frontmatter key" skills/agent-build-scaffold/references/citations.md && echo "OK: output_format note" && \
grep -c "As of 2026-05-29" skills/agent-build-scaffold/references/citations.md && \
grep -q "SubagentStop" skills/agent-build-scaffold/references/citations.md && echo "OK: hook event cited" && \
grep -q "plugin-dev/agent-development" skills/agent-build-scaffold/references/citations.md && echo "OK: plugin-dev authoring citation"
```

Expected output (the count must be ≥ 4 — multiple dated entries):
```
OK: output_format note
7
OK: hook event cited
OK: plugin-dev authoring citation
```

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/references/citations.md
git commit -m "agent-build-scaffold: add dated citations reference (volatile CC specifics)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: `agent-build-scaffold/SKILL.md`

The skill body — a table of contents + procedure that runs the renderer, reads warnings, verifies volatile specifics, and reports. Frontmatter follows the repo idiom (`workflow-design-validate/SKILL.md`).

**Files:**
- Create: `skills/agent-build-scaffold/SKILL.md`

- [ ] **Step 1: Write the SKILL.md.**

`skills/agent-build-scaffold/SKILL.md`:
```markdown
---
name: agent-build-scaffold
description: This skill should be used when the user asks to "scaffold an agent", "build the agent from my blueprint", "turn my workflow design into Claude Code files", "generate subagents and hooks", "render my blueprint into a runnable agent", or right after workflow-design-validate passes and prompt-engineering-author has produced prompts. It renders a validated blueprint into .claude/ subagents, hooks, scripts, and an entry-point command, warning when a subagent is used where a script would do.
argument-hint: "[path to the validated <name>.blueprint.md]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Agent Build: Scaffold

Render a **validated** workflow blueprint into Claude-Code-native artifacts: subagents
(`.claude/agents/`), rubric-gate hooks (`.claude/hooks/`), deterministic step scripts
(`.claude/scripts/`), and a one-level-deep orchestration entry-point command
(`.claude/commands/`). Generation is deterministic where possible — a Python renderer
does the file emission; the model only fills the placeholder bodies and wires the real
commands afterward.

This is the **build** step of the plugin lifecycle: design (`workflow-design-*`) →
author prompts (`prompt-engineering-author`) → **build & run (`agent-build-*`)** →
measure (`prompt-evals-*`) → improve (`prompt-engineering-improve`).

The rendering map (blueprint element → Claude-Code construct) is
`${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/references/rendering-map.md`. The
emitted-artifact patterns are in `references/patterns.md`. All version-volatile
Claude-Code specifics live in `references/citations.md`.

## Preconditions

- A **validated** blueprint exists (`workflow-design-validate` exits 0 on it). If the
  user passed a path, use it; otherwise Glob `./workflows/*.blueprint.md`. If none
  exists, stop and route the user to **`workflow-design-interview`** →
  **`workflow-design-validate`** first.
- Optionally, authored prompts from **`prompt-engineering-author`** for the agentic
  steps. Absent prompts are fine — the subagent bodies are scaffolded and the human
  pastes the authored prompt text in.

## Procedure

### 1. Install the renderer dependency (idempotent)

```bash
pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/requirements.txt
```

### 2. Dry-run first — read the plan and the warnings

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/scaffold.py <path> --out . --dry-run
```

This prints the files it *would* write and any **WARNING** lines. A warning means an
`agentic` step reads as mechanical work (a deterministic script would do) — the
scaffolder never silently expands it. For each warning, decide with the user: keep the
subagent (genuine judgment the heuristic missed) or revise the blueprint's step to
`kind: deterministic` and re-validate. **Do not proceed past unresolved warnings
without an explicit decision.**

Exit codes: `0` = clean plan; `1` = an incomplete subagent contract (fix the blueprint
and re-validate); `2` = unreadable file or not exactly one fenced `yaml` block.

### 3. Verify the volatile Claude-Code specifics before emitting

Open `references/citations.md` and re-verify, against the current runtime/docs, the
fields the renderer emits: subagent frontmatter keys (`name`, `description`, `tools`,
`model` — and that there is **no `output_format` frontmatter key**), the model tier →
alias mapping, the hook event name (default `SubagentStop`), and the dispatch tool name.
If a field has changed, note it and adjust the emitted files in step 5.

### 4. Write the artifacts

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/scaffold.py <path> --out .
```

This writes under `./.claude/`: `agents/<id>.md`, `scripts/<id>.sh` (executable),
`hooks/<name>-gate.sh` (executable) + `hooks.json`, and `commands/<workflow>.md`.

### 5. Wire the real content

The renderer emits **placeholders**, not finished code. With the Edit tool:
- **Subagent bodies:** paste the authored prompt text (from `prompt-engineering-author`)
  into each agent's Objective/body, keeping the **Output format** section (the contract's
  output spec is a body section, never frontmatter).
- **Deterministic scripts:** replace each `TODO` with the real command; keep the
  idempotency guard on `side_effecting` steps and the strict-mode header.
- **Rubric-gate hooks:** wire the real score source into the gate script; keep the
  exit-code contract (0 = pass, 1 = block).
- **Entry command:** confirm the step order and termination conditions match the
  blueprint.

**Authoring & validating the subagents (companion plugin).** For *how* to write a strong
subagent — system-prompt structure, a discovery-optimized `description`, least-privilege
`tools` — follow `plugin-dev/agent-development`'s guidance (`references/system-prompt-design.md`,
`triggering-examples.md`); this skill renders the contract skeleton and reuses that guidance
rather than restating it (see `references/citations.md` and `CONTRIBUTING.md`). Optionally
validate the emitted files: run `plugin-dev`'s `scripts/validate-agent.sh` over each
`.claude/agents/*.md`, or ask the `plugin-validator` / `skill-reviewer` agents. Optional by
design — the renderer works offline without plugin-dev installed; this is a quality pass, not a
dependency.

### 6. Add runtime state to .gitignore

```bash
grep -qxF '.agent-build-state/' .gitignore 2>/dev/null || echo '.agent-build-state/' >> .gitignore
```

### 7. Report and hand off

Confirm what was written (count + paths), list any warnings and how they were resolved,
and tell the user the next step is **`/je-dev-skills:agent-build-run`** to drive the
scaffolded app, then **`/je-dev-skills:prompt-evals-*`** to measure it.

## Definition of done

- `scaffold.py` exits `0` (or `0` on `--dry-run`) with all warnings resolved by an
  explicit decision.
- `./.claude/` contains a subagent per agentic step's subagent, a script per
  deterministic step, a hook per rubric gate + `hooks.json`, and one entry command.
- Volatile specifics were re-verified against the runtime (step 3).
- `.agent-build-state/` is gitignored.

## Offline check (no API key)

The renderer's own tests run fully offline:

```bash
cd ${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts && python3 -m unittest discover -s tests -t .
```

## Notes

- **Deterministic generation, model-assisted wiring.** File emission is pure Python; the
  model only fills bodies and wires commands. This keeps the volatile surface auditable.
- **Simplicity-first.** The scaffolder warns (never expands) on a subagent where a
  script would do — see `references/rendering-map.md`.
- **One level deep.** The entry command is the top-level orchestrator; subagents are
  leaves and never dispatch their own subagents.
```

- [ ] **Step 2: Structural check** (required sections + key rules present):

```bash
cd /home/dawti/je-dev-skills && \
for s in "## Preconditions" "## Procedure" "## Definition of done" "## Offline check"; do \
  grep -qF "$s" skills/agent-build-scaffold/SKILL.md && echo "OK: $s" || echo "MISSING: $s"; done && \
grep -q "no .output_format. frontmatter key\|no \`output_format\` frontmatter key" skills/agent-build-scaffold/SKILL.md && echo "OK: output_format rule" && \
grep -q "never silently expands\|never silently expand" skills/agent-build-scaffold/SKILL.md && echo "OK: warn rule" && \
grep -q "\${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/scripts/scaffold.py" skills/agent-build-scaffold/SKILL.md && echo "OK: invokes renderer by plugin path"
```

Expected output: all `OK:` lines, no `MISSING:`.

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-scaffold/SKILL.md
git commit -m "agent-build-scaffold: add SKILL.md (TOC + procedure)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: `agent-build-run/SKILL.md`

Spec §3.1 deliverable (b): drive the scaffolded application in-session, one-level subagent dispatch, honoring gates/loops/termination. This is an authored-markdown skill (no Python — it orchestrates the human/Claude turns). Its "test" is a structural grep + a documented manual scenario.

**Files:**
- Create: `skills/agent-build-run/SKILL.md`

- [ ] **Step 1: Write the SKILL.md.**

`skills/agent-build-run/SKILL.md`:
```markdown
---
name: agent-build-run
description: This skill should be used when the user asks to "run the scaffolded agent", "drive my agent workflow", "execute the agent-build app", "run the workflow end to end", or after agent-build-scaffold has emitted .claude/ artifacts. It drives the scaffolded application in-session — dispatching deterministic steps as scripts and agentic steps as subagents, one level deep, honoring rubric gates, loops, and termination conditions, with no API key on the interactive path.
argument-hint: "[workflow name, e.g. refund-triage] [the workflow inputs]"
allowed-tools: Bash, Read, Write, Edit, Glob, Task
version: 0.1.0
---

# Agent Build: Run

Drive a **scaffolded** agent application (produced by `agent-build-scaffold`) inside the
current Claude Code session. The orchestration is **one level deep** and runs on
**session auth — no `ANTHROPIC_API_KEY`** on this interactive path: this skill is the
top-level orchestrator, deterministic steps run as scripts, agentic steps run as
dispatched subagents (leaves that never dispatch their own subagents).

This is the **run** half of the build lifecycle: scaffold → **run**. For a *headless/CI*
unattended run, use the keyed Agent-SDK/`claude -p` fallback instead (requires a key) —
that path is out of scope for this skill.

## Preconditions

- `./.claude/commands/<workflow>.md` exists (the entry-point command
  `agent-build-scaffold` wrote). If absent, stop and route to
  **`/je-dev-skills:agent-build-scaffold`** first.
- The subagent bodies, step scripts, and gate hooks have been **wired** (step 5 of
  scaffold) — placeholders replaced with real content. If they still contain `TODO`
  markers, warn the user that the run will exercise stubs.

## Procedure

### 1. Load the orchestration plan

Read `./.claude/commands/<workflow>.md`. It lists the ordered steps, each marked
**deterministic** ("run script `<id>.sh`") or **agentic** ("dispatch subagent
`<subagent-id>`") with its termination condition, plus a Gates section.

### 2. Run each step in order

For each step, in the listed order:

- **Deterministic step** → run its script and capture the exit code:

  ```bash
  bash ./.claude/scripts/<id>.sh
  ```

  A non-zero exit halts the workflow — report the failure and stop. For a
  `side_effecting` step the script is idempotent on its declared key, so a re-run after a
  transient failure is safe.

- **Agentic step** → **dispatch the named subagent one level deep** via the Task/Agent
  tool, passing the step's inputs and the authored prompt. The subagent returns text or
  JSON per its **Output format** body section. **Never** let a subagent dispatch its own
  subagent (the runtime forbids nesting). Honor the step's **termination** condition: stop
  the step when it is met; if it is a loop, stop at the termination check or the budget.

### 3. Honor gates

After a graded step, its rubric-gate hook (`.claude/hooks/<name>-gate.sh`, wired in
`hooks.json`) evaluates the score and **blocks on a sub-threshold result** (exit 1). If a
gate blocks: do **not** proceed to the next step — report the blocked gate, the score,
and the threshold, and stop. Gates are deterministic; do not override them by reasoning.

### 4. Honor loops and termination

For any step the entry command marks as a loop, run the body until the explicit
**termination** condition holds or the blueprint budget (`max_turns` / `max_tool_calls`)
is reached — whichever comes first. There is always an explicit stop; never loop
unbounded.

### 5. Report the run

Summarize: which steps ran, each step's outcome (script exit / subagent output summary),
any gate that blocked, and the final workflow output. If the workflow completed, point
the user at **`/je-dev-skills:prompt-evals-run`** to measure it.

## Definition of done

- Every step ran in order, or the run halted at the first failed script / blocked gate
  with a clear report.
- No subagent dispatched a sub-subagent (one-level invariant held).
- Every loop terminated on its explicit condition or budget.
- The final output (or the halt reason) was reported to the user.

## Manual verification scenario (no API key; not unit-testable)

This skill orchestrates live model turns, so it is verified by a documented manual
scenario rather than a unit test: scaffold the `valid_full` fixture
(`agent-build-scaffold/scripts/tests/fixtures/valid_full.blueprint.md`) into a scratch
project, wire the `classify-reason` subagent with a trivial prompt and the two scripts
with `echo` stubs, then run this skill — confirm (a) `classify-reason` dispatches the
`reason-classifier` subagent one level deep, (b) `fetch-order.sh` and `issue-refund.sh`
run in order, (c) a sub-threshold `classification-accuracy` score blocks the gate and
halts the run.

## Notes

- **No key on the interactive path.** This skill uses session auth via subagent dispatch.
  An unattended headless run needs the keyed fallback (out of scope here).
- **One level deep.** See `${CLAUDE_PLUGIN_ROOT}/skills/agent-build-scaffold/references/citations.md`
  for the (volatile) dispatch-tool name and the open runtime questions about subagent
  permissions/context/hook-firing — re-verify before a high-stakes run.
```

- [ ] **Step 2: Structural check:**

```bash
cd /home/dawti/je-dev-skills && \
for s in "## Preconditions" "## Procedure" "## Definition of done" "## Manual verification scenario"; do \
  grep -qF "$s" skills/agent-build-run/SKILL.md && echo "OK: $s" || echo "MISSING: $s"; done && \
grep -q "one level deep" skills/agent-build-run/SKILL.md && echo "OK: one-level rule" && \
grep -q "no .ANTHROPIC_API_KEY.\|no \`ANTHROPIC_API_KEY\`" skills/agent-build-run/SKILL.md && echo "OK: no-key path" && \
grep -q "blocks on a sub-threshold\|block" skills/agent-build-run/SKILL.md && echo "OK: gate honoring"
```

Expected output: all `OK:` lines, no `MISSING:`.

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add skills/agent-build-run/SKILL.md
git commit -m "agent-build-run: add SKILL.md (drive scaffolded app one level deep)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: README — unify the lifecycle (replace both island blurbs)

Spec §4.2: replace **both** existing per-group lifecycle blurbs with the single unified design→author→build→measure→improve narrative + a lifecycle diagram, add an `agent-build-*` group row, and a cost note. Do not merely append a row.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the top description + the two skill-group sections.** In `README.md`, replace the block from line 3 (`A Claude Code **plugin**...`) through line 28 (the workflow-design lifecycle sentence ending `[docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md](docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md).`) with the unified narrative. Use the Edit tool with this `old_string` (the current text) → `new_string`.

`old_string` (read `README.md` lines 3–28 first to copy exactly; it is the block beginning `A Claude Code **plugin** of skills for adding LLM-graded` and ending with `See the design spec at\n[docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md](docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md).`).

`new_string`:
```markdown
A Claude Code **plugin** that helps you build high-quality agent applications, end to
end, inside Claude Code — with deterministic code over non-deterministic wherever
possible.

## The lifecycle

**Design → author → build & run → measure → improve**, one journey:

```
workflow-design-*  →  prompt-engineering-author  →  agent-build-*  →  prompt-evals-*  →  prompt-engineering-improve
   (design)              (author prompts)            (build + run)      (measure)            (improve, looped)
```

The **interactive path runs in Claude Code on session auth — no API key**. Headless/CI
execution uses a keyed fallback (`ANTHROPIC_API_KEY`).

| Skill group | Invoke | What it does |
|-------------|--------|--------------|
| `workflow-design-*` | `/je-dev-skills:workflow-design-{interview,validate}` | Turn an idea into a checked `./workflows/<name>.blueprint.md` and lint it for completeness. |
| `prompt-engineering-author` | `/je-dev-skills:prompt-engineering-author` | Author or refactor a strong single-shot prompt from a task description (eval-free). |
| `agent-build-*` | `/je-dev-skills:agent-build-{scaffold,run}` | Render a validated blueprint + authored prompts into `.claude/` subagents, hooks, scripts, and an entry-point command, then drive them in-session one level deep (no API key). |
| `prompt-evals-*` | `/je-dev-skills:prompt-evals-{setup,create-dataset,run}` | Vendor the eval framework, generate & freeze a dataset, run the prompt/agent under test, and grade outputs into a scored report. |
| `prompt-engineering-improve` | `/je-dev-skills:prompt-engineering-improve` | Drive an eval-driven improve loop (measure → diagnose → rewrite) with deterministic stopping rules. |

**Cost note.** The interactive subagent-dispatch path uses your Claude Code session and
needs no API key. Headless/CI runs draw on the Agent-SDK/headless credit (the 2026-06-15
billing split — verify the current wording before relying on it). A full eval round is
~`2 × num_cases` model calls (execute + grade per case).

See the design specs:
[docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md](docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md),
[docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md](docs/superpowers/specs/2026-05-29-agent-build-and-execution-spec.md),
and [docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md](docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md).
```

(If `prompt-engineering-author`/`-improve` are not yet merged when this task runs, the
rows still correctly describe the unified plugin per the specs — the README documents
the lifecycle the plugin is being built toward.)

- [ ] **Step 2: Verify the islands are gone and the unified story is present:**

```bash
cd /home/dawti/je-dev-skills && \
grep -q "design → author → build" README.md || grep -qi "Design → author → build & run → measure → improve" README.md && echo "OK: unified narrative" && \
grep -q "agent-build-\*" README.md && echo "OK: agent-build row" && \
grep -qi "Cost note" README.md && echo "OK: cost note" && \
grep -qi "no API key" README.md && echo "OK: no-key qualifier" && \
test "$(grep -c 'The skills form a lifecycle' README.md)" = "0" && echo "OK: old island blurbs removed"
```

Expected output: all `OK:` lines.

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add README.md
git commit -m "README: unify into one design→author→build→measure→improve lifecycle + agent-build row + cost note

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: `.claude-plugin/plugin.json` — one-journey description + keywords

Spec §4.2: rewrite `description` to the one-journey sentence; update `keywords`; **keep `orchestration`** (scoped to the in-CC runtime, since `agent-build-run` ships).

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Edit the description and keywords.** Replace the `description` line:

`old_string`:
```
  "description": "A personal collection of Claude Code skills. Includes a prompt/agent evaluation lifecycle (prompt-evals-*: setup, create-dataset, run) and a workflow-design lifecycle (workflow-design-*: interview, validate) that turns an idea into a checked workflow blueprint.",
```

`new_string`:
```
  "description": "Build high-quality agent applications inside Claude Code, end to end: design the workflow into a validated blueprint (workflow-design-*), author the prompts (prompt-engineering-author), build & run the agent as Claude-Code-native artifacts with no API key on the interactive path (agent-build-*), measure it (prompt-evals-*), and improve it through an eval-driven loop (prompt-engineering-improve). Headless/CI uses a keyed fallback.",
```

Then replace the `keywords` line:

`old_string`:
```
  "keywords": ["evaluation", "evals", "prompt-engineering", "llm-as-judge", "testing", "agents", "workflow", "orchestration", "blueprint", "agent-design"]
```

`new_string`:
```
  "keywords": ["agent-development", "evaluation", "evals", "prompt-engineering", "llm-as-judge", "testing", "agents", "workflow", "orchestration", "blueprint", "agent-design", "scaffold", "subagents"]
```

- [ ] **Step 2: Verify the JSON is valid and scoped `orchestration` is kept:**

```bash
cd /home/dawti/je-dev-skills && python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert 'orchestration' in d['keywords']; assert 'agent-build' in d['description'] or 'agent-build-*' in d['description']; assert 'end to end' in d['description']; print('OK: valid json, orchestration kept, one-journey description')"
```

Expected output:
```
OK: valid json, orchestration kept, one-journey description
```

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add .claude-plugin/plugin.json
git commit -m "plugin.json: one-journey description + keywords (keep scoped orchestration)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: WORKFLOW_DESIGN_SPEC §9 — relocate the scaffold roadmap entry

Spec §4.2: relocate the `workflow-design-scaffold` roadmap entry — it is superseded by `agent-build-*`. Add a one-line pointer so the two specs don't both claim scaffolding.

**Files:**
- Modify: `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md`

- [ ] **Step 1: Replace the scaffold roadmap bullet.** In §9 (lines 335–337), replace:

`old_string`:
```
- **`workflow-design-scaffold`** — render the Claude-Code layer of a validated
  blueprint into actual skill / subagent / script files. The most volatile surface
  (Claude Code internals churn), deferred deliberately.
```

`new_string`:
```
- **`workflow-design-scaffold` — SUPERSEDED → `agent-build-*`.** Rendering a validated
  blueprint into the Claude-Code layer (subagents / hooks / scripts / an entry-point
  command) is now owned by the **`agent-build-*`** group, which ships scaffold **and** a
  one-level-deep in-session runner. See
  [2026-05-29-agent-build-and-execution-spec.md](../specs/2026-05-29-agent-build-and-execution-spec.md)
  §3. This roadmap entry is retained only as a pointer; the deferred-scaffold work is no
  longer planned here.
```

- [ ] **Step 2: Verify the relocation:**

```bash
cd /home/dawti/je-dev-skills && \
grep -q "SUPERSEDED → .agent-build-\*\|SUPERSEDED" docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md && echo "OK: superseded marker" && \
grep -q "agent-build-and-execution-spec.md" docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md && echo "OK: pointer to agent-build spec" && \
test "$(grep -c 'render the Claude-Code layer of a validated' docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md)" = "0" && echo "OK: old deferred bullet removed"
```

Expected output: all `OK:` lines.

- [ ] **Step 3: Commit.**

```bash
cd /home/dawti/je-dev-skills && git add docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md
git commit -m "WORKFLOW_DESIGN_SPEC §9: relocate scaffold roadmap entry to agent-build-*

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 19: Full offline test sweep + final verification

Confirm the whole renderer suite is green and nothing in the framework core was touched.

**Files:** none (verification only).

- [ ] **Step 1: Run the full renderer suite — expect PASS:**

```bash
cd /home/dawti/je-dev-skills/skills/agent-build-scaffold/scripts && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -6
```

Expected output ends with:
```
Ran 34 tests in 0.0XXs

OK
```
(Exact count depends on the methods written across Tasks 2–10; every test file must pass with a final `OK` and zero failures/errors.)

- [ ] **Step 2: Confirm the framework CORE is untouched** (composition invariant — this group must not have modified `evaluator/*.py` or `prompts/`):

```bash
cd /home/dawti/je-dev-skills && git diff --name-only main...HEAD -- skills/prompt-evals-setup/framework/evals/evaluator skills/prompt-evals-setup/framework/evals/prompts
```

Expected output: **empty** (no core files changed by this branch's agent-build commits). If the branch also carries sibling-plan commits that legitimately touch `config.py`/`run_eval.py`/`aggregate.py`, those are at the vendored top level — NOT under `evaluator/` or `prompts/` — and this command (scoped to `evaluator/` + `prompts/`) must still print nothing.

- [ ] **Step 3: Confirm the workflow-design-validate suite still passes** (we reused its parsing idiom; ensure no accidental coupling broke it):

```bash
cd /home/dawti/je-dev-skills/skills/workflow-design-validate/scripts && python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected output ends with `OK`.

- [ ] **Step 4: Final commit (only if any verification fix was needed; otherwise skip).** If steps 1–3 all pass with no edits, there is nothing to commit. If a fix was required, commit it:

```bash
cd /home/dawti/je-dev-skills && git add -A && git commit -m "agent-build-*: verification sweep fixes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Coverage summary

- **Spec §3.1 (two skills: scaffold → run):** Tasks 14 (scaffold SKILL.md), 15 (run SKILL.md). `agent-build-run` ships in this cut.
- **Spec §3.2 (rendering map):** Tasks 4 (deterministic step → script), 5 (agentic step → subagent, output_format as body), 6 (contract completeness), 7 (rubric gate → hook), 8 (entry command, one level deep), 11 (the canonical `rendering-map.md`).
- **Spec §3.3 (simplicity-first; warn, never expand):** Task 9 (`warn_overpowered_steps` + tests), surfaced by the CLI (Task 10) and the SKILL procedure (Task 14 step 2).
- **Spec §3.4 (volatility containment):** Task 13 (`citations.md`), the verify-against-runtime step in Task 14 step 3, no hardcoded volatile constants in the renderer.
- **Spec §4 (plugin composition):** Task 16 (README unify + agent-build row + cost note), Task 17 (plugin.json one-journey + keep scoped `orchestration`), Task 18 (WORKFLOW_DESIGN_SPEC §9 relocation).
- **Spec §5 DoD — offline acceptance:** Tasks 2–10 (TDD renderer with good/bad fixtures), Task 9 (warn assertion), Task 19 (full sweep + composition-invariant check). Interactive acceptance (subagent dispatch, gates) is the documented manual scenario in Task 15.
- **Composition invariant:** Task 19 step 2 asserts `evaluator/*.py` + `prompts/` are untouched by this group.
```
