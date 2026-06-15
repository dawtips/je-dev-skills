# Path A renders `command_adapter` targets — Implementation Plan

Status: In progress

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Path A (`EXECUTION_MODE=in_claude_code`, no API key) run `command_adapter`
targets by rendering a deterministic, render-only `target.render_command` (stdout = the
assembled prompt) that the execute-subagent then answers like a `prompt_file` target.

**Architecture:** Add an optional `target.render_command` argv. `render-artifact` renders it
(subprocess, `{"prompt_inputs":…}` on stdin → prompt on stdout). Path B and `prompt_file`
stay unchanged; a render-only target raised clearly on Path B. Spec:
`docs/superpowers/specs/2026-06-14-path-a-command-adapter-render-spec.md`.

**Tech stack:** Python 3 stdlib (`subprocess`, `json`, `unittest`); the plugin-resident
`evals` framework under `skills/prompt-evals-setup/framework/`.

> **Host note:** on this Windows box, `python3` is the broken Store shim — run the test
> commands with `python`. (`AGENTS.md` uses `python3` on POSIX; both run the same suite.)
> Run all framework commands from `skills/prompt-evals-setup/framework`.

All tasks are `inline` (core-engine + semantic; low task count).

---

### Task 1: `render_command` field + validation (`inline`)

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/artifacts.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_artifacts.py`

- [ ] **Step 1: Write the failing tests** — append to `test_artifacts.py` (it already imports
  `json`, `tempfile`, `unittest`, `Path`, `load_eval_spec`; add imports only if missing):

```python
class TestRenderCommandField(unittest.TestCase):
    def _eval_json(self, root: Path, name: str, target: dict) -> Path:
        eval_dir = root / "evals" / name
        (eval_dir / "runs").mkdir(parents=True, exist_ok=True)
        ej = eval_dir / "eval.json"
        ej.write_text(json.dumps({
            "name": name, "target": target, "cases_file": "cases.json",
            "runs_dir": "runs", "assertions": [], "assertion_policy": "gate_mandatory",
        }), encoding="utf-8")
        return ej

    def test_render_command_loads_for_command_adapter(self):
        with tempfile.TemporaryDirectory() as d:
            ej = self._eval_json(Path(d).resolve(), "agent", {
                "mode": "command_adapter",
                "command": ["echo", "x"],
                "render_command": ["echo", "render"],
            })
            spec = load_eval_spec(ej)
            self.assertEqual(spec.render_command, ["echo", "render"])
            self.assertEqual(spec.target.render_command, ["echo", "render"])

    def test_render_only_command_adapter_loads(self):
        with tempfile.TemporaryDirectory() as d:
            ej = self._eval_json(Path(d).resolve(), "agent", {
                "mode": "command_adapter", "render_command": ["echo", "render"],
            })
            spec = load_eval_spec(ej)
            self.assertIsNone(spec.command)
            self.assertEqual(spec.render_command, ["echo", "render"])

    def test_command_adapter_requires_command_or_render_command(self):
        with tempfile.TemporaryDirectory() as d:
            ej = self._eval_json(Path(d).resolve(), "agent", {"mode": "command_adapter"})
            with self.assertRaisesRegex(ValueError, "command.*render_command"):
                load_eval_spec(ej)

    def test_render_command_rejected_for_prompt_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "prompts").mkdir(parents=True, exist_ok=True)
            (root / "prompts" / "p.md").write_text("{g}", encoding="utf-8")
            ej = self._eval_json(root, "p", {
                "mode": "prompt_file", "prompt_file": "prompts/p.md",
                "render_command": ["echo", "x"],
            })
            with self.assertRaisesRegex(ValueError, "command_adapter mode"):
                load_eval_spec(ej)

    def test_render_command_must_be_nonempty_list(self):
        with tempfile.TemporaryDirectory() as d:
            ej = self._eval_json(Path(d).resolve(), "agent", {
                "mode": "command_adapter", "render_command": [],
            })
            with self.assertRaisesRegex(ValueError, "non-empty list"):
                load_eval_spec(ej)

    def test_command_must_be_nonempty_list_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            ej = self._eval_json(Path(d).resolve(), "agent", {
                "mode": "command_adapter", "command": [],
                "render_command": ["echo", "render"],
            })
            with self.assertRaisesRegex(ValueError, "target.command must be a non-empty list"):
                load_eval_spec(ej)
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `python -m unittest evals.tests.test_artifacts -v`
Expected: FAIL (`render_command` unknown to `TargetSpec`/`load_eval_spec`).

