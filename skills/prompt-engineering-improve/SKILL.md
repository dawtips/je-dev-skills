---
name: prompt-engineering-improve
description: This skill should be used when the user asks to "improve my prompt with evals", "iterate on my prompt", "make my prompt measurably better", "run the improvement loop", "optimize my prompt against the dataset", or wants an eval-driven iterate->measure->diagnose->rewrite loop with explicit stopping rules. It orchestrates the existing ./evals framework; every numeric decision (delta, best version, stop verdict, diagnosis tally) is computed by a deterministic helper.
argument-hint: "[prompt name under evals/prompts_under_test, e.g. meal-plan]"
allowed-tools: Bash, Read, Write, Edit, Glob
version: 0.1.0
---

# Prompt Engineering: Improve (the eval-driven loop)

Drive an **iterate -> measure -> diagnose -> rewrite** loop that makes a prompt
*measurably* better, with explicit, **deterministically-evaluated** stopping rules. This
skill **orchestrates** the eval framework - it never reimplements it. Every numeric
decision (per-round delta, running-best version, the continue/stop verdict, the diagnosis
tally, the `EXTRA_CRITERIA` freeze) is computed by `scripts/improve_step.py`; the model's
only jobs are **naming the dominant failure theme** and **the rewrite**.

This SKILL is a table of contents. **Load each reference only at its step** - never all
four up front.

## Preconditions

- `./evals` exists (else stop and route to `/je-dev-skills:prompt-evals-setup`).
- A **frozen dataset** exists in `evals/datasets/` (else route to
  `/je-dev-skills:prompt-evals-create-dataset`). This skill owns **no** eval engine and
  does **not** define success criteria or build datasets.
- The measurement substrate determines which execution path is available. If
  `evals/config.py` has `EXECUTION_MODE`, `evals/aggregate.py` exists, and
  `prompt-evals-run` itself documents the substrate path, the no-key path is available.
  If those files or instructions are absent, use the keyed fallback or stop and install
  the execution substrate first; do not claim no-key execution is available.
- The prompt-under-test lives at `evals/prompts_under_test/<name>.current.md`. On first
  use, migrate any custom `run_prompt` per the substrate's migration note (extract the
  prompt text to `<name>.current.md`; map system/user content to subagent options; route
  raw `messages.create`/`max_tokens`/tools to the keyed fallback; **show the diff and get
  explicit confirmation** before the first eval).

## Execution paths (from the architecture spec - consumed, not redefined)

