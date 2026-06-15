# Path A renders `command_adapter` targets — Specification & Design

A design contract for letting the subscription execution path (**Path A**,
`EXECUTION_MODE=in_claude_code`, no API key) run `command_adapter` targets, by adding a
deterministic **render-only** command contract that produces the assembled prompt (model
*input*), which the execute-subagent then answers exactly like a `prompt_file` target.

> **Ticket covered:** [T-026] Path A (in_claude_code) renders `command_adapter` targets
> (phase `eval-hardening`, type `feature`). **GitHub issue:** #11.
>
> **Relationship to other specs.** This extends the plugin-resident artifact path defined
> in `2026-05-30-prompt-evals-plugin-resident-architecture-spec.md` (§3: one unified run
> path through `live_run.run_evaluation`). It adds a target capability; it does not change
> the run seam, the report writers, or assertion gating.

---

## 1. Purpose & problem

The subscription path (Path A) is the canonical, no-key way to run evals: the interactive
session dispatches subagents to execute and grade each case. Today Path A can only run
`prompt_file` targets, because its first step renders the prompt deterministically via the
`render-artifact` CLI, and that command **errors for any non-`prompt_file` target**
(`run_eval.py:263-264`: `render-artifact only applies to prompt_file mode`).

`command_adapter` targets therefore have no Path A. They can run only via Path B
(`anthropic_api`, metered, needs `ANTHROPIC_API_KEY`), where `run_command_adapter` runs
the project's command and grades **its stdout as the generated answer**.

This blocks a real consumer. **presales-sqnce** uses `command_adapter` on purpose (design
decision D4) to grade the *real* CLI prompt assembly — `node src/cli/index.js eval-adapter
--step <step>` — rather than a hand-maintained template copy that would drift from
production. Because that target is `command_adapter`, its suites cannot run on the Claude
Code subscription; only the metered API. Converting to `prompt_file` is a workaround that
loses assembly fidelity (the template duplicates, and drifts from, the production
assembly).

## 2. The key distinction (why this is not just "run the adapter")

The existing `command_adapter` contract treats the command's **stdout as the gradeable
answer** (an embedded agent produces output). The capability this spec adds is the
*opposite*: a **render-only** command whose **stdout is the assembled prompt** — the
model's *input*, not its output. Path A then feeds that prompt to the execute-subagent,
which produces the answer under the subscription. Conflating the two would grade the prompt
as if it were the answer, so the contract must be explicit and separate.

## 3. Design decision: a distinct `target.render_command`

Add a new optional field `target.render_command` (an argv list) that names the
**render-only** invocation of the adapter, distinct from the generate `command`.

```jsonc
// eval.json target, render-capable command_adapter
"target": {
  "mode": "command_adapter",
  "render_command": ["node", "src/cli/index.js", "eval-adapter", "--step", "discover", "--render"],
  "command": ["node", "src/cli/index.js", "eval-adapter", "--step", "discover"]  // optional (Path B generate)
}
```

**Render-only command contract** (identical I/O shape to the generate adapter, so projects
reuse one stdin convention):

- **Invocation:** the `render_command` argv, run with `cwd = project_root`, bounded by
  `config.ADAPTER_TIMEOUT_SECONDS` (default 120s), `check=True`. A non-zero exit (or a
  timeout) raises `CalledProcessError` / `TimeoutExpired`; the `render-artifact` CLI
  **catches it, prints `error: render_command failed …` with the adapter's stderr, and
  exits non-zero (rc 2)** — no traceback, never a silent pass. See §3.2 for how Path A
  reacts to that non-zero exit.
- **stdin:** the JSON object `{"prompt_inputs": {…}}` for case *i* — the same shape
  `run_command_adapter` already sends. Deterministic; **no model call**.
- **stdout:** the fully assembled prompt for that case (raw text). The framework treats
  stdout as the **prompt**, and hands it to the execute-subagent verbatim.

### 3.2 Path A render-failure handling (no silent dropped cases)

