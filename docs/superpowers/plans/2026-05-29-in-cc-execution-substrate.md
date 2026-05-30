# In-Claude-Code Execution Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the no-API-key execution substrate so prompt evals can run inside an interactive Claude Code session (subagent dispatch + a deterministic offline report assembler), while keeping the existing keyed `AnthropicClient` loop as a headless/CI fallback.

**Architecture:** The framework CORE (`evals/evaluator/*.py`, `evals/prompts/`) is frozen. We add a new deterministic, model-free `evals/aggregate.py` that reads per-case verdict JSON files and writes the framework's standard `output.json`/`output.html`; we add `EXECUTION_MODE` to `config.py`; we add a `check_placeholders` prompt-prep helper plus a file-backed `<name>.current.md` default to `run_eval.py` and make its `main()` mode-aware (under `in_claude_code` the `evaluate` command prints guidance and exits non-zero; the keyed `run_evaluation` loop runs only under `anthropic_api`, threading `run_label`); we rewrite `prompt-evals-run/SKILL.md`'s run procedure to the no-key "Path A" (skill dispatches execute+grade subagents per case → writes per-case verdict JSONs → calls `aggregate.py`) with Path B documented as fallback; and we update `prompt-evals-setup` so vendoring ships the new files non-clobbering on re-setup.

**Tech Stack:** Python 3.10+ (stdlib only for the new deterministic code; `anthropic` only on the keyed fallback path), `unittest` (offline tests, no API key, matching `skills/workflow-design-validate/scripts/tests/`), Markdown SKILL files.

---

## Orientation — read before starting

The framework is vendored at `skills/prompt-evals-setup/framework/evals/` and copied to a user's `./evals` by `prompt-evals-setup`. **All edits in this plan target the SOURCE under `skills/prompt-evals-setup/framework/evals/`** (never a user `./evals`). Absolute repo root: `/home/dawti/je-dev-skills`.

Key real signatures you will compose with (do NOT modify these files — they are the frozen CORE):

- `evals/evaluator/report.py`:
  - `summarize(results: list[dict]) -> dict` → `{"total", "average_score", "passed", "pass_rate"}`. Reads `r["score"]` from each result and compares to `config.PASS_THRESHOLD`.
  - `write_json(path: str | Path, results: list[dict], summary: dict, meta: dict) -> None` → writes `{"meta", "summary", "results"}`.
  - `write_html(path: str | Path, results: list[dict], summary: dict, meta: dict) -> None`. Reads `r["test_case"]` (`scenario`, `prompt_inputs`, `solution_criteria`), `r["output"]`, `r["score"]`, `r["reasoning"]`, and `meta` keys (`task_description`, `dataset_file`, `judge_model`, `run_label`).
- `evals/evaluator/schemas.py`:
  - `validate_verdict(verdict: dict) -> dict` → raises `ValueError` if not a dict or missing numeric `score`; clamps `score` to int 1-10; `setdefault`s `reasoning=""`, `strengths=[]`, `weaknesses=[]`.
  - `verdict_schema() -> dict` (the closed-key shape: `strengths`, `weaknesses`, `reasoning`, `score`).
- `evals/evaluator/templates.py`:
  - `render(template: str, /, **values: object) -> str` → `{name}` substitution, `{{`/`}}` literal-brace escaping, **raises `KeyError`** on a missing placeholder, **ignores extra values**.
- `evals/evaluator/evaluator.py`:
  - `PromptEvaluator.run_evaluation(*, run_function, dataset_file, extra_criteria=None, process_criteria=None, runs_dir=config.RUNS_DIR, run_label=None) -> {"summary", "run_dir", "results"}`. Already accepts `run_label` and returns `run_dir`.
- The per-case **result** shape produced by `run_evaluation` (and what `report.py` consumes): each result dict is
  `{"output": str, "trajectory": {...}, "test_case": {...}, "score": int, "reasoning": str, "verdict": {strengths, weaknesses, reasoning, score}}`.

CORE-import rule (composition invariant): `summarize`, `write_json`, `write_html` are NOT re-exported from `evals/evaluator/__init__.py` (which exports only `PromptEvaluator`, `AnthropicClient`, `LLMClient`, `Trajectory`, `Step`). Therefore the new code imports them by submodule path: `from evals.evaluator.report import summarize, write_json, write_html` and `from evals.evaluator.schemas import validate_verdict`.

The deterministic-and-tested exemplar to mirror for style: `skills/workflow-design-validate/scripts/validate_blueprint.py` + `skills/workflow-design-validate/scripts/tests/test_cli.py` (argparse CLI, exit codes 0/1/2, `unittest` with a `fixtures/` dir, importing the module directly).

---

## File Structure (created / modified)

**Framework SOURCE (under `skills/prompt-evals-setup/framework/evals/`):**

| Path | New/Changed | Responsibility |
|---|---|---|
| `config.py` | CHANGED | Add `EXECUTION_MODE: str = "in_claude_code"` (other value `"anthropic_api"`) + subagent dispatch knobs (`SUBAGENT_EXECUTOR_MODEL`, `SUBAGENT_JUDGE_MODEL`, `SUBAGENT_EFFORT`). |
| `aggregate.py` | NEW (top level, beside `run_eval.py`, NOT in `evaluator/`) | Deterministic, NO-model report assembler for the no-key Path A. CLI reads per-case verdict JSONs, validates each via `validate_verdict`, writes `runs/<label>/{output.json,output.html}` via the frozen `report.py` writers. Prints the run_dir. |
| `promptprep.py` | NEW (top level, beside `run_eval.py`, NOT in `evaluator/`) | `check_placeholders(template, prompt_inputs) -> {declared, unused, missing}`; raises on missing, logs a WARNING on unused, never auto-syncs. Reuses `render`. |
| `run_eval.py` | CHANGED | File-backed `<name>.current.md` default; `run_prompt` renders via `render()` + `check_placeholders`; mode-aware `main()` (under `in_claude_code` `evaluate` prints guidance + exits non-zero; keyed `run_evaluation` runs only under `anthropic_api`, threading `run_label`); `run_label` accepted as a CLI arg. |
| `tests/test_aggregate.py` | NEW | Offline `unittest` for `aggregate.py`: validates good verdict JSONs → correct `output.json`/`output.html`, no API key/model call; handles invalid verdict; deterministic run_dir from `run_label`. |
| `tests/test_promptprep.py` | NEW | Offline `unittest` for `check_placeholders`: declared/unused/missing report; raises on missing; warns on unused. |
| `tests/fixtures/verdicts_ok/` (3 JSON files) | NEW | Per-case verdict fixtures for `test_aggregate.py`. |
| `tests/fixtures/verdicts_bad/` (1 JSON file) | NEW | A malformed verdict fixture (missing numeric score) for the error path. |

**Skills:**

