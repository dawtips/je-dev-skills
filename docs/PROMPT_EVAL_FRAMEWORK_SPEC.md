# Prompt Evaluation Framework — Implementation Spec

A reusable specification for building LLM-graded prompt evaluation into any application. It describes the architecture, the data contracts, what is required vs. optional, and what separates high-quality from low-quality inputs — independent of any particular task or dataset.

---

## 1. Purpose

The framework answers one question: **"Is my prompt good enough?"** — at scale, repeatably, and without hand-writing test cases or hand-grading outputs.

It does this with three model-driven stages:

1. **Generate** a diverse test dataset from a plain-English task description.
2. **Run** the prompt-under-test against every test case.
3. **Grade** each output with an LLM judge against per-case criteria, and produce a scored report.

The key idea: **the LLM builds the test data, and a separate LLM call grades the results.** The human only supplies (a) a task description, (b) an input schema, (c) the prompt to test, and optionally (d) global pass/fail criteria.

---

## 2. Architecture Overview

```
Human inputs:  task_description, prompt_inputs_spec, num_cases,
               run_prompt_function, extra_criteria
                                 |
        +------------------------+------------------------+
        v                        v                        v
  +-----------+          +---------------+         +--------------+
  | STAGE 1   | ideas[]  |  STAGE 1b     | dataset |  STAGE 2+3   |
  | Generate  | -------> |  Generate     | ------> |  Run + Grade |
  | Ideas     |          |  Test Cases   |  []     |  Each Case   |
  +-----------+          +---------------+         +--------------+
   (1 LLM call)          (N parallel calls)        (2N parallel calls)
                                 |                        |
                                 v                        v
                            dataset.json          output.json + output.html
```

Each stage is an independent unit and can be run separately. Datasets are persisted to disk so generation (expensive, one-time) is decoupled from evaluation (run repeatedly as the prompt is iterated).

---

## 3. Core Data Contracts

These are the stable interfaces. An implementation in any language must preserve these shapes.

### 3.1 `prompt_inputs_spec` (input schema) — REQUIRED

A map of `input_key -> human description of that input`.

```json
{
  "height": "Athlete's height in cm",
  "weight": "Athlete's weight in kg",
  "goal":   "Goal of the athlete"
}
```

- The **keys** define the exact set of variables the prompt-under-test consumes. They are treated as a closed set — generation is instructed to use *only* these keys and *all* of these keys.
- The **values** are natural-language descriptions used to steer the LLM toward realistic values. They are documentation for the model, not type enforcement.

### 3.2 Test Case — produced by Stage 1, consumed by Stage 2/3

```json
{
  "task_description": "string - copied from the run config",
  "scenario":         "string - the idea this case was generated from",
  "prompt_inputs":    { "<key from spec>": "concrete value" },
  "solution_criteria": ["criterion 1", "criterion 2"]
}
```

| Field | Origin | Required | Notes |
|-------|--------|----------|-------|
| `prompt_inputs` | LLM-generated | Yes | Must contain exactly the keys from the spec. |
| `solution_criteria` | LLM-generated | Yes | 1-4 concise, measurable criteria scoped to the task. |
| `task_description` | injected by framework | Yes | Carried so grading is self-contained. |
| `scenario` | injected by framework | Yes | The originating idea; used for reporting + diversity. |

### 3.3 Result — produced by Stage 3

```json
{
  "output":    "raw text the prompt-under-test produced",
  "test_case": { "...the full test case..." },
  "score":     7,
  "reasoning": "judge's concise explanation"
}
```

The judge actually returns `{strengths[], weaknesses[], reasoning, score}`; only `score` and `reasoning` are propagated into the result, but the richer object is available if you choose to persist it.

### 3.4 `run_prompt_function` (the prompt-under-test) — REQUIRED

A callable with the signature:

```
(prompt_inputs: dict) -> str
```

It receives one test case's `prompt_inputs` and returns the **raw model output** as a string. This is the only piece that is fully user-owned and where the prompt being evaluated lives. The framework is otherwise agnostic to what it does.

---

## 4. The Three Stages in Detail

### Stage 1 — Dataset Generation

Two sub-steps, both LLM-driven:

**1a. Idea generation** (single call). Given the task description and input spec, the model returns a JSON array of `num_cases` short, *distinct* scenario descriptions. The prompt explicitly requires each idea to be:
- clearly distinct from the others (diversity),
- relevant to the task,
- specific enough to drive a full test case,
- quick to solve (no multi-step computation),
- solvable within a bounded output budget (~400 tokens).

