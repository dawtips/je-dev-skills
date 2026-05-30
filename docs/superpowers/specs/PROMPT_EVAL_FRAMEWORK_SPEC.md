# Prompt Evaluation Framework — Specification & Setup Guide

A reusable, **invocable** specification for adding LLM-graded prompt/agent evaluation
to any project. It defines the architecture, the data contracts, the prescribed
folder layout, the configuration surface, and a step-by-step bootstrap procedure —
and it ships a working **Python reference implementation** under [`evals/` (bundled)](../skills/prompt-evals-setup/framework/evals/)
that a new project vendors and adapts.

> **How to use this spec.** If you are an agent setting up evaluation in a new
> project, follow §11 (Bootstrap Procedure). It is the runbook. Everything before
> it is the reference you consult while doing so.

---

## 1. Purpose

The framework answers one question: **"Is my prompt good enough?"** — at scale,
repeatably, and without hand-writing test cases or hand-grading outputs.

Three model-driven stages:

1. **Generate** a diverse test dataset from a plain-English task description.
2. **Run** the prompt-under-test against every test case.
3. **Grade** each output with an LLM judge against per-case criteria, and produce a scored report.

The key idea: **the LLM builds the test data, and a separate LLM call grades the
results.** The human supplies only (a) a task description, (b) an input schema,
(c) the prompt/agent to test, and optionally (d) global pass/fail criteria.

**Scope.** The base layer evaluates **single-shot prompts** (`inputs -> str`). An
**agentic extension layer** (§3.5) evaluates **multi-step agents** that return a
trajectory of turns and tool calls. This is a **dev-time iteration tool**, not a
CI gate — runs produce versioned artifacts you diff by hand.

---

## 2. Architecture Overview

```
Human inputs:  task_description, prompt_inputs_spec, num_cases,
               run_function, extra_criteria
                                 |
        +------------------------+------------------------+
        v                        v                        v
  +-----------+          +---------------+         +--------------+
  | STAGE 1a  | ideas[]  |  STAGE 1b     | dataset |  STAGE 2+3   |
  | Generate  | -------> |  Generate     | ------> |  Run + Grade |
  | Ideas     |          |  Test Cases   |  []     |  Each Case   |
  +-----------+          +---------------+         +--------------+
   (1 LLM call)          (N parallel calls)        (2N parallel calls)
                                 |                        |
                                 v                        v
                        datasets/<name>.json     runs/<timestamp>/{output.json,output.html}
```

Each stage is independent. Datasets persist to disk so generation (expensive,
one-time) is decoupled from evaluation (cheap, repeated as the prompt is iterated).

---

## 3. Core Data Contracts

Stable interfaces. The reference implementation lives in
[`evals/evaluator/schemas.py`](../skills/prompt-evals-setup/framework/evals/evaluator/schemas.py).

### 3.1 `prompt_inputs_spec` (input schema) — REQUIRED

A map of `input_key -> human description of that input`.

```json
{
  "height": "Athlete's height in cm",
  "weight": "Athlete's weight in kg",
  "goal":   "Goal of the athlete"
}
```

- The **keys** define the exact set of variables the prompt consumes. They are a
  **closed set** — generation must use *only* these keys and *all* of them.
- The **values** are natural-language descriptions that steer the model toward
  realistic values. Documentation, not type enforcement.

### 3.2 Test Case — produced by Stage 1, consumed by Stage 2/3

```json
{
  "task_description": "string - injected by framework",
  "scenario":         "string - the idea this case came from",
  "prompt_inputs":    { "<key from spec>": "concrete value" },
  "solution_criteria": ["criterion 1", "criterion 2"]
}
```

| Field | Origin | Required | Notes |
|-------|--------|----------|-------|
| `prompt_inputs` | LLM-generated | Yes | Must contain **exactly** the keys from the spec (validated). |
| `solution_criteria` | LLM-generated | Yes | 1–4 concise, measurable criteria scoped to the task. |
| `task_description` | injected | Yes | Carried so grading is self-contained. |
| `scenario` | injected | Yes | Originating idea; used for reporting + diversity. |

### 3.3 Judge Verdict — produced by Stage 3

```json
{ "strengths": ["..."], "weaknesses": ["..."], "reasoning": "...", "score": 7 }
```

Field order is deliberate: the judge writes strengths/weaknesses/reasoning
**before** committing to a number. The **full verdict is persisted** (not just the
score) — strengths/weaknesses are the most useful debugging signal.

### 3.4 Result — one row of the report

