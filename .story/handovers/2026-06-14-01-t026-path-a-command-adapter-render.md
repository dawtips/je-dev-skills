# Session handover — T-026: Path A renders `command_adapter` targets (PR #12, closes #11)

## What this session did

Shipped T-026 (GitHub issue #11): the subscription execution path (**Path A**,
`EXECUTION_MODE=in_claude_code`, no API key) can now run `command_adapter` targets, not just
`prompt_file` ones. PR #12, Codex-reviewed across spec → plan → implement, adversarially
reviewed at the spec gate, user-approved at the spec gate.

### The design (durable detail in the spec)
Added an optional `target.render_command` (argv) — a **render-only** invocation whose
**stdout is the assembled prompt** (the model's *input*), distinct from the existing
`command_adapter` `command` whose stdout is the gradeable *answer*. Path A's `render-artifact`
step runs `render_command` (`{"prompt_inputs": …}` on stdin, no model), then the
execute-subagent answers `$RENDERED` exactly like `prompt_file`. Unblocks **presales-sqnce**,
which uses `command_adapter` to grade its real CLI prompt assembly (design decision D4) and
so could not run on the subscription. Rejected the issue's "reuse `command` + `--render`
convention" alternative as brittle/ambiguous (one stdout, two meanings).

Spec: `docs/superpowers/specs/2026-06-14-path-a-command-adapter-render-spec.md` (durable).

### Code (TDD, all offline, no key)
- `evals/artifacts.py` — `TargetSpec.render_command`, `EvalSpec.render_command`,
  `_validate_argv`; `_validate_target` validates any present argv **before** the
  at-least-one presence check (keyed on `is None`), and rejects `command`/`render_command`
  in `prompt_file` mode.
- `evals/artifact_runner.py` — `render_command_adapter` (render-only subprocess, bounded by
  `ADAPTER_TIMEOUT_SECONDS`); `build_run_function` raises for a render-only target on Path B.
- `evals/run_eval.py` — `render-artifact` renders `command_adapter` via `render_command`,
  turning `CalledProcessError`/`TimeoutExpired` into a clean rc-2 error; `prompt_file` branch
  unchanged (loud `MissingPlaceholderError`). `_render_only_path_b_error` preflight gives the
  keyed CLI a clean rc-2 instead of a traceback for a render-only target.
- `skills/prompt-evals-run/SKILL.md` — Path A precondition + render-failure handling: capture
  stdout only on success (stderr kept separate so a warning never pollutes the prompt); a
  `command_adapter` `render_command` failure writes a **complete** synthetic score-1 verdict
  (verbatim `test_case`, `"output": ""`, `"assertion_gate": null`) so `aggregate` scores it,
  not aborts; a `prompt_file` config error stays loud.
- Tests: `test_artifacts.py`, `test_artifact_runner.py` (+ `render_adapter.py` fixture),
  `test_run_eval_cli.py`, `test_aggregate.py` (render-failure verdict survives aggregation).

### Review journey (the loop worked — every round caught a real defect)
- **Codex spec loop (3 rounds):** missing branch-committed `.story/tickets/T-026.json`;
  Path A render-failure recording unspecified; `error`/`meta.errors` not achievable in Path A
  `aggregate` (scoped to preserved `reasoning`/`weaknesses`).
- **Adversarial spec review (1 must-fix P1):** a verdict-**only** render-failure file would
  abort the whole run (Path A `aggregate.load_results` needs `test_case`; `--dataset` triggers
  `_validate_results_match_dataset`) — fixed to a complete record + an offline `aggregate` test.
- **Codex plan loop (3 rounds):** validate `command` whenever present; branch render recovery
  by error (not mode); reject `command` in `prompt_file`; validate present argv before the
  presence check; separate stdout/stderr.
- **Codex impl (1) + closeout (2):** render-only target on Path B preflight; mark ticket
  complete; delete the plan; add this handover.

This **reaffirms [[L-008]]** (isolate only transient errors; deterministic config/contract
errors fail loudly — exactly the `command_adapter`-recover vs `prompt_file`-loud split) and
**[[L-009]]** (Codex probes one edge case per round on a loosened guard/parser — the
validation and render-failure branches took several rounds each, every round a fresh shape).
New operational learning recorded as [[L-010]].

## State at handover
- PR #12 on `feat/11-cmd-adapter-render`; awaiting the closeout-commit fresh 👍 to merge.
- Verification (worktree): framework **215 tests OK**, skill linter **14/0/0**, tools/tests
  **21 OK**. (Host note: `python3` is the broken Store shim here; ran with `python`.)
- Ephemeral plan deleted: `docs/superpowers/plans/2026-06-14-T-026-path-a-cmd-adapter-render.md`.
- T-026 marked `complete` (2026-06-14).

## Notes for next session
- Post-merge: bump the plugin version (minor — new user-visible capability) in **both**
  `.claude-plugin/plugin.json` and `marketplace.json`, direct commit to `main`.
- Consumer follow-up: presales-sqnce sets `target.render_command` to its
  `eval-adapter --step X --render` argv; its stdin must accept `{"prompt_inputs": …}` and its
  stdout must be the assembled prompt only.
- Possible future ticket: thread `render_command` through `scaffold-artifact` (deliberately
  out of scope here); Path B "render then keyed-execute" symmetry (out of scope; would change
  Path B).