**1b. Test-case generation** (one call per idea, run in parallel). Each idea is expanded into a full test case with realistic `prompt_inputs` and 1-4 `solution_criteria`.

Critical guardrails baked into this step:
- **Closed key set** — the model MUST use only and all the allowed input keys.
- **Criteria minimalism** — criteria must address *only* the core task; over-specification is explicitly discouraged. (The prompt includes a worked example showing a single, tight criterion as the ideal.)
- **No extra fields** — output shape is locked.

Output is written to `dataset.json`. **Generate once, evaluate many times.**

### Stage 2 — Prompt Execution

For each test case, the framework calls `run_prompt_function(test_case["prompt_inputs"])` and captures the raw string output. Runs in parallel across cases.

### Stage 3 — Grading (LLM-as-judge)

For each `(test_case, output)` pair, a judge LLM call scores the output **1-10** against:
- the case's own `solution_criteria` (secondary criteria), and
- the global `extra_criteria` (mandatory criteria — any violation forces score <= 3).

Judge design principles encoded in the grading prompt:
- **Grade only against listed criteria.** The judge is explicitly told not to invent new requirements and not to penalize a solution for "only" meeting the criteria.
- **Use the full scale.** Explicit scoring bands (1-3 fail mandatory, 4-6 meets mandatory/weak secondary, 7-8 minor issues, 9-10 full).
- **Determinism.** Judge runs at `temperature=0.0`.
- **Structured verdict.** Returns `strengths`, `weaknesses`, `reasoning`, `score` in a fixed order (ordering before the score nudges the model to reason before committing to a number).

---

## 5. Required vs. Optional Inputs

### Required
| Input | Used by | Purpose |
|-------|---------|---------|
| `task_description` | Stages 1 & 3 | Plain-English goal of the prompt. Anchors generation and grading. |
| `prompt_inputs_spec` | Stages 1 & 2 | Defines the closed set of input variables. |
| `run_prompt_function` | Stage 2 | The prompt-under-test. |
| `dataset_file` path | Stages 1 & 3 | Where the dataset is persisted / loaded. |

### Optional (have sensible defaults)
| Input | Default | Effect |
|-------|---------|--------|
| `num_cases` | 1 | Number of test cases to generate. Higher = better coverage, more cost. |
| `extra_criteria` | `None` | Global mandatory requirements applied to *every* case; violations cap the score at 3. The lever for enforcing non-negotiable output structure. |
| `max_concurrent_tasks` | 3 | Thread-pool width for generation and grading. Trade speed vs. rate limits. |
| `json_output_file` / `html_output_file` | `output.json` / `output.html` | Where results + report are written. |
| judge model / executor model | implementation choice | Can differ; judge benefits from a strong model at temp 0. |

---

## 6. High-Quality vs. Low-Quality Inputs

This is where eval quality is won or lost. The framework's effectiveness depends on the *human-supplied* inputs.

### `task_description`
| High quality | Low quality |
|--------------|-------------|
| One clear, bounded objective ("Write a compact 1-day meal plan for one athlete"). | Vague or compound ("Help users with health"). |
| Names the deliverable and its scope. | Leaves the deliverable implicit. |
| Scoped so a case is solvable in a small output budget. | Open-ended tasks needing multi-step reasoning or huge outputs. |

### `prompt_inputs_spec`
| High quality | Low quality |
|--------------|-------------|
| Keys map 1:1 to variables the prompt actually consumes. | Keys the prompt ignores, or variables used but not declared. |
| Descriptions include units/format ("height in cm"). | Bare keys with no description ("height"). |
| Minimal, orthogonal inputs. | Overlapping or redundant inputs that confuse generation. |

### `solution_criteria` (generated, but you should review them)
| High quality | Low quality |
|--------------|-------------|
| 1-4 concise, measurable, task-scoped checks. | Long lists that drift beyond the task. |
| "Includes all topics mentioned." | "Is engaging, creative, well-formatted, insightful, and concise." (subjective, unbounded) |
| Tests the fundamental requirement. | Tests stylistic preferences the task never asked for. |

If generated criteria are too strict or off-scope, regenerate or hand-edit the dataset — criteria quality directly determines whether scores are meaningful.

### `extra_criteria`
| High quality | Low quality |
|--------------|-------------|
| A short, concrete list of structural must-haves ("must include caloric total, macro breakdown, per-meal timing"). | Soft preferences that shouldn't be pass/fail. |
| Things whose absence genuinely means failure. | Aspirational quality bars (these belong in per-case criteria, not mandatory gates). |

