# Plan: T-033 — feed command adapters a regular-file stdin (fix large-payload EAGAIN)

Status: In progress

## Problem (root cause, confirmed against code)

`artifact_runner.py` invokes both command adapters with
`subprocess.run(..., input=json.dumps(...))`. `input=` gives the child a **pipe** on
fd 0. An adapter that reads fd 0 synchronously (Node `readFileSync(0)`) gets
`EAGAIN: resource temporarily unavailable` on a large pipe payload in the WSL/Node
sandbox — persistent (presales design-brief case 2, ~81 KB, 4/4 failures).

A regular-file fd is always read-ready and never EAGAINs. The proven manual workaround
was a shell redirect (`< case-inputs.json`), i.e. fd 0 = regular file. This generalizes
that into the framework.

Affected functions (both in `evals/artifact_runner.py`):
- `render_command_adapter` (Path A render; called by `run_eval.py:311`)
- `run_command_adapter` (Path B; called by `build_run_function`)

## Fix

Add a private helper `_run_adapter_with_file_stdin(argv, payload, *, cwd, timeout)` that
writes `payload` to a `tempfile.TemporaryFile()` and passes it as `stdin=` (regular file
fd) instead of `input=` (pipe). Route both functions through it. Contract preserved:
same bytes on fd 0, `capture_output=True`, `text=True`, `check=True`, `timeout` ->
`CalledProcessError` / `TimeoutExpired` unchanged.

## TDD

1. New fixture `stdin_kind_adapter.py`: consume stdin JSON, then `os.fstat(0)` and print
   `"fifo"` / `"regular"` / `"other"`.
2. RED tests (one per function) asserting the adapter sees `"regular"`. With the current
   `input=` code they return `"fifo"` -> fail.
3. Implement the helper -> GREEN.
4. Existing tests (stdout, non-zero-exit -> CalledProcessError, timeout -> TimeoutExpired)
   must stay green.

## Verify

- Framework suite: `(cd skills/prompt-evals-setup/framework && python3 -m unittest discover -s evals/tests -t .)`
- Skill lint + the other offline suites listed in AGENTS.md.
- Two independent reviews (code-review + report-only second model), address findings.

## Close-out

Handover + lesson (pipe-stdin EAGAIN -> file-stdin), delete this plan, local-merge to
main, rerun verification, delete branch, bump 0.6.1 -> 0.6.2.