- [ ] **Step 3: Implement** in `artifacts.py`:

3a. Add the field to `TargetSpec` (after `command`):

```python
    command: list[str] | None = None  # argv for the adapter subprocess (command_adapter mode)
    render_command: list[str] | None = None  # argv for a render-only adapter invocation (Path A)
    output_schema: dict | None = None  # optional JSON Schema for prompt-under-test output
```

3b. Add a property to `EvalSpec` (after the `command` property):

```python
    @property
    def render_command(self) -> list[str] | None:
        return self.target.render_command
```

3c. Replace `_validate_target` with the render-aware version (keep the default-`None`
`render_command` param so `scaffold_eval_artifacts`'s positional 3-arg call still works):

```python
def _validate_argv(value, field: str) -> None:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) for item in value)
    ):
        raise ValueError(f"{field} must be a non-empty list of strings")


def _validate_target(
    mode: str,
    prompt_file: str | None,
    command: list[str] | None,
    render_command: list[str] | None = None,
) -> None:
    if mode not in VALID_MODES:
        raise ValueError(f"target.mode must be one of {VALID_MODES}, got {mode!r}")
    if mode == "prompt_file":
        if not prompt_file:
            raise ValueError("prompt_file mode requires target.prompt_file")
        if render_command is not None:
            raise ValueError("target.render_command is only valid in command_adapter mode")
    if mode == "command_adapter" and not (command or render_command):
        raise ValueError(
            "command_adapter mode requires target.command or target.render_command"
        )
    if command is not None:
        _validate_argv(command, "target.command")
    if render_command is not None:
        _validate_argv(render_command, "target.render_command")
```

> Validating `command` whenever present (not just `render_command`) is required: a target
> with a valid `render_command` and an invalid `command` such as `[]` otherwise satisfies the
> `command or render_command` requirement, and the Path B guard's `spec.command is None` check
> would let an empty `command` reach `run_command_adapter` and degrade into scored-1 results
> instead of a loud config error. An empty/invalid `command` was already broken at run time;
> this makes it fail loudly at load time (no valid Path B config changes behavior).

3d. In `load_eval_spec`, read and thread `render_command`:

```python
    command = target_data.get("command")
    render_command = target_data.get("render_command")
    output_schema = target_data.get("output_schema")
    if output_schema is not None:
        output_schema = validate_output_schema(output_schema)
    _validate_target(mode, prompt_file, command, render_command)
    return EvalSpec(
        name=data.get("name", path.parent.name),
        eval_json=path,
        target=TargetSpec(
            mode=mode,
            prompt_file=prompt_file,
            command=command,
            render_command=render_command,
            output_schema=output_schema,
        ),
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `python -m unittest evals.tests.test_artifacts -v`
Expected: PASS (all, including the existing tests).

- [ ] **Step 5: Commit**

```bash
git add skills/prompt-evals-setup/framework/evals/artifacts.py \
        skills/prompt-evals-setup/framework/evals/tests/test_artifacts.py
git commit -m "feat(evals): target.render_command field + validation (T-026, #11)"
```

---

### Task 2: `render_command_adapter` runner + Path B guard (`inline`)

**Files:**
- Create: `skills/prompt-evals-setup/framework/evals/tests/fixtures/adapters/render_adapter.py`
- Modify: `skills/prompt-evals-setup/framework/evals/artifact_runner.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_artifact_runner.py`

- [ ] **Step 1: Create the render-only fixture** `render_adapter.py`:

```python
"""Offline render-only adapter fixture: read a case from stdin, print an assembled
PROMPT (model input, NOT an answer) on stdout. Mirrors the render_command contract."""

import json
import sys

case = json.load(sys.stdin)
sys.stdout.write("PROMPT for " + case["prompt_inputs"]["goal"])
```

- [ ] **Step 2: Write the failing tests** — add to `test_artifact_runner.py`. Extend the
  existing import to include `render_command_adapter`:

```python
from evals.artifact_runner import (
    build_run_function,
    evaluate_artifact,
    render_command_adapter,
    render_prompt_file,
    run_command_adapter,
)
```

Then append:

```python
_RENDER_ADAPTER = Path(__file__).parent / "fixtures" / "adapters" / "render_adapter.py"


def _render_only_eval(root: Path, render_command):
    eval_dir = root / "evals" / "agent"
    (eval_dir / "runs").mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval.json").write_text(
        json.dumps({
            "name": "agent",
            "target": {"mode": "command_adapter", "render_command": render_command},
        }),
        encoding="utf-8",
    )
    return load_eval_spec(eval_dir / "eval.json")