### Dataset size / diversity
- **High quality:** enough cases (often 10-50+) to cover edge cases, varied input combinations, and adversarial scenarios; each `scenario` genuinely distinct.
- **Low quality:** 1-2 cases (fine for a smoke test, not for confidence), or many near-duplicate scenarios that inflate the count without adding coverage.

---

## 7. Output & Reporting

Two artifacts per run:

1. **`output.json`** — full machine-readable results array (every output, test case, score, reasoning). Use this for diffing prompt versions and regression tracking.
2. **`output.html`** — a self-contained human-readable report with:
   - **Summary header:** total test cases, average score (`/10`), and **pass rate** (% of cases scoring >= 7).
   - **Per-case table:** scenario, inputs, criteria, raw output, color-coded score (green >= 8, yellow 6-7, red <= 5), and the judge's reasoning.

The pass threshold (>= 7) and the high/low color bands are the framework's notion of "good." Adjust these constants to match your application's bar.

---

## 8. Implementation Requirements

To reimplement in another stack, you need:

1. **An LLM client** with: system prompt support, temperature control, and stop sequences.
2. **The assistant-prefill + stop-sequence JSON trick.** Each generation/grading call:
   - prefills the assistant turn with an opening ```` ```json ```` fence,
   - sets a stop sequence of ```` ``` ````,
   - parses the returned text as JSON.
   This forces clean, parseable JSON without markdown fences leaking in. Replicate this (or use native structured-output / JSON mode) in your stack.
3. **A tiny template renderer.** Substitutes `{placeholder}` tokens and supports literal braces via `{{`/`}}` escaping. (Needed because prompts contain JSON examples with real braces.)
4. **Concurrency** with a bounded worker pool (the `max_concurrent_tasks` knob) plus progress reporting at milestones (e.g., every 20%).
5. **Disk persistence** of the dataset (JSON) so generation and evaluation are decoupled.
6. **Three carefully-worded prompts** — idea generation, test-case generation, and grading. These prompts *are* the framework; port their constraints faithfully:
   - closed key set enforcement,
   - criteria minimalism with a worked example,
   - judge "grade only against listed criteria / use full scale / mandatory -> <=3" rules,
   - reason-before-score field ordering.

### Recommended model settings
| Call | Temperature | Why |
|------|-------------|-----|
| Idea generation | ~1.0 | Maximize diversity of scenarios. |
| Test-case generation | ~0.7 | Realistic but varied. |
| Grading (judge) | 0.0 | Deterministic, reproducible scores. |

---

## 9. Known Limitations & Hardening Suggestions

The reference implementation is a teaching scaffold. For production, consider:

- **JSON parse robustness.** Direct `json.loads` will throw on malformed output. Add retries / repair / validation against the expected schema.
- **Input value escaping.** Values are interpolated into prompts with naive `\n` escaping; richer escaping (or true structured inputs) avoids prompt-injection-style breakage and quote collisions.
- **HTML escaping in the report.** Outputs are injected into HTML unescaped — escape them to avoid layout breakage and XSS if reports are shared.
- **Single-judge variance.** One judge call per case. For higher confidence, use a judge panel (majority vote) or multiple samples and average.
- **Judge/executor model leakage.** Grading with the same model that produced the output can bias scores upward; consider a different (often stronger) judge model.
- **Criteria audit.** Always spot-check generated `solution_criteria` before trusting aggregate scores — bad criteria silently corrupt every metric downstream.
- **Cost/coverage tuning.** Total LLM calls = `1 + num_cases (generation) + 2 x num_cases (run + grade)`. Budget accordingly.

---

## 10. Minimal Usage Flow (any implementation)

```
evaluator = PromptEvaluator(max_concurrent_tasks=N)

# 1. Generate dataset (once)
evaluator.generate_dataset(
    task_description = "<bounded plain-English goal>",
    prompt_inputs_spec = { "<key>": "<description w/ units>" },
    num_cases = 20,
    output_file = "dataset.json",
)

# 2. Define the prompt-under-test
def run_prompt(prompt_inputs):
    # build prompt from prompt_inputs, call the model, return raw text
    ...

# 3. Evaluate (repeatedly, as you iterate the prompt)
evaluator.run_evaluation(
    run_prompt_function = run_prompt,
    dataset_file = "dataset.json",
    extra_criteria = "<global mandatory requirements>",
    json_output_file = "output.json",
    html_output_file = "output.html",
)
```

Iterate step 2 and re-run step 3 against the **same frozen dataset** to compare prompt versions apples-to-apples. Regenerate the dataset only when the task or input schema changes.
