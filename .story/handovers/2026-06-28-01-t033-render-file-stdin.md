# T-033 — command adapters EAGAIN on large payloads: feed via regular-file stdin

Date: 2026-06-28
Ticket: T-033 (complete)
Branch: t033-render-file-stdin → merged to main locally
Plan (deleted before merge): `docs/superpowers/plans/2026-06-28-T-033-render-file-stdin.md`

## What surfaced this

The presales-sqnce Path-A graded re-baseline could not render large design-brief cases.
The framework's render-artifact step (`render_command_adapter`) feeds the project's
render adapter (`node src/cli/index.js eval-adapter --render`, which reads fd 0 with a
synchronous `readFileSync(0)`) its `{prompt_inputs}` payload. On a ~81 KB case the
adapter died with `EAGAIN: resource temporarily unavailable` — persistently, 4/4
retries, and the Codex reviewers had hit the same. The proven manual workaround was a
shell redirect (`eval-adapter --render < case-inputs.json`), which renders first-try.

## Root cause (confirmed in code)

`run_command_adapter` and `render_command_adapter` in
`skills/prompt-evals-setup/framework/evals/artifact_runner.py` fed the child via
`subprocess.run(..., input=json.dumps(...))`. `input=` hands the child a **pipe** on
fd 0. A synchronous read of a *pipe* fd (Node `readFileSync(0)`) returns EAGAIN when the
payload is large in the WSL/Node sandbox. The redirect workaround works because a shell
`<` makes fd 0 a **regular file**, which is always read-ready and never EAGAINs. Same
bytes on fd 0; only the fd *type* differs.

This is a framework robustness bug, not just an adapter bug: the framework chose the pipe.
The adapter side (`index.js`) lives in presales-sqnce and is out of scope here.

## Fix

Added `_run_adapter_with_file_stdin(argv, payload, *, cwd, timeout)`: writes the payload
to a `tempfile.TemporaryFile()`, `seek(0)`, and passes it as `stdin=` (a regular-file fd).
Routed both adapter functions through it. The `(JSON on stdin → text on stdout)` contract,
`capture_output`/`check`/`timeout` semantics (`CalledProcessError`/`TimeoutExpired`) are
unchanged; no project adapter needs to change. This generalizes the proven `< file`
workaround into the framework for every consumer.

## Verification (actual output)

- New RED→GREEN regression tests assert fd 0 is a regular file (not a FIFO) for both
  functions; they failed `'fifo' != 'regular'` before the fix, pass after.
- Framework suite: 217 tests OK (was 215 + 2 new). skill_lint: 6 skills, 0 errors,
  0 warnings. tools/tests 14 OK; dev-workflow-init 15 OK; prompt-engineering-improve 53 OK.
- Two independent review rounds (correctness+cleanup; adversarial). Round 2 empirically
  stress-tested 10 MB payloads, 50 concurrent threads, 20 timeout firings — all safe
  (per-call temp file, seek flushes before child read, `with` cleans up fds on
  error/timeout). Cleanups applied: dropped a redundant `list(argv)`; trimmed test
  docstrings to point at the helper.

## Deliberate trade-off (not a bug)

The new path needs a writable `TMPDIR`; the old pipe path needed no disk. Accepted: the
only alternative is falling back to a pipe, which *is* the EAGAIN bug. A broken `TMPDIR`
fails loudly as a per-case execution error, and every eval run already writes run
artifacts to disk, so this is not a practical regression.

## Not done here (presales-sqnce side)

- The 500-char clarifying-question overflow (design-brief case 4 / q-3) is a presales-sqnce
  dataset issue; their q-3 truncation + relock handles it. Not a framework bug.
- 0/21 package/package-qa cases carry a `## Solution Architecture`; that retrofit was
  deferred by the session owner (proportional scope). Unrelated to this fix.

## Follow-ups

- Version bumped 0.6.1 → 0.6.2 (patch) on main.
- See lesson L-015 (pipe-stdin EAGAIN → file-stdin).