class TestRenderCommandAdapter(unittest.TestCase):
    def test_returns_assembled_prompt_from_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _render_only_eval(Path(d).resolve(), [sys.executable, str(_RENDER_ADAPTER)])
            self.assertEqual(render_command_adapter(spec, {"goal": "retention"}), "PROMPT for retention")

    def test_raises_on_failure(self):
        import subprocess

        fail = Path(__file__).parent / "fixtures" / "adapters" / "fail_adapter.py"
        with tempfile.TemporaryDirectory() as d:
            spec = _render_only_eval(Path(d).resolve(), [sys.executable, str(fail)])
            with self.assertRaises(subprocess.CalledProcessError):
                render_command_adapter(spec, {"goal": "x"})

    def test_times_out(self):
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            spec = _render_only_eval(
                Path(d).resolve(), [sys.executable, "-c", "import time; time.sleep(30)"]
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                render_command_adapter(spec, {"goal": "x"}, timeout=0.5)


class TestBuildRunFunctionRenderOnly(unittest.TestCase):
    def test_render_only_target_raises_on_path_b(self):
        with tempfile.TemporaryDirectory() as d:
            spec = _render_only_eval(Path(d).resolve(), [sys.executable, str(_RENDER_ADAPTER)])
            with self.assertRaisesRegex(ValueError, "render-only|render_command"):
                build_run_function(spec)
```

- [ ] **Step 3: Run the tests, verify they fail**

Run: `python -m unittest evals.tests.test_artifact_runner -v`
Expected: FAIL (`render_command_adapter` does not exist; `build_run_function` runs the
render-only target instead of raising).

- [ ] **Step 4: Implement** in `artifact_runner.py`:

4a. Add the render-only runner after `run_command_adapter`:

```python
def render_command_adapter(
    spec: EvalSpec, prompt_inputs: dict, *, timeout: float | None = config.ADAPTER_TIMEOUT_SECONDS
) -> str:
    """Run the render-only command: ``{"prompt_inputs": …}`` on stdin, the assembled
    prompt (model *input*, not an answer) on stdout. Deterministic; no model call.

    ``timeout`` bounds the subprocess; a non-zero exit raises ``CalledProcessError`` and
    a timeout raises ``TimeoutExpired`` (the CLI turns both into a clean rc-2 error).
    """
    if not spec.render_command:
        raise ValueError(
            "render_command_adapter requires a command_adapter-mode eval spec with "
            "target.render_command"
        )
    proc = subprocess.run(
        list(spec.render_command),
        input=json.dumps({"prompt_inputs": prompt_inputs}),
        capture_output=True,
        text=True,
        cwd=str(spec.project_root),
        check=True,
        timeout=timeout,
    )
    return proc.stdout
```

4b. Guard the `command_adapter` branch of `build_run_function` so a render-only target
fails clearly on Path B (it was unreachable before — `command` used to be required):

```python
    if mode == "command_adapter":
        if spec.command is None:
            raise ValueError(
                "command_adapter target defines only target.render_command (render-only); "
                "it has no Path B generate command. Run it on Path A (in_claude_code), or "
                "add a generate target.command for Path B (evaluate-artifact)."
            )

        def _run_adapter(prompt_inputs: dict) -> str:
            return run_command_adapter(spec, {"prompt_inputs": prompt_inputs})

        return _run_adapter
```

- [ ] **Step 5: Run the tests, verify they pass**

Run: `python -m unittest evals.tests.test_artifact_runner -v`
Expected: PASS (new + existing, incl. `test_command_adapter_run_function_needs_no_executor`
which still has a `command`).

- [ ] **Step 6: Commit**

```bash
git add skills/prompt-evals-setup/framework/evals/artifact_runner.py \
        skills/prompt-evals-setup/framework/evals/tests/test_artifact_runner.py \
        skills/prompt-evals-setup/framework/evals/tests/fixtures/adapters/render_adapter.py
git commit -m "feat(evals): render_command_adapter runner + render-only Path B guard (T-026, #11)"
```

---

### Task 3: `render-artifact` CLI renders `command_adapter` (`inline`)

**Files:**
- Modify: `skills/prompt-evals-setup/framework/evals/run_eval.py`
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_run_eval_cli.py`

- [ ] **Step 1: Write the failing tests** — add to `test_run_eval_cli.py` (it already has the
  `self._run(argv) -> (rc, stdout)` helper in `TestRunEvalCli`):

```python
    # --- T-026 render-artifact for command_adapter ---------------------------
    _RENDER_ADAPTER = Path(__file__).parent / "fixtures" / "adapters" / "render_adapter.py"

    def _scaffold_render_adapter_project(self, root: Path, render_command):
        import sys
        scaffold_eval_artifacts(
            root, "agent", mode="command_adapter", command=[sys.executable, "-c", "pass"]
        )
        ej = root / "evals" / "agent" / "eval.json"
        data = json.loads(ej.read_text(encoding="utf-8"))
        data["target"]["render_command"] = render_command
        ej.write_text(json.dumps(data), encoding="utf-8")
        (root / "evals" / "agent" / "cases.json").write_text(
            json.dumps({
                "provenance": {"task_description": "agent"},
                "cases": [{"task_description": "agent",
                           "prompt_inputs": {"goal": "retention"},
                           "solution_criteria": ["x"]}],
            }),
            encoding="utf-8",
        )
        return ej

    def test_render_artifact_renders_command_adapter(self):
        import sys
        with tempfile.TemporaryDirectory() as d:
            ej = self._scaffold_render_adapter_project(
                Path(d).resolve(), [sys.executable, str(self._RENDER_ADAPTER)]
            )
            rc, out = self._run(["render-artifact", str(ej), "0"])
            self.assertEqual(rc, 0)
            self.assertIn("PROMPT for retention", out)

    def test_render_artifact_command_adapter_without_render_command_errors(self):
        import sys
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            scaffold_eval_artifacts(
                root, "agent", mode="command_adapter", command=[sys.executable, "-c", "pass"]
            )
            (root / "evals" / "agent" / "cases.json").write_text(
                json.dumps({"provenance": {}, "cases": [
                    {"task_description": "a", "prompt_inputs": {"goal": "g"}, "solution_criteria": ["x"]}]}),
                encoding="utf-8",
            )
            rc, out = self._run(["render-artifact", str(root / "evals" / "agent" / "eval.json"), "0"])
            self.assertEqual(rc, 2)
            self.assertIn("render_command", out)

    def test_render_artifact_render_command_failure_is_clean_rc2(self):
        import sys
        fail = Path(__file__).parent / "fixtures" / "adapters" / "fail_adapter.py"
        with tempfile.TemporaryDirectory() as d:
            ej = self._scaffold_render_adapter_project(
                Path(d).resolve(), [sys.executable, str(fail)]
            )
            rc, out = self._run(["render-artifact", str(ej), "0"])
            self.assertEqual(rc, 2)
            self.assertIn("render_command failed", out)
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `python -m unittest evals.tests.test_run_eval_cli -v`
Expected: FAIL (current `render-artifact` rejects any non-`prompt_file` mode at rc 2 with
`render-artifact only applies to prompt_file mode`, so the render test fails and the
failure-message asserts miss).

- [ ] **Step 3: Implement** in `run_eval.py`:

3a. Add the stdlib import (top of file, after `import json`):

```python
import json
import subprocess
import sys
```

3b. Replace the whole `if command == "render-artifact":` block (the one that errors on
non-`prompt_file` mode) with:

```python
    if command == "render-artifact":
        if len(argv) != 4:
            print("usage: python -m evals.run_eval render-artifact <eval.json> <case_index>")
            return 2
        spec = _load_eval_spec_for_cli(argv[2])
        if spec is None:
            return 2
        mode = spec.target.mode
        if mode == "command_adapter" and not spec.render_command:
            print(
                "error: render-artifact needs target.render_command for a command_adapter "
                "target (Path A renders the assembled prompt with no model). Add "
                "render_command, or run this target on Path B (evaluate-artifact)."
            )
            return 2
        if mode not in ("prompt_file", "command_adapter"):
            print(f"error: render-artifact does not support target mode {mode!r}")
            return 2
        try:
            index = int(argv[3])
        except ValueError:
            print("error: <case_index> must be an integer")
            return 2
        if not spec.cases_file.exists():
            print(
                f"error: cases file not found: {spec.cases_file} "
                "(run 'generate-artifact' / prompt-evals-create-dataset first)"
            )
            return 2
        cases = json.loads(spec.cases_file.read_text(encoding="utf-8")).get("cases", [])
        if index < 0 or index >= len(cases):
            print(f"error: case_index {index} out of range (0..{len(cases) - 1})")
            return 2
        prompt_inputs = cases[index]["prompt_inputs"]
        if mode == "prompt_file":
            print(artifact_runner.render_prompt_file(spec, prompt_inputs))
            return 0
        # command_adapter with target.render_command: stdout IS the assembled prompt.
        try:
            rendered = artifact_runner.render_command_adapter(spec, prompt_inputs)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            print(f"error: render_command failed (exit {exc.returncode}): {stderr}")
            return 2
        except subprocess.TimeoutExpired:
            print(f"error: render_command timed out after {config.ADAPTER_TIMEOUT_SECONDS}s")
            return 2
        print(rendered, end="")
        return 0
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `python -m unittest evals.tests.test_run_eval_cli -v`
Expected: PASS (new + existing prompt_file render tests).

- [ ] **Step 5: Commit**

```bash
git add skills/prompt-evals-setup/framework/evals/run_eval.py \
        skills/prompt-evals-setup/framework/evals/tests/test_run_eval_cli.py
git commit -m "feat(evals): render-artifact renders command_adapter via render_command (T-026, #11)"
```

---

### Task 4: render-failure verdict survives aggregation (`inline`)

Locks the spec §3.2 "no dropped case" contract offline. (`prompt_file` render failures stay
loud per §3.2 rule 3 — no behavior change to test.)

**Files:**
- Test: `skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py`

- [ ] **Step 1: Write the failing/locking tests** — append to `test_aggregate.py` (it has the
  module-level `_write_dataset(path, cases, task=...)` helper and imports `aggregate`,
  `json`, `tempfile`, `Path`):

```python
class TestRenderFailureVerdictSurvives(unittest.TestCase):
    def _run_aggregate(self, root: Path, verdict_record: dict, case: dict) -> int:
        verdicts = root / "verdicts"; verdicts.mkdir()
        runs = root / "runs"; runs.mkdir()
        ds = root / "cases.json"
        _write_dataset(ds, [case])
        (verdicts / "case-00.json").write_text(json.dumps(verdict_record), encoding="utf-8")
        return aggregate.main([
            "--run-label", "t", "--verdicts-dir", str(verdicts),
            "--dataset", str(ds), "--runs-dir", str(runs), "--extra-criteria", "none",
        ]), runs

    def test_complete_render_failure_verdict_is_scored_not_aborted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            case = {"task_description": "t", "prompt_inputs": {"goal": "x"},
                    "solution_criteria": ["c"]}
            rc, runs = self._run_aggregate(root, {
                "test_case": case,
                "output": "",
                "assertion_gate": None,
                "verdict": {"strengths": [], "weaknesses": ["render_command failed"],
                            "reasoning": "render_command failed (exit 1): boom", "score": 1},
            }, case)
            self.assertEqual(rc, 0)
            out = json.loads((runs / "t" / "output.json").read_text(encoding="utf-8"))
            self.assertEqual(out["results"][0]["score"], 1)

    def test_verdict_only_render_failure_file_aborts(self):
        """Proves the P1: a verdict-only file (no test_case) aborts the whole run."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            case = {"task_description": "t", "prompt_inputs": {"goal": "x"},
                    "solution_criteria": ["c"]}
            rc, _ = self._run_aggregate(root, {
                "verdict": {"strengths": [], "weaknesses": [], "reasoning": "r", "score": 1},
            }, case)
            self.assertEqual(rc, 1)
```

- [ ] **Step 2: Run the tests**

Run: `python -m unittest evals.tests.test_aggregate -v`
Expected: PASS immediately — this task adds **no production code**; it pins existing
`aggregate` behavior to the §3.2 verdict-file shape. If
`test_complete_render_failure_verdict_is_scored_not_aborted` fails, the assumed `output.json`
results shape is wrong; read `runs/t/output.json` and fix the assertion's key path (do not
change `aggregate.py`).

