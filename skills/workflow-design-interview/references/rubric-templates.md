# Rubric templates

Reusable rubric shapes for the blueprint's `rubrics` block, loaded by Stage 6 of the
interview (success criteria). Source grounding: `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §4.1
(rubric schema) and §10 (evaluation rigor — LLM-as-judge with explicit rubrics,
categorical scales, calibration, judge biases).

A blueprint's `rubrics` and `outcomes` are the **same shape** the `prompt-evals-*`
lifecycle consumes — see the [link below](#link-to-prompt-evals). Design rubrics here
once and they feed directly into evaluation later.

## Table of contents

1. [What makes a good rubric](#what-makes-a-good-rubric)
2. [The rubric schema (recap)](#the-rubric-schema-recap)
3. [Template 1 — correctness (reference-based)](#template-1--correctness-reference-based)
4. [Template 2 — completeness (reference-free)](#template-2--completeness-reference-free)
5. [Template 3 — citation fidelity (reference-based)](#template-3--citation-fidelity-reference-based)
6. [Link to the prompt-evals lifecycle](#link-to-prompt-evals)

---

## What makes a good rubric

- **Categorical integer scale, not floats.** Use a small, fixed, anchored scale
  (e.g. `1-5`). A judge cannot reliably distinguish `0.73` from `0.81`; it *can* pick
  between defined levels. Avoid unanchored continuous scores.
- **Explicit per-level definitions.** Define what each level *means* in observable
  terms. Levels must **discriminate** — a reader should be able to bin an output
  unambiguously. Vague levels ("good", "bad") produce noisy scores.
- **A pass/fail `gate`.** Every rubric names the integer threshold at or above which
  the output passes. Without a gate the score is uninterpretable.
- **`reference_based` vs reference-free.** `reference_based: true` when there is a
  known-correct answer to grade against (the judge compares output to a reference);
  `reference_based: false` for open-quality judgments with no single right answer.
- **`judge: human | llm`.** Who applies the rubric. `llm` for scalable LLM-as-judge
  grading (mind judge biases — calibrate against a labeled set); `human` for
  high-stakes or hard-to-automate judgments.

---

## The rubric schema (recap)

```yaml
rubrics:
  - name: <slug>
    scale: 1-5                   # categorical integer, NOT unanchored floats
    levels: {1: "...", 3: "...", 5: "..."}   # explicit per-level definitions
    gate: <int>                  # pass threshold (output passes at >= gate)
    reference_based: true|false  # is there a known-correct answer to grade against?
    judge: human|llm
```

---

## Template 1 — correctness (reference-based)

Grade an output against a known-correct answer. Use when the task has a verifiable
right answer (extraction, computation, classification against labels).

```yaml
  - name: correctness
    scale: 1-5
    levels:
      1: "Wrong: contradicts the reference answer."
      2: "Mostly wrong: a few correct fragments, key claim wrong."
      3: "Partially correct: right direction, material errors or omissions."
      4: "Correct with minor slips: substantively right, small inaccuracies."
      5: "Fully correct: matches the reference answer on every checked point."
    gate: 4
    reference_based: true
    judge: llm
```

---

## Template 2 — completeness (reference-free)

Grade how fully an open-ended output covers the required scope, with no single right
answer. Use for synthesis, briefs, plans.

```yaml
  - name: completeness
    scale: 1-5
    levels:
      1: "Major gaps: misses most required topics."
      3: "Partial: covers the main topics but shallow or with notable omissions."
      5: "Thorough: every required topic covered in adequate depth, no gaps."
    gate: 4
    reference_based: false
    judge: llm
```

---

## Template 3 — citation fidelity (reference-based)

Grade whether claims are supported by cited, real sources. Use for research/RAG
outputs where unsupported claims are the key failure mode.

```yaml
  - name: citation_fidelity
    scale: 1-5
    levels:
      1: "Fabricated or no citations; claims unsupported."
      2: "Some citations, but several claims unsupported or sources misattributed."
      3: "Most claims cited; a few unsupported or weakly sourced."
      4: "Nearly all claims cited to real, relevant sources; minor lapses."
      5: "Every material claim cited to a verifiable, relevant source."
    gate: 4
    reference_based: true
    judge: human
```

---

## Link to prompt-evals

The `rubrics` and `outcomes` you author here are the same shape consumed by the
plugin's `prompt-evals-*` lifecycle:

- `prompt-evals-create-dataset` defines the task, input schema, and solution criteria
  — the reference-based / reference-free framing and the categorical scales map
  directly onto those criteria.
- `prompt-evals-run` applies LLM-as-judge grading against a frozen dataset, using
  the same categorical-scale + per-level-definition + gate machinery described above.

When a blueprint reaches the build stage, hand its `rubrics`/`outcomes` to
`/je-dev-skills:prompt-evals-create-dataset` as the starting point for an eval
dataset. (This handoff is a documented future integration, not automated in v0.1 —
see `docs/superpowers/specs/WORKFLOW_DESIGN_SPEC.md` §8.)