Path A renders by *shelling out* to `render-artifact` before any execute/grade verdict is
written, so — unlike Path B, where `run_evaluation`'s per-case handler turns an adapter
exception into a scored-1 failure automatically — the skill loop must handle a render
failure itself. The contract:

- The skill **must check the `render-artifact` exit code** for each case. It captures
  stdout into `$RENDERED` *only* on rc 0 (e.g. `RENDERED=$(… render-artifact …) || { …
  handle failure … }`). It must **never** dispatch the execute-subagent with an empty or
  partial prompt produced by a failed render.
- On a non-zero render exit, the skill records a **synthetic scored-1 failure verdict** for
  that case — `{"strengths":[],"weaknesses":["render_command failed"],"reasoning":"<the
  CLI's error line>","score":1}` — and continues to the next case (the run is not aborted;
  partial results are never lost, as in Path B). The render error rides in the verdict's
  `reasoning`/`weaknesses`, which `evals.aggregate.load_results` preserves verbatim
  (`reasoning` and the whole `verdict` are kept), so the failure is visible in
  `output.json`/`output.html` and the case is scored, not omitted.

A verdict-level `error` field and a `meta.errors` list are a **Path-B-only** concept:
Path A's `evals.aggregate.load_results` keeps only
`output/trajectory/test_case/score/reasoning/verdict/assertion_gate` (a top-level `error`
is dropped) and `_build_meta` builds no `errors` list. This spec deliberately leaves
`aggregate.py` unchanged, so it makes **no** `error`/`meta.errors` promise for Path A — the
render error is surfaced through the preserved `reasoning`/`weaknesses` instead. This keeps
the floor non-negotiable (render errors are loud and never silently drop a case) without
expanding scope into the shared aggregator.

### 3.1 Why a new field, not a flag/stdin convention (rejected alternative)

Issue #11 floated reusing the existing `command` with a render-only convention (e.g. the
framework appends `--render`, or the command auto-detects a render request on stdin). That
is rejected: the framework cannot know a project's render flag, auto-mutating argv is
brittle and silent, and overloading one command with two stdout meanings (prompt vs.
answer) is exactly the conflation §2 warns against. An explicit, separately-named argv is
self-documenting, validates cleanly, and lets a target offer *both* paths (render for
Path A, generate for Path B) without ambiguity.

## 4. Scope & boundaries

**In scope**

1. `target.render_command` on `TargetSpec` / `EvalSpec` / `load_eval_spec`, with
   validation (§5).
2. `artifact_runner.render_command_adapter(spec, prompt_inputs)` — deterministic render-only
   subprocess (the §3 contract).
3. `render-artifact` CLI: render `prompt_file` (unchanged) **and** `command_adapter` with a
   `render_command`; a clear, actionable error for `command_adapter` **without**
   `render_command`.
4. `prompt-evals-run/SKILL.md` Path A documents the `command_adapter` subscription path and
   its precondition (`render_command` set).

**Out of scope (deliberate, to honor "Path B unchanged")**

- **Path B (`evaluate-artifact`) behavior is unchanged.** `build_run_function`'s
  `command_adapter` branch keeps grading the generate `command`'s stdout as the answer. A
  target that defines **only** `render_command` (no generate `command`) is a Path-A-only
  target; `build_run_function` raises a clear error pointing to Path A rather than guessing
  a Path B execution. This adds an error only for a configuration that was previously
  invalid (a `command_adapter` with no `command` failed validation before), so no existing
  valid Path B run changes behavior.
- **`scaffold-artifact` is not extended** to emit `render_command` (it stays
  `command`-only); a render-capable target adds the field by editing `eval.json`. Threading
  a render arg through the scaffold CLI is a separate, optional ergonomics ticket.
- Path B "render via `render_command`, then call the keyed executor" symmetry is **not**
  built; it is unnecessary for the acceptance criteria and would change Path B.

## 5. Validation rules (`artifacts._validate_target`)

- `command_adapter` requires **at least one** of `command` / `render_command`
  (was: `command` required). Message names both.
