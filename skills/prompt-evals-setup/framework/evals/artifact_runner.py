"""Plugin-resident artifact runner (T-018).

A thin front-end over the existing live run path. It renders a prompt template (or
invokes a project command adapter) for each frozen case and routes the whole run
through ``live_run.run_evaluation`` — so assertion gating, the report writers, and
the ``baseline``/``variance_runs`` analysis are inherited verbatim rather than
re-implemented. See spec §3 (one unified run path; no capability regression).

Deterministic and offline-testable: the executor (prompt -> output) and the judge
client are injected, so tests exercise the full path with no network.
"""

from __future__ import annotations

import json
import inspect
import subprocess
import tempfile
from typing import Callable

from evals import config
from evals.artifacts import EvalSpec
from evals.evaluator.run import RunFunction
from evals.evaluator.templates import render
from evals.live_run import run_evaluation
from evals.promptprep import check_placeholders

# An executor turns a fully-rendered prompt into the model's output text. The keyed
# CLI wires an AnthropicClient call here; tests pass a pure function. New executors accept
# the optional output schema; legacy one-arg executors remain supported when no schema is set.
SchemaExecutor = Callable[[str, dict | None], str]
LegacyExecutor = Callable[[str], str]
Executor = SchemaExecutor | LegacyExecutor


def render_prompt_file(spec: EvalSpec, prompt_inputs: dict) -> str:
    """Render a case's prompt, reusing promptprep + templates (no duplicated logic)."""
    if spec.prompt_file is None:
        raise ValueError("render_prompt_file requires a prompt_file-mode eval spec")
    template = spec.prompt_file.read_text(encoding="utf-8")
    check_placeholders(template, prompt_inputs)  # raises MissingPlaceholderError; warns on unused
    return render(template, **prompt_inputs)


def _run_adapter_with_file_stdin(
    argv: list[str], payload: str, *, cwd: str, timeout: float | None
) -> str:
    """Run ``argv`` feeding ``payload`` on a regular-file stdin, returning captured stdout.

    Why a temp file rather than ``subprocess.run(input=…)``: ``input=`` hands the child a
    *pipe* on fd 0. An adapter that reads fd 0 synchronously (e.g. Node's
    ``readFileSync(0)``) gets ``EAGAIN: resource temporarily unavailable`` on a large pipe
    payload in some sandboxes (observed persistently under WSL for ~80 KB renders). A
    regular-file fd is always read-ready, so the same bytes on fd 0 are delivered
    reliably. The adapter contract (JSON on stdin, text on stdout) is unchanged; only the
    fd *type* differs. ``capture_output``/``check``/``timeout`` semantics match ``input=``:
    a non-zero exit raises ``CalledProcessError`` and a timeout raises ``TimeoutExpired``.
    """
    with tempfile.TemporaryFile() as stdin_file:
        stdin_file.write(payload.encode("utf-8"))
        stdin_file.seek(0)
        proc = subprocess.run(
            list(argv),
            stdin=stdin_file,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
            timeout=timeout,
        )
    return proc.stdout


def run_command_adapter(
    spec: EvalSpec, case: dict, *, timeout: float | None = config.ADAPTER_TIMEOUT_SECONDS
) -> str:
    """Invoke the project command adapter: case JSON on stdin, output text on stdout.

    ``timeout`` (seconds) bounds the subprocess so a hung adapter cannot block its
    worker thread forever; on expiry ``subprocess.run`` raises ``TimeoutExpired``,
    which the per-case run handler records as a case failure.

    The case JSON is fed on a regular-file stdin (not a pipe) so adapters that read fd 0
    synchronously do not EAGAIN on large payloads; see ``_run_adapter_with_file_stdin``.
    """
    if not spec.command:
        raise ValueError("run_command_adapter requires a command_adapter-mode eval spec")
    return _run_adapter_with_file_stdin(
        list(spec.command), json.dumps(case), cwd=str(spec.project_root), timeout=timeout
    )


