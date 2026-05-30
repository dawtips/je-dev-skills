# Workflow Design Review Rubric

The judge scores each dimension on a categorical 1-5 scale. Scores 2 and 4 are
intermediate judgments between the anchored levels below. The judge must cite
specific `steps[i]` and `subagents[i]` ids when the blueprint contains them.

## 1. Determinism Classification Soundness (`determinism_classification`)

Assesses whether each step is correctly classified as `deterministic` or
`agentic`, and whether the rationale genuinely supports that choice.

- 1: Multiple steps are clearly misclassified, or rationales are absent,
  circular, or unrelated to the step behavior.
- 3: Most classifications are defensible, with one questionable call or thin
  rationale that would affect implementation quality.
- 5: Every step's `kind` is correct and each rationale explains why the work is
  deterministic or needs agentic judgment.

## 2. Simplicity / No Over-Engineering (`simplicity`)

Assesses whether the workflow uses the simplest sufficient architecture.

- 1: The design adds unjustified subagents, loops, tools, or orchestration for a
  problem that can be solved more directly.
- 3: The design is mostly proportionate, but one component, loop, or handoff is
  heavier than the problem requires.
- 5: Every step, subagent, loop, and artifact is necessary for the stated goal.

## 3. Subagent Contract Quality (`subagent_contracts`)

Assesses whether subagent contracts are specific, bounded, non-overlapping, and
least-privilege.

- 1: Contracts are present but vacuous; objectives, output formats, boundaries,
  or tools are broad enough that subagents can overlap or act unsafely.
- 3: Contracts are usable, but one boundary, output format, or tool allowlist is
  too vague for reliable delegation.
- 5: Each subagent has a crisp objective, explicit output shape, narrow tools,
  and boundaries that prevent overlap.

## 4. Rubric Quality (`rubric_quality`)

Assesses whether the blueprint's own success rubrics discriminate meaningful
quality levels and define sensible gates.

- 1: Rubric levels are generic, circular, missing gates, or cannot separate weak
  from strong outcomes.
- 3: Rubrics cover the right outcomes but one scale or gate is too coarse or
  ambiguous.
- 5: Rubric levels are concrete, observable, discriminating, and have gates that
  match the workflow's risk.

## 5. Outcome Testability (`outcome_testability`)

Assesses whether outcomes are observable Given-When-Then checks rather than
aspirational prose.

- 1: Outcomes cannot be verified from artifacts or behavior, or they omit the
  triggering condition and observable result.
- 3: Outcomes are mostly observable, with one weak `given`, `when`, or `then`
  that leaves success open to interpretation.
- 5: Outcomes are concrete, externally observable, and sufficient to tell
  whether the workflow worked.

## 6. N/A Honesty (`na_honesty`)

Assesses whether each `n/a` dimension is genuinely non-applicable.

- 1: One or more `n/a` rationales hide real design work, risk, or operational
  constraints that apply to the workflow.
- 3: Most `n/a`s are fair, but one rationale is thin or should be converted into
  a specified design note.
- 5: Every `n/a` is justified by the workflow's actual scope and constraints.

## 7. Internal Consistency (`internal_consistency`)

Assesses whether inputs, outputs, preconditions, postconditions, steps,
subagents, dimensions, rubrics, and outcomes agree with each other.

- 1: Major inconsistencies exist, such as step outputs not feeding downstream
  inputs, missing preconditions, or rubrics/outcomes that measure a different
  workflow.
- 3: The design is mostly coherent, with one mismatch or implied artifact that
  should be made explicit.
- 5: The blueprint reads as one coherent system; artifacts and guarantees line
  up across every section.