```json
{
  "output": "raw final text the system under test produced",
  "trajectory": { "final_output": "...", "steps": [ ... ] },
  "test_case": { "...": "..." },
  "score": 7,
  "reasoning": "judge's concise explanation",
  "verdict": { "strengths": [], "weaknesses": [], "reasoning": "...", "score": 7 }
}
```

### 3.5 `run_function` (the system under test) — REQUIRED

```
single-shot:  (prompt_inputs: dict) -> str
agentic:      (prompt_inputs: dict) -> Trajectory
```

`Trajectory` carries the final answer **and** the process that produced it:

```python
@dataclass
class Step:
    role: str                  # "assistant" | "tool"
    content: str = ""
    tool_name: str | None = None
    tool_input:  Any = None
    tool_output: Any = None

@dataclass
class Trajectory:
    final_output: str
    steps: list[Step]          # empty => treated as single-shot
```

A bare `str` is normalized to a steps-less `Trajectory`, so both paths share one
grading pipeline. When `steps` is non-empty, the **trajectory grading** prompt is
used and `process_criteria` (if supplied) judge *how* the agent worked, not just
the final answer.

This is the only fully user-owned piece — where the prompt/agent being evaluated
lives. The framework is otherwise agnostic to what it does.

---

## 4. The Three Stages in Detail

Reference: [`generate.py`](../skills/prompt-evals-setup/framework/evals/evaluator/generate.py),
[`run.py`](../skills/prompt-evals-setup/framework/evals/evaluator/run.py), [`grade.py`](../skills/prompt-evals-setup/framework/evals/evaluator/grade.py).

### Stage 1 — Dataset Generation

**1a. Idea generation** (single call, temp ~1.0). Returns a JSON array of
`num_cases` short, *distinct* scenario descriptions. Each idea must be: distinct
(diversity), relevant, specific, quick to solve, and bounded (~400-token output).

**1b. Test-case generation** (one call per idea, parallel, temp ~0.7). Each idea
becomes a full test case. Guardrails baked into the prompt **and** enforced in
code (`validate_test_case`):
- **Closed key set** — uses only and all the allowed input keys (validated; one retry on violation).
- **Criteria minimalism** — 1–4 criteria addressing only the core task, with a worked example in the prompt.
- **No extra fields** — shape is locked.

Output → `datasets/<name>.json`, including a **provenance** block (generator model,
num_cases, the input spec, UTC timestamp). **Generate once, evaluate many times.**

### Stage 2 — Execution

For each test case, the framework calls `run_function(prompt_inputs)` and
normalizes the result to a `Trajectory`. Runs in parallel across cases.

### Stage 3 — Grading (LLM-as-judge)

For each `(test_case, trajectory)`, a judge call scores **1–10** against:
- the case's `solution_criteria` (secondary), and
- the global `extra_criteria` (mandatory — any violation forces score ≤ 3), and
- for agentic runs, the `process_criteria` (how the agent behaved).

Judge design principles encoded in the prompts:
- **Grade only against listed criteria.** No invented requirements; no penalty for "only" meeting them.
- **Use the full scale.** Explicit bands (1–3 fail mandatory, 4–6 meets mandatory/weak secondary, 7–8 minor issues, 9–10 full).
- **Determinism.** Judge runs at `temperature=0.0` on models that accept it. The default judge (Opus 4.8) removed sampling params, so the client omits temperature there and determinism rests on the model (see §8).
- **Reason before score.** Field order is strengths → weaknesses → reasoning → score.
- **Score clamped** to 1–10 in code (`validate_verdict`).

---

## 5. Prescribed Folder Structure

A project that invokes this spec ends up with exactly this tree:

```
evals/
  evaluator/            # framework package (vendored, rarely edited)
    __init__.py         #   exports PromptEvaluator, AnthropicClient, Trajectory, Step
    client.py           #   LLMClient protocol + Anthropic reference client
    templates.py        #   {placeholder} renderer with {{ }} escaping
    jsonio.py           #   tolerant JSON extraction
    schemas.py          #   contracts + validation (closed key set, verdict clamp)
    prompts.py          #   loads prompt templates from prompts/
    generate.py         #   Stage 1
    run.py              #   Stage 2
    grade.py            #   Stage 3
    report.py           #   output.json + escaped output.html
    evaluator.py        #   PromptEvaluator orchestration (bounded worker pool)
  prompts/              # THE FRAMEWORK PROMPTS — tune these, not the code
    idea_generation.md
    test_case_generation.md
    grading.md
    trajectory_grading.md
  prompts_under_test/   # your versioned prompt/agent definitions
  datasets/             # frozen *.json (+ provenance). git-ignored
  runs/                 # timestamped results (json + html). git-ignored
  examples/             # fake_client.py + smoke_test.py (offline)
  tests/                # stdlib unittest suite for the pure logic
  config.py             # models, temperatures, thresholds, paths
  run_eval.py           # copy-and-edit entrypoint
  requirements.txt
  README.md
```