- **No-key path (only when the execution substrate is installed,
  `EXECUTION_MODE=in_claude_code`):** follow the substrate-updated `prompt-evals-run`
  procedure, which dispatches execute+grade **subagents** per case (session auth, no API
  key), then runs
  `python -m evals.aggregate --run-label <label> --verdicts-dir <dir> --dataset <path>`
  to write `evals/runs/<label>/{output.json,output.html}`. **Single-shot only** (subagents
  can't nest). This branch does not ship that substrate; if the local `prompt-evals-run`
  file only documents `ANTHROPIC_API_KEY`, use the keyed fallback below.
- **Keyed fallback (`EXECUTION_MODE=anthropic_api`, headless/CI):** `python3 -m evals.run_eval evaluate`
  runs `run_evaluation` in-process with `ANTHROPIC_API_KEY`; supports agentic prompts.

## Loop parameters (one home)

The five loop params live as a **constants block at the top of `evals/run_eval.py`**;
`pass_threshold` references `config.PASS_THRESHOLD` (7). `improve_step.py` reads them
from the loop-state JSON and stamps the resolved values into each `delta.json` + the
final report. Defaults: `pass_rate_target=0.80`, `max_rounds=3`, `epsilon=0.25`,
`diminishing_return_rounds=2`, `regression_band=0.5`.

## Token cost & optional cheap subset (optimization)

One full evaluation is about `2N` model calls (N execute + N grade); a loop is baseline +
N re-evals + 1 held-out, about `(N+2)` full evaluations (single-shot; agentic execute is
unbounded per case on the keyed path). **Optional:** to cut recurring cost, mid-loop
*diagnosis* may run against a **deterministically sampled K-case subset** written from
the frozen dataset (a helper writes the subset and passes it as `--dataset`); always run
the **full** frozen set at every decision point (delta / stop verdict / version
selection). This is an optimization, not required.

## One round

```text
baseline:  prompt-evals-run -> evals/runs/improve-<name>-round-NN/output.json
diagnose:  improve_step.py tallies mandatory-fails + %-per-theme -> model names the dominant theme
   |- criteria problem? (diagnosis.md guard) -> STOP, route to prompt-evals-create-dataset
select:    map theme -> next ladder rung (diagnosis.md table)
rewrite:   follow rewrite-procedure.md + the diagnosis -> <name>.vN+1.md -> copy into <name>.current.md
re-eval:   prompt-evals-run on the SAME frozen dataset -> new output.json
delta:     improve_step.py -> delta + best + continue/stop verdict
```

### Step detail

1. **Baseline.** Run `/je-dev-skills:prompt-evals-run` with
   `run_label=improve-<name>-round-00` against the frozen dataset. Build the **loop-state
   JSON** (`evals/improve/<name>/<timestamp>/loop-state.json`): the resolved `params`,
   the frozen `extra_criteria` + its hash (`improve_step.py`'s `extra_criteria_hash`),
   `current_version`, and an empty `rounds` list.
2. **Diagnose and record the completed round.** Read
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`. Run
   the helper to get the tally:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts/improve_step.py \
     --output-json evals/runs/improve-<name>-round-NN/output.json \
     --loop-state evals/improve/<name>/<timestamp>/loop-state.json \
     --delta-out evals/improve/<name>/<timestamp>/round-NN/delta.json \
     --check-freeze
   ```
   Act on the helper's exit code even for the baseline: exit 1 means the baseline already
   hit a stopping rule, so finalize without rewriting; exit 2 means bad input or freeze
   violation. If the loop continues, append this completed round's
   `{version, avg, pass_rate, technique, decision, run_dir}` to `rounds` before selecting a
   rewrite. Use the tally (mandatory-fail count, %-per-theme) to **name the dominant theme**.
   Apply the criteria-vs-prompt guard: if it's a criteria problem, **STOP** and route to
   `prompt-evals-create-dataset`.
3. **Select.** Map the dominant theme -> the minimum ladder rung (diagnosis.md table +
   priority/tie-break).
4. **Rewrite.** Read and follow
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`
   (it pulls in `techniques.md` + `anti-patterns.md`). Write the candidate to
   `evals/prompts_under_test/<name>.vN+1.md`, then **copy it into `<name>.current.md`**
   before re-measuring. Never change the `{placeholder}` set.
5. **Re-eval + decide.** Re-run `/je-dev-skills:prompt-evals-run` with
   `run_label=improve-<name>-round-NN` on the **same** frozen dataset. Update
   `current_version` to the candidate version, but leave `rounds` containing prior
   completed rounds only, then run `improve_step.py` again. After it writes `delta.json`,
   append that completed round's `{version, avg, pass_rate, technique, decision, run_dir}`
   to `rounds`. **Act on its verdict, do not recompute it:** exit 0 ->
   continue; exit 1 -> stop (a rule fired; the printed `verdict.rule` says which) and keep
   the printed `best.version`; exit 2 -> bad input or freeze violation.

## Hybrid control

- **Checkpointed (default):** pause each round with the diagnosis + chosen technique +
  delta + remaining weaknesses; ask the user continue / stop / adjust.
- **Auto, up to N rounds:** stream each delta; stop early on the helper's verdict; then
  return to checkpointed. Auto mode is no-key only when the execution substrate is present
  and an interactive session drives it (subagent dispatch). A genuinely unattended/CI
  auto-loop uses the keyed `anthropic_api` fallback and requires `ANTHROPIC_API_KEY`.

## Stopping rules (all evaluated by improve_step.py)

threshold (avg >= `pass_threshold`) . pass_rate (>= `pass_rate_target`) . regression
(> `regression_band` below best -> discard the round, keep best) . diminishing-returns
(delta < epsilon for K consecutive rounds) . budget cap (`max_rounds`). If several fire,
the helper reports the first by priority and you keep the **best** version.

## Held-out validation (final, at most once)

After the loop, run **once** against a separate, **independent** held-out dataset (distinct
scenarios - not a near-duplicate). Never use it for diagnosis/rewrite/selection. Before
any held-out run, `EXTRA_CRITERIA` is **frozen** - run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts/improve_step.py \
  --loop-state evals/improve/<name>/<timestamp>/loop-state.json \
  --check-freeze
```

Exit 2 means violation -> the held-out claim is forfeit; regenerate a held-out set. Record
`held_out_run_count` (must stay <= 1) in the final report. Absent held-out set -> mark
final validation **skipped, not failed**.

## Finalize (deterministic - never hand-serialized)

After the loop stops, write the final report **with the helper, not by hand**:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts/improve_step.py \
  --loop-state evals/improve/<name>/<timestamp>/loop-state.json \
  --final-report-out evals/improve/<name>/<timestamp>/final-report.json \
  --held-out-output-json evals/runs/improve-<name>-held-out/output.json \
  --check-freeze
```

This stamps the resolved loop params, the round-by-round trace, the winning `best.version`,
`held_out_run_count`, and the frozen `EXTRA_CRITERIA` hash into `final-report.json` (exit 2 =
freeze violation). Pass `--held-out-output-json` when held-out validation ran so the helper
checks the actual held-out report's `meta.extra_criteria`; omit it only when held-out was
skipped. The model never serializes these by hand.

## Output / trace

```text
evals/improve/<name>/<timestamp>/
  loop-state.json
  round-00-baseline/ { delta.json, diagnosis notes, run_dir -> ../../../runs/improve-<name>-round-00 }
  round-01/          { <name>.v2.md (or id), delta.json, technique, decision, run_dir -> ... }
  ...
  final-report.md    (round-by-round trace, winning version, held-out result or "skipped")
  final-report.json  (resolved loop params + held_out_run_count + EXTRA_CRITERIA hash)
```

Versioned prompt files (`<name>.vN.md` + `<name>.current.md`) + the trace + a final report.

## Definition of done

- The loop ran with each numeric decision produced by `improve_step.py` (not by hand).
- A winning version is named (the helper's `best.version`), with the trace + final report.
- If a criteria problem was found, the user was routed to `prompt-evals-create-dataset`
  and the loop stopped.
- Held-out validation ran at most once (recorded) or is marked "skipped, not failed".

## Offline check (no API key)

The deterministic helper is fully offline-tested:

```bash
cd ${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/scripts && \
  python3 -m unittest discover -s tests
```

## Cross-skill reference coupling (flag)

This skill reads `rewrite-procedure.md` + `techniques.md` + `anti-patterns.md` from
**`prompt-engineering-author`**, and its own `references/diagnosis.md` is read by
**`prompt-evals-run`**. These `${CLAUDE_PLUGIN_ROOT}` path dependencies are part of the
group contract - the files cannot move/rename without updating every reader.
