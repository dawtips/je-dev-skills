---
name: workflow-design-review
description: This skill should be used when the user asks to "review my workflow design", "critique a workflow blueprint", "assess a blueprint", "is this workflow design any good", or after workflow-design-validate passes and the user wants semantic design feedback. It runs an advisory LLM-as-judge review over ./workflows/<name>.blueprint.md and writes a .review.md report.
argument-hint: "[path to the blueprint; defaults to ./workflows/*.blueprint.md] [--strict]"
allowed-tools: Bash, Read, Edit, Glob
version: 0.2.0
---

# Workflow Design: Review

Run an advisory semantic review over a workflow blueprint. This review catches
quality problems that the deterministic validator cannot see: misclassified
deterministic/agentic steps, over-engineering, weak subagent contracts, poor
rubrics, untestable outcomes, dishonest `n/a`s, and internal inconsistency.

## Precondition

A blueprint file must exist. Blueprints are written by
`workflow-design-interview` to `./workflows/<name>.blueprint.md`.

Recommended order:

1. Run `workflow-design-validate` first and fix structural gaps until it passes.
2. Run this review skill for semantic quality feedback.

The review can run before validation, but that usually wastes a paid judge call
on basic structural issues.

## Procedure

1. **Install dependencies once.**

   ```bash
   pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-review/scripts/requirements.txt
   ```

2. **Set the Anthropic API key.**

   ```bash
   export ANTHROPIC_API_KEY="..."
   ```

   Real reviews send the full blueprint content to Anthropic. Do not run this on
   blueprints that contain secrets, credentials, sensitive customer data, or
   internal details that should not leave the local machine.

3. **Run the reviewer.**

   If the user passed a path, store it in a quoted variable and pass it as one
   argument:

   ```bash
   BLUEPRINT_PATH="<path>"
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-review/scripts/review_blueprint.py" --date "$(date +%F)" -- "$BLUEPRINT_PATH"
   ```

   If no path was passed, let the script resolve `./workflows/*.blueprint.md`:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-review/scripts/review_blueprint.py" --date "$(date +%F)"
   ```

   Add `--strict` only when the user wants flagged dimensions to produce exit
   code `1`. The default model is a strong Sonnet-tier model for routine reviews;
   use `--model claude-opus-4-8` or `WORKFLOW_REVIEW_JUDGE_MODEL=claude-opus-4-8`
   only for unusually complex or high-stakes blueprints.

4. **Read the report.**

   The script writes `./workflows/<name>.review.md` next to the blueprint and
   prints a condensed summary to stdout.

5. **Address findings.**

   Edit the blueprint for flagged dimensions the user accepts. Re-run
   `workflow-design-validate` after structural edits, then re-run this review if
   semantic confirmation is useful.

## Exit Codes

- `0`: Review completed and report was written. This is returned by default even
  when the verdict is `needs-revision`.
- `1`: `--strict` was passed and at least one dimension scored below the
  threshold.
- `2`: Blueprint resolution failed, the blueprint was unreadable/malformed, the
  API call failed, or the judge response was invalid.

## Definition of Done

A `.review.md` report exists next to the blueprint. Flagged dimensions have been
addressed in the blueprint or consciously accepted by the user.

## Notes

- This review is advisory. The deterministic validator remains the hard gate.
- The judge sees the blueprint file and nothing else. Do not provide the
  interview transcript or authoring conversation; context isolation keeps the
  review skeptical.
- The script rejects non-`.blueprint.md` explicit paths and writes the report next
  to the blueprint. Existing `.review.md` reports are overwritten intentionally so
  the latest review remains the diffable artifact for that blueprint.
- Offline tests use a fake client and do not require an API key. Real reviews do
  require Anthropic credentials.