| Path | Changed | Responsibility |
|---|---|---|
| `skills/prompt-evals-run/SKILL.md` | CHANGED | Run procedure rewritten to Path A (no-key, skill dispatches execute+grade subagents per case → writes per-case verdict JSONs → calls `aggregate.py`); Path B (keyed `EXECUTION_MODE=anthropic_api`) documented as fallback. (NOTE: the §4 "Diagnose and iterate" single-pass re-scope + `diagnosis.md` citation is owned by the prompt-engineering-improve plan; THIS plan owns only the run-procedure rewrite — leave the diagnose step's wording for the other plan, but do not break it.) |
| `skills/prompt-evals-setup/SKILL.md` | CHANGED | Vendoring step lists `aggregate.py` + `promptprep.py` in the verify tree; add a non-clobbering re-setup note that adds the new substrate files (`aggregate.py`, `promptprep.py`, updated `config.py`/`run_eval.py`) to an existing `./evals` without overwriting user edits. |

**Out of scope for THIS plan** (owned by sibling plans, per the shared interface contract): `improve_step.py` and the loop-param constants block, the `prompt-engineering-*` skills, `agent-build-*`, `README.md`/`plugin.json` wiring, `docs/WORKFLOW_DESIGN_SPEC.md`. Do not touch the framework CORE (`evaluator/*.py`, `prompts/`).

---

## Conventions for every task

- Work from repo root `/home/dawti/je-dev-skills`. All paths below are absolute.
- Run offline tests with the framework dir as the import root so `from evals... import` resolves:
  `cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest <module> -v`
- After each task's test passes, commit. You are on branch `prompt-engineering-skills` (not the default branch), so commit directly here.
- Commit message footer (verbatim, last line):
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 1 — Add `EXECUTION_MODE` + subagent knobs to `config.py`

Pure constant additions. The "test" is a structural import check (config is data, not logic).

- [ ] **Step 1.1 — Write the failing structural check.** Run this exact command and expect it to FAIL (the attribute does not exist yet):

  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
  python3 -c "from evals import config; assert config.EXECUTION_MODE == 'in_claude_code'; print('OK')"
  ```

  Expected output (FAIL):
  ```
  AttributeError: module 'evals.config' has no attribute 'EXECUTION_MODE'
  ```

- [ ] **Step 1.2 — Add the constants.** Edit `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/config.py`. Insert the following block immediately after the `API_KEY_ENV = "ANTHROPIC_API_KEY"` line (line 23) and its trailing blank line, before the `# Max output tokens...` comment:

  ```python
  # --- Execution mode ----------------------------------------------------------
  # How the prompt-under-test is run + graded.
  #   "in_claude_code" (default): the no-API-key path. The prompt-evals-run skill,
  #       driven by an interactive Claude Code session, dispatches an execute- and a
  #       grade-subagent per case (session auth, NO ANTHROPIC_API_KEY), writes one
  #       verdict JSON per case, then calls `python -m evals.aggregate` to assemble
  #       the report. run_eval.py's `evaluate` command does NOT run the in-process
  #       loop in this mode (a synchronous Python function cannot dispatch a subagent).
  #   "anthropic_api": the keyed headless/CI fallback. run_eval.py's `evaluate`
  #       command runs PromptEvaluator.run_evaluation in-process with AnthropicClient
  #       for executor AND judge. Requires ANTHROPIC_API_KEY; supports agentic Trajectory.
  EXECUTION_MODE = "in_claude_code"

  # Subagent dispatch knobs the no-key Path A uses (the skill reads these; they have
  # no effect on the keyed path, which uses EXECUTOR_MODEL/JUDGE_MODEL above).
  SUBAGENT_EXECUTOR_MODEL = "claude-haiku-4-5-20251001"  # runs the prompt-under-test
  SUBAGENT_JUDGE_MODEL = "claude-opus-4-8"               # grades the output (strong, distinct)
  SUBAGENT_EFFORT = "medium"                              # reasoning effort for the subagents
  ```

- [ ] **Step 1.3 — Run the check (expect PASS).** Re-run the command from Step 1.1. Expected output:
  ```
  OK
  ```

- [ ] **Step 1.4 — Guard the existing tests still pass.** Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t . 2>&1 | tail -3
  ```
  Expected last lines:
  ```
  Ran 33 tests in 0.00Xs

  OK
  ```

- [ ] **Step 1.5 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/config.py && \
  git commit -m "$(printf 'Add EXECUTION_MODE + subagent knobs to eval config\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 2 — `check_placeholders` prompt-prep glue (`promptprep.py`) — TDD

A deterministic helper in the vendored `evals/` top level. Reuses `render`. Returns `{declared, unused, missing}`. Raises on missing (KeyError-like); logs a WARNING on unused; never auto-syncs.

- [ ] **Step 2.1 — Write the failing test.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/test_promptprep.py` with EXACTLY this content:

  ```python
  """Offline tests for the prompt-prep glue (evals/promptprep.py). No API key."""

  import logging
  import unittest

  from evals.promptprep import MissingPlaceholderError, check_placeholders


  class TestCheckPlaceholders(unittest.TestCase):
      def test_all_declared_and_used(self):
          report = check_placeholders("Hi {name}, age {age}", {"name": "Ada", "age": "30"})
          self.assertEqual(sorted(report["declared"]), ["age", "name"])
          self.assertEqual(report["unused"], [])
          self.assertEqual(report["missing"], [])

      def test_literal_braces_are_not_placeholders(self):
          # {{ }} escapes are literal braces, not declared placeholders.
          report = check_placeholders('Use {{"k": {v}}}', {"v": "1"})
          self.assertEqual(report["declared"], ["v"])
          self.assertEqual(report["unused"], [])
          self.assertEqual(report["missing"], [])

      def test_repeated_placeholder_reported_once(self):
          report = check_placeholders("{a}-{a}-{b}", {"a": "1", "b": "2"})
          self.assertEqual(sorted(report["declared"]), ["a", "b"])

      def test_unused_input_warns_but_does_not_raise(self):
          with self.assertLogs("evals.promptprep", level="WARNING") as cm:
              report = check_placeholders("Hi {name}", {"name": "Ada", "spurious": "x"})
          self.assertEqual(report["unused"], ["spurious"])
          self.assertEqual(report["missing"], [])
          self.assertTrue(any("spurious" in line for line in cm.output))

      def test_missing_placeholder_raises(self):
          with self.assertRaises(MissingPlaceholderError) as ctx:
              check_placeholders("Hi {name}, you are {role}", {"name": "Ada"})
          self.assertIn("role", str(ctx.exception))

      def test_missing_reported_before_render_keyerror(self):
          # The structured report must surface ALL missing keys, not just the first
          # one render() would raise on.
          try:
              check_placeholders("{a} {b} {c}", {"a": "1"})
              self.fail("expected MissingPlaceholderError")
          except MissingPlaceholderError as exc:
              self.assertIn("b", str(exc))
              self.assertIn("c", str(exc))

      def test_no_auto_sync_return_is_pure_report(self):
          # The helper never mutates prompt_inputs.
          inputs = {"name": "Ada", "extra": "y"}
          with self.assertLogs("evals.promptprep", level="WARNING"):
              check_placeholders("{name}", inputs)
          self.assertEqual(inputs, {"name": "Ada", "extra": "y"})


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2.2 — Run it (expect FAIL: import error).**
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_promptprep -v 2>&1 | tail -5
  ```
  Expected (FAIL):
  ```
  ModuleNotFoundError: No module named 'evals.promptprep'
  ```

- [ ] **Step 2.3 — Implement `promptprep.py`.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/promptprep.py` with EXACTLY this content:

  ```python
  """Deterministic prompt-prep glue (vendored evals/ top level — NOT in evaluator/).

  Pairs with the framework's render() to check a prompt template's {placeholders}
  against a case's prompt_inputs BEFORE rendering:
    - FAILS (raises MissingPlaceholderError) on any placeholder with no value,
      producing a structured report listing ALL missing keys (render() would only
      raise on the first one it hits).
    - WARNS (logging) on inputs that the template never references — so a human can
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
  # doubled brace ({{ or }}) is a literal brace, NOT a placeholder.
  _IDENT = r"[a-zA-Z_][a-zA-Z0-9_]*"
  _PLACEHOLDER = re.compile(r"(?<!\{)\{(" + _IDENT + r")\}(?!\})")


  class MissingPlaceholderError(KeyError):
      """A template placeholder has no matching value in prompt_inputs."""


  def declared_placeholders(template: str) -> list[str]:
      """Return the unique {placeholder} names in declaration order.

      Literal {{/}} braces are stripped first so they are never read as placeholders.
      """
      stripped = template.replace("{{", "\x00").replace("}}", "\x01")
      seen: list[str] = []
      for match in _PLACEHOLDER.finditer(stripped):
          name = match.group(1)
          if name not in seen:
              seen.append(name)
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
  ```

- [ ] **Step 2.4 — Run it (expect PASS).**
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_promptprep -v 2>&1 | tail -4
  ```
  Expected:
  ```
  Ran 7 tests in 0.00Xs

  OK
  ```

- [ ] **Step 2.5 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/promptprep.py skills/prompt-evals-setup/framework/evals/tests/test_promptprep.py && \
  git commit -m "$(printf 'Add check_placeholders prompt-prep glue + offline tests\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 3 — Verdict fixtures for `aggregate.py`

`aggregate.py` reads per-case verdict JSON files. Each file is one case: `{test_case, verdict, output}`. We create fixtures now so Task 4's test can use them.

- [ ] **Step 3.1 — Create the fixtures dir and three good verdict files.** Run this exact command (it writes the dir + three JSON files; the heredoc body is the literal file content):

  ```bash
  mkdir -p /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_bad
  ```

- [ ] **Step 3.2 — Write `case-00.json`.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok/case-00.json` with EXACTLY this content:

  ```json
  {
    "test_case": {
      "prompt_inputs": {"height": "178 cm", "weight": "82 kg", "goal": "Lose fat"},
      "solution_criteria": ["Provides a 1-day meal plan with a caloric total and macro breakdown."],
      "task_description": "Write a compact 1-day meal plan for one athlete.",
      "scenario": "A wrestler cutting weight the week before a meet"
    },
    "output": "Total: 2,400 kcal | Protein 180g / Carbs 240g / Fat 70g",
    "verdict": {
      "strengths": ["Includes a caloric total and macro breakdown."],
      "weaknesses": ["Per-meal timing could be more specific."],
      "reasoning": "Meets the mandatory structure and the secondary criterion.",
      "score": 8
    }
  }
  ```

- [ ] **Step 3.3 — Write `case-01.json`.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok/case-01.json` with EXACTLY this content:

  ```json
  {
    "test_case": {
      "prompt_inputs": {"height": "165 cm", "weight": "60 kg", "goal": "Peak endurance"},
      "solution_criteria": ["Provides a 1-day meal plan with a caloric total and macro breakdown."],
      "task_description": "Write a compact 1-day meal plan for one athlete.",
      "scenario": "A vegan marathon runner in peak training"
    },
    "output": "Total: 2,800 kcal | Protein 130g / Carbs 420g / Fat 75g",
    "verdict": {
      "strengths": ["Carb-forward and vegan-appropriate."],
      "weaknesses": ["No macro breakdown given."],
      "reasoning": "Fails the mandatory macro-breakdown criterion.",
      "score": 3
    }
  }
  ```

- [ ] **Step 3.4 — Write `case-02.json`.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok/case-02.json` with EXACTLY this content:

  ```json
  {
    "test_case": {
      "prompt_inputs": {"height": "190 cm", "weight": "110 kg", "goal": "Lean bulk"},
      "solution_criteria": ["Provides a 1-day meal plan with a caloric total and macro breakdown."],
      "task_description": "Write a compact 1-day meal plan for one athlete.",
      "scenario": "A powerlifter in a lean bulk"
    },
    "output": "Total: 3,600 kcal | Protein 220g / Carbs 380g / Fat 110g",
    "verdict": {
      "strengths": ["Clear caloric total and full macro breakdown."],
      "weaknesses": [],
      "reasoning": "Fully satisfies every criterion.",
      "score": 9
    }
  }
  ```

- [ ] **Step 3.5 — Write the bad fixture `bad-missing-score.json`.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_bad/bad-missing-score.json` with EXACTLY this content (no numeric `score` → `validate_verdict` must raise):

  ```json
  {
    "test_case": {
      "prompt_inputs": {"height": "170 cm", "weight": "70 kg", "goal": "Maintain"},
      "solution_criteria": ["Provides a 1-day meal plan with a caloric total and macro breakdown."],
      "task_description": "Write a compact 1-day meal plan for one athlete.",
      "scenario": "A recreational cyclist maintaining weight"
    },
    "output": "Eat well and train hard.",
    "verdict": {
      "strengths": [],
      "weaknesses": ["No plan, no numbers."],
      "reasoning": "Non-answer."
    }
  }
  ```

- [ ] **Step 3.6 — Verify the JSON parses.** Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
  python3 -c "import json,glob; [json.load(open(p)) for p in glob.glob('evals/tests/fixtures/verdicts_*/*.json')]; print('all-parse-OK')"
  ```
  Expected:
  ```
  all-parse-OK
  ```

- [ ] **Step 3.7 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/tests/fixtures && \
  git commit -m "$(printf 'Add verdict JSON fixtures for aggregate.py tests\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 4 — `aggregate.py` deterministic no-model report assembler — TDD

The headline new artifact. CLI: `python -m evals.aggregate --run-label <label> --verdicts-dir <dir> --dataset <path>`. Reads the per-case verdict JSONs (sorted by filename for determinism), validates each `verdict` via `validate_verdict`, builds the framework's `results` shape, then writes `runs/<label>/{output.json,output.html}` via `report.py`. Returns/prints the run_dir. NO model calls, no API key.

The `--dataset` arg supplies report `meta` (`task_description`, `dataset_file`) deterministically; the helper does not need the dataset to compute scores. It is optional — if omitted, meta falls back to values harvested from the first verdict's `test_case`.

- [ ] **Step 4.1 — Write the failing test.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py` with EXACTLY this content:

  ```python
  """Offline tests for evals/aggregate.py — the no-model report assembler. No API key."""

  import json
  import os
  import tempfile
  import unittest
  from pathlib import Path

  from evals import aggregate

  FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
  VERDICTS_OK = os.path.join(FIXTURES, "verdicts_ok")
  VERDICTS_BAD = os.path.join(FIXTURES, "verdicts_bad")


  class TestLoadVerdicts(unittest.TestCase):
      def test_load_sorts_by_filename_and_builds_results(self):
          results = aggregate.load_results(VERDICTS_OK)
          # 3 fixtures, in filename order case-00, case-01, case-02.
          self.assertEqual(len(results), 3)
          self.assertEqual([r["score"] for r in results], [8, 3, 9])
          first = results[0]
          self.assertEqual(set(first.keys()) >= {"output", "test_case", "score", "reasoning", "verdict"}, True)
          self.assertEqual(first["reasoning"], first["verdict"]["reasoning"])

      def test_bad_verdict_raises(self):
          with self.assertRaises(ValueError):
              aggregate.load_results(VERDICTS_BAD)


  class TestAggregateWritesReport(unittest.TestCase):
      def test_writes_output_json_and_html_to_run_dir(self):
          with tempfile.TemporaryDirectory() as d:
              runs_dir = Path(d) / "runs"
              run_dir = aggregate.aggregate(
                  run_label="improve-meal-round-00",
                  verdicts_dir=VERDICTS_OK,
                  dataset=None,
                  runs_dir=str(runs_dir),
              )
              self.assertEqual(Path(run_dir), runs_dir / "improve-meal-round-00")
              out_json = Path(run_dir) / "output.json"
              out_html = Path(run_dir) / "output.html"
              self.assertTrue(out_json.exists())
              self.assertTrue(out_html.exists())
              data = json.loads(out_json.read_text())
              self.assertEqual(set(data.keys()), {"meta", "summary", "results"})
              # summarize(): scores [8,3,9], PASS_THRESHOLD 7 -> 2 pass of 3.
              self.assertEqual(data["summary"]["total"], 3)
              self.assertEqual(data["summary"]["passed"], 2)
              self.assertEqual(data["meta"]["run_label"], "improve-meal-round-00")
              # HTML is escaped + self-contained.
              html = out_html.read_text()
              self.assertIn("Average score", html)

      def test_dataset_meta_overrides_when_provided(self):
          with tempfile.TemporaryDirectory() as d:
              dataset_path = Path(d) / "ds.json"
              dataset_path.write_text(json.dumps({
                  "provenance": {"task_description": "DS TASK", "prompt_inputs_spec": {}},
                  "cases": [],
              }))
              run_dir = aggregate.aggregate(
                  run_label="r1",
                  verdicts_dir=VERDICTS_OK,
                  dataset=str(dataset_path),
                  runs_dir=str(Path(d) / "runs"),
              )
              data = json.loads((Path(run_dir) / "output.json").read_text())
              self.assertEqual(data["meta"]["task_description"], "DS TASK")
              self.assertEqual(data["meta"]["dataset_file"], str(dataset_path))


  class TestCli(unittest.TestCase):
      def test_main_returns_zero_and_prints_run_dir(self):
          import io
          import contextlib
          with tempfile.TemporaryDirectory() as d:
              buf = io.StringIO()
              with contextlib.redirect_stdout(buf):
                  rc = aggregate.main([
                      "--run-label", "cli-run",
                      "--verdicts-dir", VERDICTS_OK,
                      "--runs-dir", str(Path(d) / "runs"),
                  ])
              self.assertEqual(rc, 0)
              self.assertIn("cli-run", buf.getvalue())
              self.assertTrue((Path(d) / "runs" / "cli-run" / "output.json").exists())

      def test_main_returns_two_on_empty_verdicts_dir(self):
          with tempfile.TemporaryDirectory() as d:
              empty = Path(d) / "empty"
              empty.mkdir()
              rc = aggregate.main([
                  "--run-label", "x",
                  "--verdicts-dir", str(empty),
                  "--runs-dir", str(Path(d) / "runs"),
              ])
              self.assertEqual(rc, 2)


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 4.2 — Run it (expect FAIL: import error).**
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_aggregate -v 2>&1 | tail -5
  ```
  Expected (FAIL):
  ```
  ModuleNotFoundError: No module named 'evals.aggregate'
  ```

- [ ] **Step 4.3 — Implement `aggregate.py`.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/aggregate.py` with EXACTLY this content:

  ```python
  """Deterministic, NO-model report assembler for the no-key Path A.

  Vendored at the evals/ top level (beside run_eval.py) — NOT in evaluator/, which is
  the frozen framework CORE. Run as a CLI by the prompt-evals-run skill AFTER it has
  dispatched an execute- and a grade-subagent per case (session auth, no API key) and
  written one verdict JSON per case:

      python -m evals.aggregate --run-label improve-meal-round-00 \
          --verdicts-dir evals/runs/_verdicts/improve-meal-round-00 \
          --dataset evals/datasets/meal_plan.json

  It reads the per-case verdict JSON files (sorted by filename for determinism),
  validates each verdict via the frozen schemas.validate_verdict, builds the
  framework's standard `results` shape, and writes runs/<label>/{output.json,output.html}
  via the frozen report.py writers. It prints (and returns) the run_dir. No model call.

  Per-case verdict JSON file shape (what the grade-subagent emits, written by the skill):
      {
        "test_case": {... the dataset case: prompt_inputs, solution_criteria,
                      task_description, scenario ...},
        "output":   "<the execute-subagent's raw output string>",
        "verdict":  {"strengths": [...], "weaknesses": [...], "reasoning": "...",
                     "score": <int 1-10>}
      }
  """

  import argparse
  import json
  import sys
  from pathlib import Path

  from evals import config
  from evals.evaluator.report import summarize, write_html, write_json
  from evals.evaluator.schemas import validate_verdict


  def _read_verdict_files(verdicts_dir: str | Path) -> list[Path]:
      """Return the per-case JSON files in deterministic (filename-sorted) order."""
      d = Path(verdicts_dir)
      return sorted(d.glob("*.json"), key=lambda p: p.name)


  def load_results(verdicts_dir: str | Path) -> list[dict]:
      """Load + validate every per-case verdict JSON into the framework result shape.

      Raises FileNotFoundError if the dir has no .json files; ValueError (from
      validate_verdict) if any verdict is malformed.
      """
      files = _read_verdict_files(verdicts_dir)
      if not files:
          raise FileNotFoundError(f"no verdict JSON files in {verdicts_dir}")

      results: list[dict] = []
      for path in files:
          record = json.loads(path.read_text(encoding="utf-8"))
          verdict = validate_verdict(record["verdict"])  # raises on bad/missing score
          test_case = record["test_case"]
          output = record.get("output", "")
          results.append(
              {
                  "output": output,
                  "trajectory": {"final_output": output, "steps": []},
                  "test_case": test_case,
                  "score": verdict["score"],
                  "reasoning": verdict.get("reasoning", ""),
                  "verdict": verdict,
              }
          )
      return results


  def _build_meta(
      run_label: str, dataset: str | None, results: list[dict]
  ) -> dict:
      """Assemble report meta. Prefer the dataset's provenance; else harvest from the
      first verdict's test_case."""
      task_description = ""
      dataset_file = dataset or ""
      if dataset:
          provenance = json.loads(Path(dataset).read_text(encoding="utf-8")).get(
              "provenance", {}
          )
          task_description = provenance.get("task_description", "")
      elif results:
          task_description = results[0]["test_case"].get("task_description", "")
      return {
          "task_description": task_description,
          "dataset_file": dataset_file,
          "judge_model": config.SUBAGENT_JUDGE_MODEL,
          "run_label": run_label,
          "extra_criteria": None,
      }


  def aggregate(
      *,
      run_label: str,
      verdicts_dir: str | Path,
      dataset: str | None = None,
      runs_dir: str = config.RUNS_DIR,
  ) -> str:
      """Assemble runs/<run_label>/{output.json,output.html}. Returns the run_dir path."""
      results = load_results(verdicts_dir)
      summary = summarize(results)
      meta = _build_meta(run_label, dataset, results)

      out_dir = Path(runs_dir) / run_label
      out_dir.mkdir(parents=True, exist_ok=True)
      write_json(out_dir / "output.json", results, summary, meta)
      write_html(out_dir / "output.html", results, summary, meta)
      return str(out_dir)


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(
          description="Assemble a prompt-eval report from per-case verdict JSONs (no model)."
      )
      parser.add_argument("--run-label", required=True, help="names runs/<label>/")
      parser.add_argument(
          "--verdicts-dir", required=True, help="dir of per-case verdict JSON files"
      )
      parser.add_argument(
          "--dataset", default=None, help="optional dataset JSON for report meta"
      )
      parser.add_argument(
          "--runs-dir", default=config.RUNS_DIR, help="base runs dir (default config.RUNS_DIR)"
      )
      args = parser.parse_args(argv)
      try:
          run_dir = aggregate(
              run_label=args.run_label,
              verdicts_dir=args.verdicts_dir,
              dataset=args.dataset,
              runs_dir=args.runs_dir,
          )
      except (OSError, FileNotFoundError) as exc:
          print(f"ERROR: {exc}")
          return 2
      except (ValueError, KeyError) as exc:
          print(f"ERROR: invalid verdict data: {exc}")
          return 1
      print(run_dir)
      return 0


  if __name__ == "__main__":
      sys.exit(main())
  ```

  Note: the empty-dir path raises `FileNotFoundError`, which `main` catches → returns 2 (matching `test_main_returns_two_on_empty_verdicts_dir`). A malformed verdict raises `ValueError` from `validate_verdict` → `load_results` (test `test_bad_verdict_raises`) and → `main` returns 1.

- [ ] **Step 4.4 — Run it (expect PASS).**
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest evals.tests.test_aggregate -v 2>&1 | tail -4
  ```
  Expected:
  ```
  Ran 6 tests in 0.0XXs

  OK
  ```

- [ ] **Step 4.5 — Smoke the CLI end-to-end (real invocation, no API key).** Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
  rm -rf /tmp/agg_smoke && python3 -m evals.aggregate \
    --run-label smoke-agg \
    --verdicts-dir evals/tests/fixtures/verdicts_ok \
    --runs-dir /tmp/agg_smoke && \
  python3 -c "import json; d=json.load(open('/tmp/agg_smoke/smoke-agg/output.json')); print('avg', d['summary']['average_score'], 'pass', d['summary']['pass_rate'])"
  ```
  Expected output (the printed run_dir then the summary; avg of [8,3,9]=6.67, pass-rate 2/3=66.7):
  ```
  /tmp/agg_smoke/smoke-agg
  avg 6.67 pass 66.7
  ```

- [ ] **Step 4.6 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/aggregate.py skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py && \
  git commit -m "$(printf 'Add deterministic no-model aggregate.py report assembler + tests\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 5 — Make `run_eval.py` file-backed, render-based, and mode-aware

Rewrite `run_eval.py` so:
1. The prompt-under-test loads from a file `evals/prompts_under_test/<name>.current.md` (default), rendered with `render()` + `check_placeholders` (Layer-2 glue) — demonstrating the file-backed default the spec mandates.
2. `main()` is mode-aware: under `EXECUTION_MODE=in_claude_code` (default) the `evaluate` command does NOT call `run_evaluation` — it prints guidance pointing at the `prompt-evals-run` skill + `aggregate.py` and exits non-zero; the keyed `run_evaluation` runs only under `anthropic_api`, threading `run_label`.
3. `run_label` is accepted as an optional CLI arg.

Because `run_eval.py` is the per-project editable template (not CORE), its "test" is a structural/scenario check: a mode-routing smoke that needs no API key.

- [ ] **Step 5.1 — Create the default prompt file the new template references.** Create `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/prompts_under_test/meal_plan.current.md` with EXACTLY this content (placeholders match `PROMPT_INPUTS_SPEC`):

  ```text
  Write a compact 1-day meal plan for one athlete.

  Height: {height}
  Weight: {weight}
  Goal: {goal}

  Include a caloric total and a macro breakdown (protein / carbs / fat).
  ```

- [ ] **Step 5.2 — Rewrite `run_eval.py`.** Overwrite `/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals/run_eval.py` with EXACTLY this content:

  ```python
  """Real entrypoint: generate a dataset once, then evaluate against it.

  Two execution modes, selected by config.EXECUTION_MODE:

    "in_claude_code" (default, NO API key): measurement is driven by the
        prompt-evals-run skill (it dispatches an execute- and a grade-subagent per
        case, writes per-case verdict JSONs, then runs `python -m evals.aggregate`).
        A synchronous Python function cannot dispatch a subagent, so the `evaluate`
        command here prints that guidance and exits non-zero in this mode.

    "anthropic_api" (keyed headless/CI fallback): the `evaluate` command runs
        PromptEvaluator.run_evaluation in-process with AnthropicClient. Requires
        ANTHROPIC_API_KEY (name in config.API_KEY_ENV) and supports agentic Trajectory.

  Prerequisites for the keyed path:
      pip install -r evals/requirements.txt
      export ANTHROPIC_API_KEY=sk-...

  Usage:
      python -m evals.run_eval generate                 # build + freeze the dataset (one-time)
      python -m evals.run_eval evaluate [run_label]     # keyed-mode only; see EXECUTION_MODE

  Copy this file per project and edit TASK / PROMPT_INPUTS_SPEC / the prompt file /
  EXTRA_CRITERIA. The prompt TEXT is a file (PROMPT_FILE), not a Python string.
  """

  import sys
  from pathlib import Path

  from evals import config
  from evals.evaluator import AnthropicClient, PromptEvaluator
  from evals.evaluator.templates import render
  from evals.promptprep import check_placeholders

  # --- 1. Describe the task and its closed input set ---------------------------
  TASK = "Write a compact 1-day meal plan for one athlete."
  PROMPT_INPUTS_SPEC = {
      "height": "Athlete's height in cm",
      "weight": "Athlete's weight in kg",
      "goal": "Goal of the athlete",
  }
  EXTRA_CRITERIA = "Must include a caloric total and a macro breakdown (protein/carbs/fat)."
  # Agentic-only: how the agent should behave (tools, recovery, no needless steps).
  # Leave None for single-shot prompts. Wired through to grading in main() below.
  PROCESS_CRITERIA = None
  DATASET_FILE = f"{config.DATASETS_DIR}/meal_plan.json"
  NUM_CASES = 20

  # The active prompt is a FILE (Layer 1), not a Python string. Each round writes a
  # candidate <name>.vN.md; the chosen candidate is copied into <name>.current.md
  # before measuring. run_prompt always renders <name>.current.md.
  PROMPT_FILE = f"{config.DATASETS_DIR}/../prompts_under_test/meal_plan.current.md"


  # --- 2. Define the prompt under test (KEYED PATH ONLY) -----------------------
  def run_prompt(prompt_inputs: dict) -> str:
      """Render the file-backed prompt with the case inputs, call the model, return text.

      Used ONLY on the keyed path (EXECUTION_MODE=anthropic_api). The no-key path
      runs the prompt by subagent dispatch from the prompt-evals-run skill instead.

      For an AGENTIC system, return a Trajectory (see evals.evaluator.Trajectory).
      """
      template = Path(PROMPT_FILE).read_text(encoding="utf-8")
      # Layer-2 glue: fail on a missing placeholder, warn on an unused input, before
      # render()'s own KeyError backstop fires.
      check_placeholders(template, prompt_inputs)
      prompt = render(template, **prompt_inputs)

      executor = AnthropicClient(config.EXECUTOR_MODEL)
      resp = executor._client.messages.create(  # noqa: SLF001 (example convenience)
          model=executor.model,
          max_tokens=600,
          messages=[{"role": "user", "content": prompt}],
      )
      return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


  def build_evaluator() -> PromptEvaluator:
      return PromptEvaluator(
          client=AnthropicClient(config.GENERATOR_MODEL),
          judge_client=AnthropicClient(config.JUDGE_MODEL),
          max_concurrent_tasks=config.MAX_CONCURRENT_TASKS,
      )


  _IN_CC_GUIDANCE = (
      "EXECUTION_MODE=in_claude_code: 'evaluate' does not run in-process here.\n"
      "A synchronous Python function cannot dispatch a subagent. Run the eval via the\n"
      "prompt-evals-run skill, which dispatches an execute- and grade-subagent per case\n"
      "(session auth, no API key), writes per-case verdict JSONs, then assembles the\n"
      "report with:\n"
      "    python -m evals.aggregate --run-label <label> --verdicts-dir <dir> --dataset "
      f"{DATASET_FILE}\n"
      "To run the keyed in-process loop instead, set EXECUTION_MODE='anthropic_api' in\n"
      "evals/config.py and export your API key."
  )


  def main(argv: list[str]) -> int:
      command = argv[1] if len(argv) > 1 else "evaluate"

      if command == "generate":
          build_evaluator().generate_dataset(
              task_description=TASK,
              prompt_inputs_spec=PROMPT_INPUTS_SPEC,
              num_cases=NUM_CASES,
              output_file=DATASET_FILE,
          )
          return 0

      if command == "evaluate":
          if config.EXECUTION_MODE != "anthropic_api":
              print(_IN_CC_GUIDANCE)
              return 3  # non-zero: not an error, but no in-process run happened
          run_label = argv[2] if len(argv) > 2 else None
          build_evaluator().run_evaluation(
              run_function=run_prompt,
              dataset_file=DATASET_FILE,
              extra_criteria=EXTRA_CRITERIA,
              process_criteria=PROCESS_CRITERIA,
              run_label=run_label,
          )
          return 0

      print(f"unknown command: {command!r} (use 'generate' or 'evaluate')")
      return 2


  if __name__ == "__main__":
      sys.exit(main(sys.argv))
  ```

- [ ] **Step 5.3 — Scenario check: in_claude_code mode prints guidance + exits 3.** With the default `EXECUTION_MODE=in_claude_code`, run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && \
  python3 -m evals.run_eval evaluate; echo "exit=$?"
  ```
  Expected output (the guidance block, then):
  ```
  EXECUTION_MODE=in_claude_code: 'evaluate' does not run in-process here.
  ...
  exit=3
  ```

- [ ] **Step 5.4 — Scenario check: render + check_placeholders wiring is importable and correct.** This proves `run_prompt`'s Layer-2 glue works without an API key (we stop before the model call). Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -c "
  from pathlib import Path
  from evals import run_eval
  from evals.evaluator.templates import render
  from evals.promptprep import check_placeholders
  t = Path(run_eval.PROMPT_FILE).read_text()
  rep = check_placeholders(t, {'height':'178 cm','weight':'82 kg','goal':'Lose fat'})
  assert sorted(rep['declared']) == ['goal','height','weight'], rep
  out = render(t, height='178 cm', weight='82 kg', goal='Lose fat')
  assert 'Height: 178 cm' in out and '{height}' not in out
  print('glue-OK')
  "
  ```
  Expected:
  ```
  glue-OK
  ```

- [ ] **Step 5.5 — Scenario check: unknown command exits 2.** Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m evals.run_eval frobnicate; echo "exit=$?"
  ```
  Expected:
  ```
  unknown command: 'frobnicate' (use 'generate' or 'evaluate')
  exit=2
  ```

- [ ] **Step 5.6 — Guard: full offline suite still green.** Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t . 2>&1 | tail -3
  ```
  Expected:
  ```
  Ran 46 tests in 0.0XXs

  OK
  ```
  (33 original + 7 promptprep + 6 aggregate = 46.)

- [ ] **Step 5.7 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/framework/evals/run_eval.py skills/prompt-evals-setup/framework/evals/prompts_under_test/meal_plan.current.md && \
  git commit -m "$(printf 'Make run_eval.py file-backed, render-based, and mode-aware\n\nThread run_label through evaluate; gate in-process loop behind anthropic_api.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 6 — Rewrite `prompt-evals-run/SKILL.md` run procedure to Path A

Rewrite the "Procedure" so the canonical path is the no-key Path A (skill dispatches execute+grade subagents per case → writes per-case verdict JSONs → calls `aggregate.py`), with Path B (keyed) as the documented fallback. Keep the Preconditions, Definition of done, and Offline check sections coherent. Do NOT touch the diagnose-step wording beyond what is needed to keep it valid — the single-pass re-scope + `diagnosis.md` citation belongs to the sibling prompt-engineering-improve plan.

The "test" for a prose SKILL is a structural grep for required sections + a documented manual scenario.

- [ ] **Step 6.1 — Rewrite the file.** Overwrite `/home/dawti/je-dev-skills/skills/prompt-evals-run/SKILL.md` with EXACTLY this content:

  ```markdown
  ---
  name: prompt-evals-run
  description: This skill should be used when the user asks to "run a prompt eval", "evaluate my prompt", "grade prompt outputs", "score my agent", "run the evals", "check my prompt against the dataset", or wants to execute and interpret an LLM-graded evaluation. It wires the prompt/agent under test, runs the project's ./evals pipeline against a frozen dataset, and interprets the report.
  argument-hint: "[dataset name to evaluate against, e.g. meal-plan]"
  allowed-tools: Bash, Read, Write, Edit, Glob, Task
  version: 0.2.0
  ---

  # Run a prompt eval

  Execute the system under test against a frozen dataset and grade every output with
  the LLM judge (run + grade), then interpret the scored report. Re-run this against
  the **same** dataset for each prompt revision to compare versions apples-to-apples.

  There are **two execution paths**, selected by `EXECUTION_MODE` in `evals/config.py`:

  - **Path A — no API key (canonical, `EXECUTION_MODE=in_claude_code`, the default).**
    This skill, driven by the interactive Claude Code session, dispatches subagents to
    run and grade each case (session auth, **no `ANTHROPIC_API_KEY`**), then a
    deterministic helper (`evals/aggregate.py`) assembles the report. **Single-shot
    prompts only** — a subagent cannot dispatch its own subagents (no nesting).
  - **Path B — keyed fallback (`EXECUTION_MODE=anthropic_api`).** The in-process
    `run_eval.py evaluate` loop with the Anthropic SDK for executor and judge.
    Requires the API key; supports agentic `Trajectory`; for headless/CI runs.

  Framework design: `${CLAUDE_PLUGIN_ROOT}/docs/PROMPT_EVAL_FRAMEWORK_SPEC.md`.

  ## Preconditions

  - `./evals` exists (else run `/je-dev-skills:prompt-evals-setup`).
  - A frozen dataset exists in `evals/datasets/` (else run `/je-dev-skills:prompt-evals-create-dataset`).
  - The active prompt is a file at `evals/prompts_under_test/<name>.current.md`
    (the `prompt-engineering-author` output, or hand-written). Its `{placeholder}`
    tokens must match the dataset's `prompt_inputs` keys.

  ## Procedure — Path A (no API key, default)

  ### 1. Confirm the mode and locate the inputs

  ```bash
  python3 -c "from evals import config; print(config.EXECUTION_MODE)"   # expect: in_claude_code
  ls evals/prompts_under_test/*.current.md
  ls evals/datasets/*.json
  ```

  Pick the dataset (the skill argument names it). Choose a `run_label` —
  by convention `improve-<name>-round-NN` when called inside the improve loop, else a
  short slug. Create a fresh per-case verdict directory:

  ```bash
  RUN_LABEL="<label>"
  VERDICTS_DIR="evals/runs/_verdicts/$RUN_LABEL"
  mkdir -p "$VERDICTS_DIR"
  ```

  ### 2. For each case: render, dispatch execute, dispatch grade, write a verdict JSON

  Read the dataset's `cases` array. For **each** case (index `i`):

  1. **Render the prompt deterministically** (no model): substitute the case's
     `prompt_inputs` into `<name>.current.md`. The framework's `render()` does the
     substitution and `check_placeholders` reconciles the keys — both are offline.
     Capture the rendered prompt string.
  2. **Dispatch an execute-subagent** (Task tool, session auth, no key): give it the
     rendered prompt as its full instruction and ask it to return ONLY the prompt's
     raw output. Use the model/effort in `config.SUBAGENT_EXECUTOR_MODEL` /
     `config.SUBAGENT_EFFORT`. This is a single-shot turn — the subagent must not
     dispatch further subagents.
  3. **Dispatch a grade-subagent** (Task tool): give it the case's
     `task_description`, `prompt_inputs`, `solution_criteria`, the global
     `EXTRA_CRITERIA` (from `evals/run_eval.py`), and the execute-subagent's output.
     Instruct it to grade per `${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals/prompts/grading.md`
     and to emit **only** a JSON object with keys `strengths`, `weaknesses`,
     `reasoning`, `score` (integer 1-10) — the `verdict_schema()` shape. Subagent
     frontmatter has no structured-output field, so the JSON discipline is in the
     instruction; the next step validates it.
  4. **Write the per-case verdict JSON** to `$VERDICTS_DIR/case-<i:02d>.json` with
     this exact shape (the skill writes the file):

     ```json
     {
       "test_case": { ...the dataset case verbatim... },
       "output": "<the execute-subagent's raw output>",
       "verdict": { "strengths": [...], "weaknesses": [...], "reasoning": "...", "score": 8 }
     }
     ```

  Do the cases in order so filenames sort deterministically (`case-00`, `case-01`, …).

  ### 3. Assemble the report (deterministic, no model)

  ```bash
  python3 -m evals.aggregate \
    --run-label "$RUN_LABEL" \
    --verdicts-dir "$VERDICTS_DIR" \
    --dataset evals/datasets/<name>.json
  ```

  This validates every verdict (`schemas.validate_verdict`, which clamps the score and
  **raises** on a malformed one), summarizes, and writes
  `evals/runs/$RUN_LABEL/{output.json,output.html}` via the framework's report writers.
  It prints the run directory. If it exits non-zero, a verdict JSON was malformed —
  re-dispatch the offending grade-subagent and re-write that one file.

  ### 4. Read the report

  Open `evals/runs/$RUN_LABEL/output.html`:
  - **Summary:** total cases, average score `/10`, **pass rate** (% scoring ≥ `PASS_THRESHOLD`).
  - **Per-case table:** scenario, inputs, criteria, raw output, color-coded score, judge reasoning.

  `output.json` holds the full record; each result's `verdict` field carries the
  judge's `strengths`/`weaknesses` — the most useful signal for *why* a case scored low.

  ### 5. Diagnose and iterate

  - **Low scores from real output flaws** → fix the prompt and re-run against the
    **same** dataset. Compare `output.json` across runs to confirm improvement, **or
    invoke `/je-dev-skills:prompt-engineering-improve` to automate the loop.**
  - **Low scores from bad criteria** (off-scope, subjective) → the dataset is the
    problem, not the prompt. Fix via `/je-dev-skills:prompt-evals-create-dataset` (audit step).
  - **Mandatory-criterion failures** cap a score at ≤ 3 — check `EXTRA_CRITERIA` first
    when scores cluster low.

  Beware judge/executor leakage: keep `SUBAGENT_JUDGE_MODEL` strong and **distinct**
  from `SUBAGENT_EXECUTOR_MODEL`. For higher confidence on close calls, widen the dataset.

  ## Procedure — Path B (keyed fallback, headless/CI)

  Use when you need an unattended/CI run or agentic `Trajectory` grading.

  1. Set `EXECUTION_MODE = "anthropic_api"` in `evals/config.py`.
  2. Implement/keep `run_prompt` in `evals/run_eval.py` — it renders the file-backed
     `<name>.current.md` (via `render()` + `check_placeholders`) and calls the model.
     For agentic systems return a `Trajectory` (import `from evals.evaluator import
     Trajectory, Step`) and set `PROCESS_CRITERIA` in `run_eval.py`.
  3. Run:

     ```bash
     pip install -r evals/requirements.txt
     export ANTHROPIC_API_KEY=...      # name is in evals/config.py (API_KEY_ENV)
     python3 -m evals.run_eval evaluate <run_label>
     ```

     This makes `2 × num_cases` calls for a single-shot prompt (one execute + one
     grade per case) and writes `evals/runs/<run_label>/{output.json,output.html}`.

  ## Definition of done

  - A run exists at `evals/runs/<run_label>/` with `output.json` + `output.html`.
  - On Path A, one verdict JSON per case was written under `evals/runs/_verdicts/<run_label>/`
    and `aggregate.py` exited 0.
  - The report was interpreted: average score, pass rate, and the main weakness themes
    reported back to the user, with a clear next action (fix prompt vs. fix criteria).

  ## Offline check (no API key)

  `python3 -m evals.aggregate --run-label check --verdicts-dir <a dir of verdict JSONs>`
  assembles a report from already-written verdicts with **no model call** — use it to
  confirm the aggregation wiring. The framework's own pipeline (fake client) is exercised
  by `python3 -m evals.examples.smoke_test`.
  ```

- [ ] **Step 6.2 — Structural check: required sections + Path A wiring present.** Run:
  ```bash
  cd /home/dawti/je-dev-skills && python3 - <<'PY'
  text = open("skills/prompt-evals-run/SKILL.md", encoding="utf-8").read()
  required = [
      "## Procedure — Path A (no API key, default)",
      "## Procedure — Path B (keyed fallback, headless/CI)",
      "python3 -m evals.aggregate",
      "_verdicts/",
      "Task tool",
      "EXECUTION_MODE",
      "## Definition of done",
      "## Offline check (no API key)",
      "allowed-tools: Bash, Read, Write, Edit, Glob, Task",
  ]
  missing = [s for s in required if s not in text]
  assert not missing, f"MISSING: {missing}"
  print("structure-OK")
  PY
  ```
  Expected:
  ```
  structure-OK
  ```

- [ ] **Step 6.3 — Manual scenario (document, do not execute here).** Record in the commit body that the interactive acceptance scenario is: *in a session with no `ANTHROPIC_API_KEY`, the skill renders each case, dispatches execute+grade subagents, writes `case-NN.json` files, and `aggregate.py` produces `output.json`/`output.html`* — this is the manual integration check from architecture-spec §5 (explicitly not unit-testable). The offline portion is already covered by Task 4's `aggregate.py` tests.

- [ ] **Step 6.4 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-run/SKILL.md && \
  git commit -m "$(printf 'Rewrite prompt-evals-run to no-key Path A subagent dispatch\n\nPath A: skill dispatches execute+grade subagents per case, writes per-case\nverdict JSONs, then aggregate.py assembles the report. Path B (keyed) documented\nas the headless/CI fallback. Manual interactive acceptance: no-key session renders\neach case, dispatches subagents, aggregate.py emits the report.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 7 — Update `prompt-evals-setup/SKILL.md` vendoring (ships new files, non-clobbering re-setup)

The vendoring `cp -R` already copies the whole `evals` tree, so `aggregate.py`, `promptprep.py`, the updated `config.py`/`run_eval.py`, and the new tests/fixtures land automatically on a fresh setup. Two doc changes are required: (a) the verify-tree step must mention the new top-level files so a reviewer confirms they landed; (b) a new **non-clobbering re-setup** note that copies ONLY the missing substrate files into an existing `./evals` without overwriting user edits.

The "test" is a structural grep + a real `cp`/file-presence smoke.

- [ ] **Step 7.1 — Add the new files to the verify tree (Step 2 of the setup skill).** Edit `/home/dawti/je-dev-skills/skills/prompt-evals-setup/SKILL.md`. Replace this exact sentence (lines 55-57):

  ```
  Verify the tree landed: `evals/evaluator/`, `evals/prompts/`, `evals/config.py`,
  `evals/run_eval.py`, `evals/tests/`, `evals/examples/`, and the `.gitkeep` dirs
  `evals/datasets/`, `evals/runs/`, and `evals/prompts_under_test/`.
  ```

  with:

  ```
  Verify the tree landed: `evals/evaluator/`, `evals/prompts/`, `evals/config.py`,
  `evals/run_eval.py`, `evals/aggregate.py`, `evals/promptprep.py`, `evals/tests/`,
  `evals/examples/`, and the `.gitkeep` dirs `evals/datasets/`, `evals/runs/`, and
  `evals/prompts_under_test/`. `aggregate.py` (the no-key Path A report assembler) and
  `promptprep.py` (the prompt-prep glue) are part of the substrate — confirm both
  copied.
  ```

- [ ] **Step 7.2 — Add a non-clobbering re-setup note.** In `/home/dawti/je-dev-skills/skills/prompt-evals-setup/SKILL.md`, replace this exact block in Step 1 (lines 41-43):

  ```
  If `evals/` already exists, stop and report. Offer to re-run only if the user
  explicitly confirms overwriting.
  ```

  with:

  ```
  If `evals/` already exists, do NOT clobber it. Instead, run the **non-clobbering
  substrate update**: copy in ONLY the substrate files that are missing or that the
  user has not customized, leaving `config.py`, `run_eval.py`, and any
  `prompts_under_test/*.md` the user edited untouched.

  ```bash
  SRC="${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals"
  # New top-level substrate modules: safe to add if absent (the framework owns them).
  for f in aggregate.py promptprep.py; do
    [ -f "$TARGET/evals/$f" ] || cp "$SRC/$f" "$TARGET/evals/$f"
  done
  # New tests for the substrate.
  for f in tests/test_aggregate.py tests/test_promptprep.py; do
    [ -f "$TARGET/evals/$f" ] || cp "$SRC/$f" "$TARGET/evals/$f"
  done
  cp -Rn "$SRC/tests/fixtures/." "$TARGET/evals/tests/fixtures/" 2>/dev/null || true
  ```

  For `config.py` (the `EXECUTION_MODE` block) and `run_eval.py` (the file-backed +
  mode-aware changes), do NOT overwrite — these are user-editable. Show the user a diff
  against the bundled versions and let them merge the `EXECUTION_MODE`/subagent-knob
  constants and the mode-aware `main()` by hand if their copy predates the substrate.
  Then report what was added and stop.
  ```

- [ ] **Step 7.3 — Structural check.** Run:
  ```bash
  cd /home/dawti/je-dev-skills && python3 - <<'PY'
  text = open("skills/prompt-evals-setup/SKILL.md", encoding="utf-8").read()
  required = [
      "evals/aggregate.py", "evals/promptprep.py",
      "non-clobbering substrate update",
      "cp -Rn", "EXECUTION_MODE",
  ]
  missing = [s for s in required if s not in text]
  assert not missing, f"MISSING: {missing}"
  print("setup-doc-OK")
  PY
  ```
  Expected:
  ```
  setup-doc-OK
  ```

- [ ] **Step 7.4 — Real vendoring smoke (proves a fresh `cp -R` ships the substrate + everything imports/passes from a clean copy).** Run:
  ```bash
  rm -rf /tmp/setup_smoke && mkdir -p /tmp/setup_smoke && \
  cp -R /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals /tmp/setup_smoke/evals && \
  find /tmp/setup_smoke/evals -name __pycache__ -type d -prune -exec rm -rf {} + ; \
  test -f /tmp/setup_smoke/evals/aggregate.py && test -f /tmp/setup_smoke/evals/promptprep.py && echo "files-present" && \
  cd /tmp/setup_smoke && python3 -m unittest discover -s evals/tests -t . 2>&1 | tail -3
  ```
  Expected:
  ```
  files-present
  Ran 46 tests in 0.0XXs

  OK
  ```

- [ ] **Step 7.5 — Non-clobbering re-setup smoke (proves the additive copy adds missing files but preserves a user-edited config).** Run:
  ```bash
  rm -rf /tmp/resetup_smoke && mkdir -p /tmp/resetup_smoke/evals && \
  SRC=/home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals && \
  cp -R "$SRC/evaluator" /tmp/resetup_smoke/evals/evaluator && \
  printf 'PASS_THRESHOLD = 99  # user edit\n' > /tmp/resetup_smoke/evals/config.py && \
  for f in aggregate.py promptprep.py; do [ -f /tmp/resetup_smoke/evals/$f ] || cp "$SRC/$f" /tmp/resetup_smoke/evals/$f; done && \
  grep -q "PASS_THRESHOLD = 99" /tmp/resetup_smoke/evals/config.py && echo "user-config-preserved" && \
  test -f /tmp/resetup_smoke/evals/aggregate.py && test -f /tmp/resetup_smoke/evals/promptprep.py && echo "substrate-added"
  ```
  Expected:
  ```
  user-config-preserved
  substrate-added
  ```

- [ ] **Step 7.6 — Commit.**
  ```bash
  cd /home/dawti/je-dev-skills && git add skills/prompt-evals-setup/SKILL.md && \
  git commit -m "$(printf 'Vendor aggregate.py + promptprep.py; non-clobbering re-setup note\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
  ```

---

## Task 8 — Final verification of the whole substrate

- [ ] **Step 8.1 — Full offline suite from the framework root.**
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t . 2>&1 | tail -3
  ```
  Expected:
  ```
  Ran 46 tests in 0.0XXs

  OK
  ```

- [ ] **Step 8.2 — Confirm the framework CORE is byte-for-byte unchanged (composition invariant).** Run:
  ```bash
  cd /home/dawti/je-dev-skills && git diff --name-only main -- \
    skills/prompt-evals-setup/framework/evals/evaluator \
    skills/prompt-evals-setup/framework/evals/prompts
  ```
  Expected output: **(empty)** — no CORE file changed. If any line prints, you edited the frozen core; revert it.

- [ ] **Step 8.3 — Confirm only the intended top-level files changed/added.** Run:
  ```bash
  cd /home/dawti/je-dev-skills && git diff --name-status main -- skills/prompt-evals-setup skills/prompt-evals-run
  ```
  Expected to list exactly (status A or M):
  ```
  M  skills/prompt-evals-run/SKILL.md
  M  skills/prompt-evals-setup/SKILL.md
  M  skills/prompt-evals-setup/framework/evals/config.py
  M  skills/prompt-evals-setup/framework/evals/run_eval.py
  A  skills/prompt-evals-setup/framework/evals/aggregate.py
  A  skills/prompt-evals-setup/framework/evals/promptprep.py
  A  skills/prompt-evals-setup/framework/evals/prompts_under_test/meal_plan.current.md
  A  skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py
  A  skills/prompt-evals-setup/framework/evals/tests/test_promptprep.py
  A  skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok/case-00.json
  A  skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok/case-01.json
  A  skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_ok/case-02.json
  A  skills/prompt-evals-setup/framework/evals/tests/fixtures/verdicts_bad/bad-missing-score.json
  ```

- [ ] **Step 8.4 — Keyed-fallback wiring sanity (no key needed; we only confirm it routes into `run_evaluation`, not that it calls the API).** Run:
  ```bash
  cd /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework && python3 -c "
  import evals.config as config
  config.EXECUTION_MODE = 'anthropic_api'
  import evals.run_eval as r
  # Monkeypatch run_evaluation so we never need a key/network; assert it is reached
  # AND that run_label is threaded through.
  seen = {}
  class FakeEval:
      def run_evaluation(self, **kw):
          seen.update(kw); return {'run_dir':'x'}
  r.build_evaluator = lambda: FakeEval()
  rc = r.main(['run_eval','evaluate','keyed-label'])
  assert rc == 0, rc
  assert seen['run_label'] == 'keyed-label', seen
  assert seen['dataset_file'].endswith('meal_plan.json'), seen
  print('keyed-path-routes-OK')
  "
  ```
  Expected:
  ```
  keyed-path-routes-OK
  ```

- [ ] **Step 8.5 — Clean up scratch artifacts.**
  ```bash
  rm -rf /tmp/agg_smoke /tmp/setup_smoke /tmp/resetup_smoke
  find /home/dawti/je-dev-skills/skills/prompt-evals-setup/framework/evals -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  ```

- [ ] **Step 8.6 — Final commit (only if Step 8.5 left tracked changes; otherwise skip).**
  ```bash
  cd /home/dawti/je-dev-skills && git status --porcelain
  ```
  If clean, the substrate is complete. If anything tracked changed, stage and commit it with the standard footer.

---

## Coverage map (spec section → task)

- Architecture spec §2.3 "CHANGED `evals/config.py` — add `EXECUTION_MODE`" → **Task 1**.
- Prompt-engineering spec §4 Layer-2 "deterministic prompt-prep glue `check_placeholders`" + behavioral AC "unused-input warning" → **Task 2**.
- Architecture spec §2.2 Path A step 4 + §2.3 "NEW `evals/aggregate.py`" + shared interface contract `aggregate.py` CLI/imports/`run_label` → **Tasks 3 + 4**.
- Architecture spec §2.3 "CHANGED `evals/run_eval.py` … `main()` becomes mode-aware … `run_label` threaded" + prompt-engineering spec §4 "file-backed `<name>.current.md` + `render()` + check-placeholders default" → **Task 5**.
- Architecture spec §2.3 + §5 "CHANGED `prompt-evals-run/SKILL.md` — run procedure → Path A; keyed fallback documented" → **Task 6** (the §4 diagnosis re-scope is deferred to the sibling prompt-engineering-improve plan, noted inline).
- Architecture spec §2.3 + §5 "`prompt-evals-setup`'s vendoring must ship `aggregate.py` … re-running setup must add them non-clobbering" → **Task 7**.
- Architecture spec §5 "Composition invariant (named files): CORE unchanged" + offline acceptance "given fixture verdict JSONs, `aggregate.py` produces the correct `output.json`/`output.html` with no API key and no model call" + "keyed fallback still works" → **Task 8**.

**Deferred to sibling plans (not this plan):** `improve_step.py` + loop-param constants block (prompt-engineering-improve plan); the §4 single-pass diagnosis re-scope + `diagnosis.md` citation merged into `prompt-evals-run/SKILL.md` (prompt-engineering-improve plan); `README.md`/`plugin.json`/`docs/WORKFLOW_DESIGN_SPEC.md` wiring and `agent-build-*` (composition/agent-build plans). The framework CORE (`evaluator/*.py`, `prompts/`) is intentionally untouched.