---

## 6. Required vs. Optional Inputs

### Required
| Input | Used by | Purpose |
|-------|---------|---------|
| `task_description` | Stages 1 & 3 | Plain-English goal. Anchors generation and grading. |
| `prompt_inputs_spec` | Stages 1 & 2 | The closed set of input variables. |
| `run_function` | Stage 2 | The prompt/agent under test. |
| `dataset_file` | Stages 1 & 3 | Where the dataset is persisted / loaded. |

### Optional (sensible defaults)
| Input | Default | Effect |
|-------|---------|--------|
| `num_cases` | 1 | Number of test cases. Higher = better coverage, more cost. |
| `extra_criteria` | `None` | Global **mandatory** requirements; violations cap the score at 3. |
| `process_criteria` | `None` | Agentic only: how the agent should behave (tools, recovery, no needless steps). |
| `max_concurrent_tasks` | 3 | Worker-pool width. Speed vs. rate limits. |
| `run_label` | UTC timestamp | Names the `runs/<label>/` directory. |
| judge / executor / generator model | see `config.py` | Judge benefits from a strong model at temp 0, **different** from the executor. |

---

## 7. High-Quality vs. Low-Quality Inputs

Eval quality is won or lost here. The framework's effectiveness depends on the
*human-supplied* inputs.

### `task_description`
| High quality | Low quality |
|--------------|-------------|
| One clear, bounded objective ("Write a compact 1-day meal plan for one athlete"). | Vague or compound ("Help users with health"). |
| Names the deliverable and its scope. | Leaves the deliverable implicit. |
| Solvable in a small output budget. | Open-ended, needs multi-step reasoning or huge outputs. |

### `prompt_inputs_spec`
| High quality | Low quality |
|--------------|-------------|
| Keys map 1:1 to variables the prompt actually consumes. | Keys the prompt ignores, or undeclared variables. |
| Descriptions include units/format ("height in cm"). | Bare keys with no description. |
| Minimal, orthogonal inputs. | Overlapping or redundant inputs that confuse generation. |

### `solution_criteria` (generated — but review them)
| High quality | Low quality |
|--------------|-------------|
| 1–4 concise, measurable, task-scoped checks. | Long lists that drift beyond the task. |
| "Includes all topics mentioned." | "Is engaging, creative, well-formatted, insightful, and concise." |
| Tests the fundamental requirement. | Tests stylistic preferences the task never asked for. |

If generated criteria are too strict or off-scope, regenerate or hand-edit the
dataset — criteria quality directly determines whether scores are meaningful.

### `extra_criteria`
| High quality | Low quality |
|--------------|-------------|
| Short, concrete structural must-haves ("must include caloric total, macro breakdown, per-meal timing"). | Soft preferences that shouldn't be pass/fail. |
| Things whose absence genuinely means failure. | Aspirational quality bars (put those in per-case criteria). |

### Dataset size / diversity
- **High quality:** enough cases (often 10–50+) to cover edge cases, varied input combinations, and adversarial scenarios; each `scenario` genuinely distinct.
- **Low quality:** 1–2 cases (smoke test only), or many near-duplicates that inflate the count without adding coverage.

---

## 8. Configuration Surface

All in [`evals/config.py`](config.py):

| Setting | Default | Notes |
|---------|---------|-------|
| `PROVIDER` | `"anthropic"` | Swap by implementing `LLMClient` and passing your client in. |
| `GENERATOR_MODEL` | `claude-sonnet-4-6` | Builds ideas + test cases. |
| `EXECUTOR_MODEL` | `claude-haiku-4-5-...` | Default for the system under test. |
| `JUDGE_MODEL` | `claude-opus-4-8` | Strong, and different from executor (reduces self-grading bias). |
| `API_KEY_ENV` | `ANTHROPIC_API_KEY` | Where the client reads the key. |
| `IDEA/TESTCASE/GRADING_TEMPERATURE` | 1.0 / 0.7 / 0.0 | Diversity / realism / determinism. |
| `MAX_CONCURRENT_TASKS` | 3 | Worker-pool width. |
| `PASS_THRESHOLD` | 7 | A case passes if score ≥ this. |
| `COLOR_GREEN_MIN` / `COLOR_YELLOW_MIN` | 8 / 6 | HTML report color bands. |

