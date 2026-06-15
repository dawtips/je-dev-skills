"""Plugin-resident eval artifacts: scaffold + spec loader + path resolution (T-018).

Target projects keep only lightweight artifacts under ``evals/<name>/``:

  eval.json   - config/spec: target mode, prompt ref / command adapter, judge config
  cases.json  - frozen dataset (created later by ``generate-artifact``)
  runs/       - generated outputs/grades/reports (gitignored; kept by ``.gitkeep``)

The shared runner/grader/aggregation/reporting machinery stays plugin-owned under
``${CLAUDE_PLUGIN_ROOT}/skills/prompt-evals-setup/framework/evals`` and reads these
artifacts; it is never copied into the target. See
``docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from evals.output_schema import parse_strict_json, validate_output_schema

VALID_MODES = ("prompt_file", "command_adapter")


def resolve_project_root(eval_json: Path) -> Path:
    """Resolve ``<project>`` from ``<project>/evals/<name>/eval.json``.

    Enforces the prescribed layout: the eval dir's parent must be named ``evals``.
    Raises a clear ``ValueError`` (not an opaque ``IndexError``, and not a silently
    wrong directory) for any other shape.
    """
    eval_dir = eval_json.parent
    if eval_dir.parent.name != "evals" or len(eval_dir.parents) < 2:
        raise ValueError(
            "eval.json must live at <project>/evals/<name>/eval.json; got a path that "
            f"does not follow that layout: {eval_json}"
        )
    return eval_dir.parents[1]

_GITIGNORE_RUNS = "evals/*/runs/*"
_GITIGNORE_KEEP = "!evals/*/runs/.gitkeep"
_GITIGNORE_HEADER = "# prompt-evals generated run artifacts"


@dataclass(frozen=True)
class TargetSpec:
    """How a single eval produces output: a prompt template or a project command."""

    mode: str
    prompt_file: str | None = None  # project-root-relative path (prompt_file mode)
    command: list[str] | None = None  # argv for the adapter subprocess (command_adapter mode)
    render_command: list[str] | None = None  # argv for a render-only adapter invocation (Path A)
    output_schema: dict | None = None  # optional JSON Schema for prompt-under-test output


@dataclass(frozen=True)
class EvalSpec:
    """A loaded ``eval.json`` with deterministic path resolution.

    Per the prescribed layout ``<project>/evals/<name>/eval.json``:
      - ``eval_dir`` is the directory holding ``eval.json``,
      - ``project_root`` is ``eval_dir.parents[1]``,
      - ``cases_file`` / ``runs_dir`` resolve relative to ``eval_dir``,
      - ``prompt_file`` / command cwd resolve relative to ``project_root``.
    """

    name: str
    eval_json: Path
    target: TargetSpec
    cases_file_rel: str = "cases.json"
    runs_dir_rel: str = "runs"
    extra_criteria: str | None = None
    process_criteria: str | None = None
    assertions: list[dict] = field(default_factory=list)
    assertion_policy: str = "gate_mandatory"
    # Optional keyed dataset-generation params (filled by create-dataset before
    # `generate-artifact` freezes cases.json). None/empty until the developer sets them.
    generation: dict = field(default_factory=dict)

    @property
    def eval_dir(self) -> Path:
        return self.eval_json.parent

    @property
    def project_root(self) -> Path:
        return resolve_project_root(self.eval_json)

    @property
    def cases_file(self) -> Path:
        return self.eval_dir / self.cases_file_rel

    @property
    def runs_dir(self) -> Path:
        return self.eval_dir / self.runs_dir_rel

    @property
    def prompt_file(self) -> Path | None:
        if self.target.prompt_file is None:
            return None
        return self.project_root / self.target.prompt_file

    @property
    def command(self) -> list[str] | None:
        return self.target.command

    @property
    def render_command(self) -> list[str] | None:
        return self.target.render_command


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
    # Validate any PRESENT argv first, so an explicit empty list ([]) raises the
    # non-empty-list error rather than tripping the at-least-one presence check below
    # (which keys on ``is None``, not falsiness).
    if command is not None:
        _validate_argv(command, "target.command")
    if render_command is not None:
        _validate_argv(render_command, "target.render_command")
    if mode == "prompt_file":
        if not prompt_file:
            raise ValueError("prompt_file mode requires target.prompt_file")
        if command is not None:
            raise ValueError("target.command is only valid in command_adapter mode")
        if render_command is not None:
            raise ValueError("target.render_command is only valid in command_adapter mode")
    if mode == "command_adapter" and command is None and render_command is None:
        raise ValueError(
            "command_adapter mode requires target.command or target.render_command"
        )


def load_eval_spec(eval_json_path: str | Path) -> EvalSpec:
    """Load and validate an ``eval.json``, resolving all artifact paths."""
    path = Path(eval_json_path).resolve()
    resolve_project_root(path)  # validate the prescribed layout up front (clear error)
    data = parse_strict_json(path.read_text(encoding="utf-8"))
    target_data = data.get("target") or {}
    mode = target_data.get("mode")
    prompt_file = target_data.get("prompt_file")
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
        cases_file_rel=data.get("cases_file", "cases.json"),
        runs_dir_rel=data.get("runs_dir", "runs"),
        extra_criteria=data.get("extra_criteria"),
        process_criteria=data.get("process_criteria"),
        assertions=data.get("assertions", []),
        assertion_policy=data.get("assertion_policy", "gate_mandatory"),
        generation=data.get("generation") or {},
    )


def scaffold_eval_artifacts(
    project_root: str | Path,
    name: str,
    *,
    mode: str,
    prompt_file: str | None = None,
    command: list[str] | None = None,
    output_schema: dict | None = None,
) -> EvalSpec:
    """Create the ``evals/<name>/`` artifact layout without copying the framework.

    Idempotent: an existing ``eval.json`` is left untouched, ``runs/.gitkeep`` is
    preserved, and the ``.gitignore`` run-artifact entries are inserted only once.
    """
    _validate_target(mode, prompt_file, command)
    root = Path(project_root)
    eval_dir = root / "evals" / name
    (eval_dir / "runs").mkdir(parents=True, exist_ok=True)
    gitkeep = eval_dir / "runs" / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")

    target: dict = {"mode": mode}
    if mode == "prompt_file":
        target["prompt_file"] = prompt_file
    else:
        target["command"] = list(command)
    if output_schema is not None:
        target["output_schema"] = validate_output_schema(output_schema)

    eval_json = eval_dir / "eval.json"
    if not eval_json.exists():
        payload = {
            "name": name,
            "target": target,
            "cases_file": "cases.json",
            "runs_dir": "runs",
            "extra_criteria": None,
            "process_criteria": None,
            "assertions": [],
            "assertion_policy": "gate_mandatory",
            "generation": {
                "task_description": "",
                "prompt_inputs_spec": {},
                "num_cases": 20,
            },
        }
        eval_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    _ensure_gitignore(root)
    return load_eval_spec(eval_json)


def _ensure_gitignore(project_root: Path) -> None:
    """Append the run-artifact ignore entries once, preserving existing content."""
    gitignore = project_root / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    additions = [line for line in (_GITIGNORE_RUNS, _GITIGNORE_KEEP) if line not in lines]
    if not additions:
        return
    block: list[str] = []
    if lines and lines[-1] != "":
        block.append("")
    block.append(_GITIGNORE_HEADER)
    block.extend(additions)
    gitignore.write_text("\n".join(lines + block) + "\n", encoding="utf-8")