def render_command_adapter(
    spec: EvalSpec, prompt_inputs: dict, *, timeout: float | None = config.ADAPTER_TIMEOUT_SECONDS
) -> str:
    """Run the render-only command: ``{"prompt_inputs": …}`` on stdin, the assembled
    prompt (model *input*, not an answer) on stdout. Deterministic; no model call.

    ``timeout`` bounds the subprocess; a non-zero exit raises ``CalledProcessError`` and a
    timeout raises ``TimeoutExpired`` (the ``render-artifact`` CLI turns both into a clean
    rc-2 error so a render failure is loud, never silent).
    """
    if not spec.render_command:
        raise ValueError(
            "render_command_adapter requires a command_adapter-mode eval spec with "
            "target.render_command"
        )
    return _run_adapter_with_file_stdin(
        list(spec.render_command),
        json.dumps({"prompt_inputs": prompt_inputs}),
        cwd=str(spec.project_root),
        timeout=timeout,
    )


def build_run_function(spec: EvalSpec, *, executor: Executor | None = None) -> RunFunction:
    """Return the ``RunFunction`` that ``run_evaluation`` executes per case.

    Prompt-file mode renders the prompt and feeds it to ``executor`` (required, since
    the rendered prompt is the executor's *input*, not gradeable output).
    Command-adapter mode runs the project command and grades its stdout (no executor).
    """
    mode = spec.target.mode
    if mode == "prompt_file":
        if executor is None:
            raise ValueError("prompt_file mode requires an executor callable (prompt -> output)")
        output_schema = spec.target.output_schema
        run_executor = _normalize_executor(executor, output_schema)

        def _run_prompt(prompt_inputs: dict) -> str:
            prompt = render_prompt_file(spec, prompt_inputs)
            return run_executor(prompt, output_schema)

        return _run_prompt

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

    raise ValueError(f"unknown target mode: {mode!r}")


def _normalize_executor(executor: Executor, output_schema: dict | None) -> SchemaExecutor:
    """Normalize legacy and schema-aware executors to the new two-arg contract."""
    if _executor_accepts_schema(executor):
        return executor
    if output_schema is not None:
        raise ValueError(
            "target.output_schema requires an executor callable accepting "
            "(prompt, output_schema)"
        )

    def _legacy_adapter(prompt: str, _output_schema: dict | None = None) -> str:
        return executor(prompt)

    return _legacy_adapter


def _executor_accepts_schema(executor: Callable) -> bool:
    """Return whether ``executor(prompt, output_schema)`` is a valid call shape."""
    try:
        signature = inspect.signature(executor)
    except (TypeError, ValueError):
        return True
    params = list(signature.parameters.values())
    if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params):
        return True
    positional = [
        param
        for param in params
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2


def evaluate_artifact(
    spec: EvalSpec,
    *,
    judge_client,
    run_function: RunFunction | None = None,
    executor: Executor | None = None,
    run_label: str | None = None,
    baseline: dict | None = None,
    variance_runs: list[dict] | None = None,
) -> dict:
    """Run one artifact eval through ``run_evaluation`` with project-relative paths.

    Supplies the project's ``cases.json`` and ``runs/`` explicitly so the run never
    depends on the framework's vendored ``config.DATASETS_DIR``/``RUNS_DIR`` defaults.
    """
    if run_function is None:
        run_function = build_run_function(spec, executor=executor)
    return run_evaluation(
        judge_client=judge_client,
        run_function=run_function,
        dataset_file=str(spec.cases_file),
        runs_dir=str(spec.runs_dir),
        assertions=spec.assertions,
        assertion_policy=spec.assertion_policy,
        extra_criteria=spec.extra_criteria,
        process_criteria=spec.process_criteria,
        run_label=run_label,
        baseline=baseline,
        variance_runs=variance_runs,
    )