- [ ] **Step 3: Commit**

```bash
git add skills/prompt-evals-setup/framework/evals/tests/test_aggregate.py
git commit -m "test(evals): render-failure verdict survives aggregation (T-026, #11)"
```

---

### Task 5: document the `command_adapter` subscription path in the skill (`inline`)

**Files:**
- Modify: `skills/prompt-evals-run/SKILL.md`

- [ ] **Step 1: Add the precondition.** After the prompt-file precondition bullet (the
  `{placeholder}` one), add:

```markdown
- For **command-adapter** mode, Path A requires `target.render_command` — a render-only argv
  whose **stdout is the assembled prompt** (the model's input, not an answer). It receives
  `{"prompt_inputs": {…}}` on stdin and must print only the assembled prompt deterministically
  (no model, no log noise). Without `render_command`, a `command_adapter` target has no Path A
  — run it on Path B.
```

- [ ] **Step 2: Replace the step-1 render block** (the `RENDERED=$(… render-artifact …)`
  line under "### 2. For each case…") with an exit-code-guarded version:

````markdown
1. **Render the prompt deterministically** (no model) with the plugin-resident helper. It
   renders both target modes — a `prompt_file` template (reusing `render()` +
   `check_placeholders`) and a `command_adapter` with `target.render_command` (running the
   render-only command; its stdout is the prompt). **Check the exit code** and capture stdout
   only on success — never dispatch the execute-subagent with an empty/partial prompt:

   ```bash
   # Capture STDOUT only into $RENDERED (the prompt); keep STDERR separate so a success-path
   # warning (e.g. check_placeholders logs an unused-input warning and still returns the
   # prompt) never contaminates the prompt sent to the execute-subagent.
   ERRFILE=$(mktemp)
   if RENDERED=$(cd "$PE" && python3 -m evals.run_eval render-artifact "$EVAL" "$i" 2>"$ERRFILE"); then
     rm -f "$ERRFILE"   # success: $RENDERED is the prompt (stdout); ignore any stderr warning
   else
     ERR=$(cat "$ERRFILE"); rm -f "$ERRFILE"
     # render-artifact exited non-zero. NEVER dispatch a prompt. The CLI prints its clean
     # `error: …` to STDOUT, so the message is in $RENDERED ($ERR holds a Python traceback,
     # e.g. a prompt_file MissingPlaceholderError). Recover ONLY a command_adapter
     # render_command RUNTIME failure (the CLI prints "render_command failed …" or
     # "render_command timed out …"). Every other rc != 0 — no render_command, missing cases
     # file, bad case index, or a prompt_file config error — is loud:
     if printf '%s' "$RENDERED" | grep -Eq 'render_command (failed|timed out)'; then
       # write the COMPLETE synthetic score-1 verdict below to
       # "$VERDICTS_DIR/case-$(printf '%02d' "$i").json", THEN continue (run not aborted).
       :  # write the verdict file shown below first, then:
       continue
     fi
     echo "render failed for case $i (config/setup error): ${RENDERED}${ERR}" >&2
     exit 1   # do NOT write a score-1 verdict — that would hide the misconfig as a low score
   fi
   ```

   **Synthetic render-failure verdict (command_adapter only).** Write the per-case verdict
   file with the *same shape* as a normal/`judge_skipped` case (so `aggregate` scores it
   instead of aborting), differing only in the `verdict`:

   ```json
   {
     "test_case": { "...the cases.json case i verbatim...": "..." },
     "output": "",
     "assertion_gate": null,
     "verdict": { "strengths": [], "weaknesses": ["render_command failed"],
                  "reasoning": "<the render-artifact error line>", "score": 1 }
   }
   ```