To use a different provider, implement the tiny `LLMClient` protocol
(`complete_json(system, user, temperature, tag, schema=None)`) in `client.py` and
pass an instance to `PromptEvaluator`. The reference client forces clean JSON with
**structured outputs** (`output_config.format` + a JSON Schema): generation and
grading pass the schema from `schemas.py`, so the model is constrained to the exact
shape. The schema-less idea-list call falls back to the tolerant parser in
`jsonio.py`. (This replaces the older assistant-prefill + stop-sequence trick,
which 400s on Claude Opus 4.7+.) Two model-conditional notes: prefilled last
assistant turns and the sampling params `temperature`/`top_p`/`top_k` both 400 on
Opus 4.7+, so the client omits temperature for those models.

---

## 9. Output, Reporting & Provenance

Per run, written to `runs/<label>/`:

1. **`output.json`** — `{meta, summary, results}`. The full machine-readable record
   (every output, trajectory, test case, **full judge verdict**, score, reasoning).
   Diff this across prompt versions for regression tracking.
2. **`output.html`** — a self-contained report with:
   - **Summary header:** total cases, average score (`/10`), **pass rate** (% scoring ≥ `PASS_THRESHOLD`).
   - **Per-case table:** scenario, inputs, criteria, raw output, color-coded score, judge reasoning. **All values are HTML-escaped.**

Runs are written to **timestamped directories** (or `run_label`), so re-running
never overwrites a prior run — you accumulate a comparable history. Datasets embed
a **provenance** block (generator model, timestamp, num_cases, spec) so a frozen
dataset is auditable even though generation is non-deterministic.

Adjust `PASS_THRESHOLD` and the color bands to match your application's bar.

---

## 10. Minimal Usage Flow

```python
from evals import config
from evals.evaluator import AnthropicClient, PromptEvaluator

evaluator = PromptEvaluator(
    client=AnthropicClient(config.GENERATOR_MODEL),
    judge_client=AnthropicClient(config.JUDGE_MODEL),   # strong, distinct judge
    max_concurrent_tasks=config.MAX_CONCURRENT_TASKS,
)

# 1. Generate the dataset (once)
evaluator.generate_dataset(
    task_description="<bounded plain-English goal>",
    prompt_inputs_spec={"<key>": "<description w/ units>"},
    num_cases=20,
    output_file="evals/datasets/mytask.json",
)

# 2. Define the prompt under test (single-shot here; return a Trajectory for agents)
def run_prompt(prompt_inputs):
    ...  # build prompt, call model, return raw text

# 3. Evaluate (repeatedly, as you iterate the prompt) against the FROZEN dataset
evaluator.run_evaluation(
    run_function=run_prompt,
    dataset_file="evals/datasets/mytask.json",
    extra_criteria="<global mandatory requirements>",
)
```

Iterate step 2 and re-run step 3 against the **same frozen dataset** to compare
prompt versions apples-to-apples. Regenerate only when the task or schema changes.

---

## 11. Bootstrap Procedure (the runbook)

To stand the framework up in a new project:

1. **Detect the stack.** This reference targets **Python 3.10+**. (For another
   language, port §3–§9 faithfully; the prompts in `evals/prompts/` are the asset
   to preserve verbatim.)
2. **Vendor the package.** Copy the `evals/` tree (§5) into the project root.
   Ensure `evals/` and `evals/evaluator/` are importable from the repo root
   (run modules as `python -m evals.<...>`).
3. **Wire configuration.** Edit `evals/config.py`: set models, `API_KEY_ENV`, and
   `PASS_THRESHOLD`. Keep the judge model strong and distinct from the executor.
4. **Ignore generated artifacts.** Add `evals/datasets/*` and `evals/runs/*`
   (except `.gitkeep`) plus `__pycache__/` to `.gitignore`.
5. **Verify offline (no API key):**
   ```bash
   python -m unittest discover -s evals/tests -t .
   python -m evals.examples.smoke_test
   ```
   Both must pass. This proves the pipeline (generate → run → grade → report) and
   both single-shot and agentic grading paths, using a fake client.
6. **Define the real task.** Copy `evals/run_eval.py`, then set `TASK`,
   `PROMPT_INPUTS_SPEC`, `EXTRA_CRITERIA`, and implement `run_prompt`
   (return a `Trajectory` for agents).
7. **Generate + freeze the dataset:**
   ```bash
   pip install -r evals/requirements.txt
   export ANTHROPIC_API_KEY=sk-...
   python -m evals.run_eval generate
   ```
8. **Audit the dataset.** Open `datasets/<name>.json` and spot-check
   `solution_criteria` — bad criteria silently corrupt every downstream metric.
