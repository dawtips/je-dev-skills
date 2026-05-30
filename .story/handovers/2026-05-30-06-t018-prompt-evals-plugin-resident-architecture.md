# Session 2026-05-30 — T-018 prompt-evals plugin-resident architecture

## Summary
Took over T-018 after an independent review of the ticket, its spec, and the original
plan. Revised the spec, rewrote the plan, and implemented the refactor: prompt-evals no
longer vendors the framework into `./evals` by default. New target projects keep only
lightweight `evals/<name>/{eval.json,cases.json,runs/}` artifacts; the runner/grader/
aggregation/reporting machinery stays plugin-owned and reads those artifacts. Branch:
`t018-prompt-evals-plugin-resident`. Plan (now deleted):
`docs/superpowers/plans/2026-05-30-t018-prompt-evals-plugin-resident-architecture.md`.

## The two review findings that shaped the work
The independent review found the original spec/plan were framed as if T-018 were the
*upstream* dependency of the eval live-path work (T-013/T-014/T-019). But those tickets had
already **shipped and merged** (`86fa682`) against the vendored `./evals` layout. Two
corrections drove everything:
1. **Retrofit, not precursor.** T-018 lands *after* the live-path work and must retrofit a
   plugin-resident layout *under* an already-wired run path.
2. **One unified run path, no regression.** The naive refactor would add a second, thinner
   artifact runner that silently drops assertion gating / K-run variance / run-delta. The
   spec now mandates routing the artifact path through the **existing**
   `live_run.run_evaluation` seam so those live-path features are inherited verbatim.

## Decided / built
1. **Spec rewritten** (`docs/superpowers/specs/2026-05-30-prompt-evals-plugin-resident-architecture-spec.md`):
   real `skill-creator` comparison table (§2), the unified-run-path decision (§3),
   `eval.json` schema + deterministic path resolution (§4.1), Claude-Code-only v1 with a
   CLI-compatible layout (§6), and a corrected retrospective framing (§1, §8, §9).
2. **Two new deterministic, offline-tested modules** at the framework top level:
   - `evals/artifacts.py` — `EvalSpec`/`TargetSpec`, `load_eval_spec`,
     `scaffold_eval_artifacts`, `resolve_project_root` (enforces the prescribed
     `<project>/evals/<name>/eval.json` layout), idempotent `.gitignore` insertion.
   - `evals/artifact_runner.py` — `render_prompt_file` (reuses `promptprep`+`templates`),
     `run_command_adapter` (case JSON on stdin), `build_run_function` (mode dispatch),
     `evaluate_artifact` (routes through `run_evaluation` with project-relative
     `dataset_file`/`runs_dir`, so assertions/variance/run-delta come for free).
3. **Additive CLI** in `evals/run_eval.py`: `scaffold-artifact`, `generate-artifact`,
   `render-artifact`, `evaluate-artifact`, `evaluate-artifact-variance`. **Legacy
   `generate`/`evaluate`/`evaluate-variance` untouched** — already-vendored projects keep
   working.
4. **Skill docs repointed** at the artifact layout: `prompt-evals-setup` (scaffold default
   + migration note for vendored projects), `-create-dataset` (`generate-artifact`),
   `-run` (Path A `render-artifact` + `aggregate --runs-dir`; Path B `evaluate-artifact`).
   Cross-spec annotations added to `PROMPT_EVAL_FRAMEWORK_SPEC.md` (superseded default) and
   the eval-live-path spec §2 (sequencing resolved-after-the-fact). `README.md` line updated.

## Verification (actual output)
- `python3 tools/skill_lint.py --root .` → `11 skills | 0 errors | 0 warnings`
- `python3 -m unittest discover -s tools/tests -t tools` → `Ran 12 tests ... OK`
- evals framework suite → `Ran 145 tests ... OK` (baseline was 99; +46 new). The trailing
  `ERROR: no verdict JSON files` is an existing negative test's expected stdout.
- workflow-design-validate suite → `PASS` (12/12 dimensions).

Two independent adversarial review rounds were run (multi-dimension reviewers + per-finding
verification). Round 1 confirmed 1 critical + several important findings (all fixed: a
`parents[1]` IndexError guard, a hoisted judge client in the variance loop, a missing
`cases.json` guard, plus 8 added tests). Round 2 confirmed the layout guard was still too
permissive (silently resolved a wrong project root for non-prescribed paths); tightened
`resolve_project_root` to require the `evals/` parent and added an explicit rejection test.

## Conventions / gotchas
- Run the artifact CLI from the framework dir with **absolute** project paths
  (`(cd "$PE" && python3 -m evals.run_eval <cmd> "$EVAL")`). Empirically, the real `evals`
  package (it has `__init__.py`) always wins over a project `evals/` data dir (a namespace
  portion), so PYTHONPATH-from-project is also safe — but the `cd $PE` form is the clean one.
- Each frozen case needs `task_description`, `prompt_inputs`, and `solution_criteria`
  (`grade()` reads all three).
- `config.DATASETS_DIR`/`RUNS_DIR` stay as legacy relative defaults; the artifact front-end
  passes explicit project-relative paths and never relies on them.
- `prompt_file` run-function renders then calls an injected executor — the rendered prompt
  is the executor's input, not gradeable output.

## Recommended next
- Optional follow-ups (deferred, not blocking): a packaged headless/CI CLI (spec §6), and a
  `--project-root` override for non-standard layouts (spec §4.1). Both are additive.
