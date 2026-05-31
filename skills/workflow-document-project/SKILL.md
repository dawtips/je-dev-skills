---
name: workflow-document-project
description: This skill should be used when the user asks to document an existing project as a workflow, generate a workflow blueprint from project evidence, inventory a project before workflow design, or produce project documentation plus actionable feedback for workflow skills.
argument-hint: "[workflow name; defaults to derived project/workflow slug]"
allowed-tools: Bash, Read, Write, Glob
version: 0.1.0
---

# Workflow Document Project

Document an existing project and synthesize a draft workflow blueprint from local evidence.

## Preconditions

Run from the target project root unless the user supplied a different root. The target project may or may not already have `./workflows/*.blueprint.md`.

## Procedure

1. Install deterministic script dependencies once:

   ```bash
   pip install -r "${CLAUDE_PLUGIN_ROOT}/skills/workflow-document-project/scripts/requirements.txt"
   ```

2. Resolve the workflow name. If the user supplied a name, use it. Otherwise derive the slug from the project directory or the only existing `./workflows/*.blueprint.md`. If more than one candidate blueprint exists, or the derived slug conflicts with an existing blueprint name, ask the user to choose a name.

3. Run the deterministic inventory:

   ```bash
   WORKFLOW_NAME="<slug>"
   INVENTORY_FILE="$(mktemp)"
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/workflow-document-project/scripts/document_project.py" \
     inventory --root "$PWD" --name "$WORKFLOW_NAME" --date "$(date +%F)" --output "$INVENTORY_FILE"
   ```

4. Read the inventory summary. If `strong_workflow_signal` is false, stop and ask the user which workflow they want documented. Do not fabricate a blueprint.

5. Path A (`in_claude_code`), the default in-session path: ask the current session model to synthesize one fenced ` ```json ` object following `${CLAUDE_PLUGIN_ROOT}/skills/workflow-document-project/references/synthesis-prompt.md`. Save the model's response to a temp file. Either the bare JSON object or the whole fenced ` ```json ` block is accepted — the deterministic writer strips the fence (`_load_synthesis_file`) before validating the shape.

6. Write artifacts from the deterministic writer. It validates the synthesis shape, renders the blueprint, runs `workflow-design-validate` on it in-process to fill the report's `validation:` field, refuses (without `--force`) to clobber an existing `status: validated` blueprint, and fails closed (exit 2, no partial write) on a malformed payload:

   ```bash
   SYNTHESIS_FILE="<path-to-saved-synthesis-response>"
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/workflow-document-project/scripts/document_project.py" \
     write --root "$PWD" --name "$WORKFLOW_NAME" --date "$(date +%F)" \
     --inventory "$INVENTORY_FILE" --synthesis "$SYNTHESIS_FILE"
   ```

7. Path B, keyed fallback (`--mode anthropic_api`): use only for headless runs where no session model is available. It sends the bounded, redacted inventory payload to Anthropic after printing a warning, and rejects an over-cap payload (`MAX_INPUT_CHARS`) before sending:

   ```bash
   export ANTHROPIC_API_KEY="..."
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/workflow-document-project/scripts/document_project.py" \
     synthesize --root "$PWD" --name "$WORKFLOW_NAME" --date "$(date +%F)" --mode anthropic_api
   ```

8. Validate the generated blueprint:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/workflow-design-validate/scripts/validate_blueprint.py" \
     "workflows/${WORKFLOW_NAME}.blueprint.md"
   ```

9. Report the written paths, validation exit code, and next action. The project-doc's `validation:` field already records the in-process validator result (step 6); re-running the standalone validator here is for the user-visible exit code. Recommend `workflow-design-review` for semantic review. The generated blueprint stays `status: draft` until the user promotes it.

## Definition Of Done

- `workflows/<name>.blueprint.md` exists and contains exactly one fenced `yaml` block with `status: draft`.
- `workflows/<name>.project-doc.md` exists with inventory, evidence map, inferences, open questions, feedback, generated artifact paths, and a `validation:` field reflecting the actual validator result (not a stale `not run`).
- Deterministic validation has been run and its actual output is reported.
- Any field filled without direct evidence is listed in Open Questions.

## Notes

- Path A does not require an API key and does not intentionally send project data outside the Claude Code session.
- Path B requires `ANTHROPIC_API_KEY` and sends only the bounded, redacted inventory payload that survives `references/exclusions.md`.
- This skill is an alternate entry point to `workflow-design-interview`, not a replacement for semantic review.