- `render_command`, if present, is valid **only** in `command_adapter` mode (reject in
  `prompt_file` mode with a clear message).
- `render_command`, if present, must be a non-empty list of strings (mirror `command`).
- `prompt_file` mode is unchanged: `prompt_file` required; `command`/`render_command`
  rejected.

`EvalSpec` gains a `render_command` property returning `self.target.render_command`.

## 6. Affected files

| File | Change |
|---|---|
| `evals/artifacts.py` | `TargetSpec.render_command`; `EvalSpec.render_command`; parse in `load_eval_spec`; `_validate_target` per §5. |
| `evals/artifact_runner.py` | `render_command_adapter(spec, prompt_inputs)` (§3 contract); `build_run_function` raises a clear error for a render-only target on Path B. |
| `evals/run_eval.py` | `render-artifact` branches on mode: `prompt_file` → `render_prompt_file`; `command_adapter` + `render_command` → `render_command_adapter`; else actionable error (rc 2). Catches `CalledProcessError`/`TimeoutExpired` from a failing `render_command` and reports `error: render_command failed …` with rc 2 (no traceback). |
| `skills/prompt-evals-run/SKILL.md` | Path A precondition + note that `render-artifact` renders a render-capable `command_adapter`; the execute-subagent answers `$RENDERED` identically; **render step checks the exit code and records a synthetic scored-1 failure verdict on a non-zero render (no silent dropped case, §3.2)**. |
| `evals/tests/test_artifacts.py`, `test_artifact_runner.py`, `test_run_eval_cli.py` | Tests per §7. |
| `evals/tests/fixtures/adapters/render_adapter.py` | New fixture: reads `{"prompt_inputs": …}` on stdin, prints an assembled *prompt* on stdout. |

## 7. Verification plan (TDD, offline, no key)

Deterministic core first; all tests run with `python -m unittest` from the framework dir,
no network, no `ANTHROPIC_API_KEY`.

1. **Validation** (`test_artifacts.py`): `render_command` accepted for `command_adapter`;
   rejected for `prompt_file`; `command_adapter` with neither `command` nor `render_command`
   rejected; `command_adapter` with only `render_command` loads; round-trips onto
   `EvalSpec.render_command`.
2. **Render-only runner** (`test_artifact_runner.py`): `render_command_adapter` pipes
   `{"prompt_inputs": …}` on stdin and returns stdout as the prompt (new `render_adapter.py`
   fixture); honors `cwd`, the timeout, and raises on non-zero exit (reuse `fail_adapter`).
   `build_run_function` raises a clear error for a render-only target (Path B).
3. **CLI** (`test_run_eval_cli.py`): `render-artifact` on a render-capable `command_adapter`
   prints the assembled prompt (rc 0); on a `command_adapter` **without** `render_command`
   returns rc 2 with an actionable message; on a `render_command` that **exits non-zero**
   returns rc 2 with `render_command failed` and no traceback (reuse `fail_adapter`);
   `prompt_file` rendering and all existing branches stay green.
4. **Regression:** full `evals/tests` suite + repo skill linter, output pasted in the PR.

**Acceptance-criteria mapping**

- *Render-capable `command_adapter` runs end-to-end under `in_claude_code`, no key* →
  `render-artifact` renders it (test 3) and Path A's documented flow feeds `$RENDERED` to
  the execute-subagent (SKILL.md §Path A); no code path requires a key to render.
- *`render-artifact` returns the assembled prompt deterministically (no model)* → tests 2–3.
- *`prompt_file` and Path B unchanged* → §4 boundary + tests 1–3 keep existing branches green.
- *Skill/docs describe the `command_adapter` subscription path* → SKILL.md change.

## 8. Consumer contract note (presales-sqnce)

presales already exposes `eval-adapter --step X --render` that prints the assembled prompt.
To adopt: set `target.render_command` to that argv. Its stdin must accept
`{"prompt_inputs": {…}}` and its stdout must be the assembled prompt only (no answer, no
log noise). No change to presales is required by this repo; this note records the contract
the consumer must satisfy.