9. **Evaluate + read the report.**
   ```bash
   python -m evals.run_eval evaluate
   ```
   Open the newest `runs/<timestamp>/output.html`.

**Definition of done:** unit tests + smoke test green; a frozen dataset exists with
audited criteria; an `evaluate` run produced a rendered `output.html`.

---

## 12. Glossary

| Term | Means |
|------|-------|
| **Secondary criteria** | A test case's `solution_criteria` — what a good answer should do. |
| **Mandatory criteria** | The global `extra_criteria` — non-negotiable; any violation caps the score at 3. |
| **Process criteria** | Agentic-only: how the agent should behave (`process_criteria`). |
| **Trajectory** | An agent run: `final_output` + ordered `steps` (turns and tool calls). |
| **Provenance** | Metadata embedded in a dataset recording how/when/with-what it was generated. |
| **Run** | One `runs/<label>/` directory: `output.json` + `output.html`. |

---

## 13. Known Limitations & Hardening

The reference implementation handles several pitfalls the original scaffold left
open (JSON-fence stripping + bracket-slice repair in `jsonio.py`; closed-key-set
validation with retry; verdict score clamping; HTML escaping; full-verdict
persistence; timestamped non-overwriting runs; dataset provenance). Still consider:

- **Single-judge variance.** One judge call per case. For higher confidence, use a
  judge panel (majority vote) or multiple samples and average.
- **Judge/executor leakage.** Grading with the same model that produced the output
  biases scores upward; the default config uses a distinct, stronger judge — keep it that way.
- **Prompt injection via generated values.** Generated inputs are interpolated into
  prompts; for untrusted-data tasks, sandbox `run_function` and prefer structured inputs.
- **Criteria audit.** Always spot-check generated `solution_criteria` before
  trusting aggregate scores.
- **No CI gate (by design).** This is a dev-time tool. If you later want regression
  gating, diff `output.json` against a saved baseline and fail on a pass-rate drop.

### v0.2 hardening (shipped)

> **Reconciliation addendum (2026-05-29, after the `claude-plugins-official` review — shipped in
> the same session).** A pattern review against Anthropic's `skill-creator` promoted four items
> above from "consider" to framework hardening. All four **shipped** as new modules at the vendored
> `evals/` top level (beside `run_eval.py`), each with offline `unittest` fixtures and a
> `python -m evals.<module>` CLI — **never** as edits to `evaluator/` core, honoring the composition
> invariant named in the architecture spec (§5) and the prompt-engineering spec (§9). Plan + commits:
> `docs/superpowers/plans/2026-05-29-eval-framework-hardening.md`; the full offline suite is 54 tests.
> **Live-path integration** (pre-judge assertion *gating* inside `run_evaluation`; orchestrating K
> *live* runs for variance) is deferred to the run-path work — the shipped pieces are the
> deterministic cores + CLIs over existing dataset/`output.json` files.

- **Multi-run variance / confidence** — `evals/variance.py`. Aggregates K run files of one frozen
  dataset into per-case **mean ± stddev**, flags high-variance (flaky) cases, and emits
  `suggested_regression_band` (worst-case grading noise) — which `prompt-engineering-improve` consumes
  to **calibrate** the `regression_band` it hardcodes at 0.5 today (that spec §6). Reference pattern:
  `skill-creator`'s `aggregate_benchmark.py`.
- **Deterministic assertion layer (pre-judge)** — `evals/assertions.py`. Structural must-haves
  (`contains` / `regex` / length / `json_valid` / `json_has_key`) checked **in code** — cheaper and
  more reliable than the judge for definite-shape requirements; the judge then handles only what needs
  judgment. The standalone engine is shipped; wiring it as a pre-judge *gate* inside the run loop is
  the deferred live-path integration above.
- **Criteria-audit script** — `evals/criteria_audit.py`. Deterministically flags **non-discriminating**
  criteria (identical across all cases), subjective-language criteria, and duplicate scenarios over a
  frozen dataset, promoting the manual spot-check (§7) into a checked report. Reference: `skill-creator`'s
  analyzer pass.
- **Baseline / previous-run delta** — `evals/run_delta.py`. A no-model diff of two
  `runs/<label>/output.json` → per-case + aggregate deltas (matched by scenario), promoting the manual
  "diff output.json" note above. `prompt-engineering-improve`'s `improve_step.py` consumes
  `compute_delta` rather than re-implementing delta/argmax (that spec §6).

### Cost
Total LLM calls ≈ `1 + num_cases (generation) + 2 × num_cases (run + grade)`.
Generation is one-time per frozen dataset; only the `2 × num_cases` run+grade cost
recurs each evaluation. Budget accordingly.