````

- [ ] **Step 3: Verify the doc edits** read coherently and run the skill linter (Task 6 runs
  the full lint; this is a quick local check):

Run (from repo root): `python tools/skill_lint.py --root .`
Expected: `0 errors` (the linter passes; note the exact summary line for the PR).

- [ ] **Step 4: Commit**

```bash
git add skills/prompt-evals-run/SKILL.md
git commit -m "docs(prompt-evals-run): document command_adapter Path A render + failure handling (T-026, #11)"
```

---

### Task 6: full regression + linter, paste output (`inline`)

**Files:** none (verification only).

- [ ] **Step 1: Run the prompt-evals framework suite**

Run (from `skills/prompt-evals-setup/framework`):
`python -m unittest discover -s evals/tests -t .`
Expected: OK (all tests pass). Paste the final `Ran N tests … OK` line into the PR.

- [ ] **Step 2: Run the skill linter**

Run (from repo root): `python tools/skill_lint.py --root .`
Expected: 0 errors. Paste the summary line.

- [ ] **Step 3: Run the other offline suites named in `AGENTS.md`** that could be touched
  (sanity; this change is confined to the eval framework + one skill):

Run (from repo root):
`python -m unittest discover -s tools/tests -t tools`
Expected: OK. Paste the summary.

- [ ] **Step 4: Push and run the Codex implementation loop**

```bash
git push
# poll with the shared helper (never a hand-rolled loop):
bash ~/.claude/scripts/codex-poll.sh <pr> <head-sha>
```
Address findings until a fresh 👍 lands on the latest push.

---

## Self-review

**Spec coverage:** §3 contract → Task 2 (`render_command_adapter` stdin/stdout/timeout) + Task 1
(field). §3.1 (new field, not a flag) → Task 1. §3.2 rules 1–3 (exit-code guard / score-1 for
render_command / prompt_file loud) → Task 5 + Task 4 (aggregation lock). §4 boundary
(Path B unchanged; render-only raises) → Task 2 step 4b. §5 validation → Task 1. §6 file table
→ Tasks 1–5. §7 verification → Tasks 1–4 + Task 6.

**Placeholder scan:** every code/test/command step has literal content; no TBD/TODO.

**Type consistency:** `render_command_adapter(spec, prompt_inputs, *, timeout=…)`,
`spec.render_command`, `TargetSpec.render_command`, and `_validate_target(…, render_command=None)`
are named identically across Tasks 1–3 and the CLI. The CLI calls
`artifact_runner.render_command_adapter` and `render_prompt_file` — both defined in Task 2 /
already present.
