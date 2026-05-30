# T-020 — Restore the single-pass diagnosis handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: In progress

**Goal:** Rewrite the "Diagnose and iterate" section (§5) of `skills/prompt-evals-run/SKILL.md` so it is an explicit **single-pass** diagnosis handoff that names the criteria-vs-prompt guard, restores the citation to the shared `diagnosis.md` reference, keeps mandatory-criterion-first guidance, and points users to `prompt-engineering-improve` for the automated multi-round loop.

**Architecture:** This is a **docs-only, single-file** change. One markdown section (`### 5. Diagnose and iterate`, currently lines 177–187) is replaced. Nothing else in the file changes — the Path A run/render/grade/aggregate mechanics (§1–§4) and the Path B substrate (§ "Procedure — Path B", line 189 onward) are left byte-for-byte intact. No Python, no schema, no framework code. Verification is **structural grep + a no-change diff guard + the skill linter** — fully deterministic, offline, no model calls.

**Tech Stack:** Markdown (GitHub-flavored), `grep -F`, `git diff`, `python3 tools/skill_lint.py`.

---

## Context an implementer needs before starting

You are editing one Claude Code skill file. Read these first so the change is faithful:

1. **The ticket (authority for the exact requirements):** `T-020`. Run `storybloq ticket get T-020` (or read `.story/tickets/T-020.json`).
2. **The spec (the design contract):** `docs/superpowers/specs/2026-05-30-prompt-engineering-diagnosis-and-future-spec.md`, **§2** ("T-020 — Restore the single-pass diagnosis handoff"). §2.2 lists the six required edits; §2.3 lists the verification; §2.4 is the definition of done. **§5 of that spec says T-020 is the ONLY buildable item — do NOT implement T-017 / §8 future enhancements.**
3. **The shared reference being cited** (read it so your wording does not contradict it): `skills/prompt-engineering-improve/references/diagnosis.md`. Its §1 header is literally `First gate: is it the prompt or the criteria? (criteria-vs-prompt guard)`; its §2 is `Mandatory criterion first` (any case scoring ≤ 3 failed a mandatory criterion — fix that gate first). The file's intro describes `prompt-evals-run`'s role as the *single-pass "what's wrong; fix and re-run, or invoke prompt-engineering-improve to automate the loop" step* — that is exactly the boundary §5 must encode.
4. **Parent spec cross-refs** (background, no edits needed): `docs/superpowers/specs/2026-05-29-prompt-engineering-skills-design.md` §4 (the diagnosis seam) and §7 (cross-skill reference coupling: `diagnosis.md` has one physical home under `prompt-engineering-improve`, two readers; `prompt-evals-run` cites it, never forks it).

### The four literal verification tokens (memorize the trap)

The ticket's verification greps for these **exact contiguous substrings**. A structural `grep -F "<token>"` of the edited file must match each:

- `single-pass`
- `prompt-engineering-improve/references/diagnosis.md`
- `prompt-engineering-improve to automate`
- `criteria-vs-prompt guard`

> **TRAP — token `prompt-engineering-improve to automate`.** The bytes between `improve` and `to` must be a **plain space**. If you write an inline-code span like `` `/je-dev-skills:prompt-engineering-improve` `` immediately followed by ` to automate`, the real bytes are `improve`​`` ` ``​` to automate` (a backtick sits before the space) and `grep -F` will **NOT** match. You therefore need a **bare, plain-text** occurrence of the contiguous phrase `prompt-engineering-improve to automate` outside any backticks. (You may *also* use the `` `/je-dev-skills:prompt-engineering-improve` `` code-span form elsewhere for the user-facing pointer — that is encouraged for edit 5 — but it does not by itself satisfy this token.)

### The no-change constraint

The ticket requires **no changes** under:
- `skills/prompt-evals-setup/framework/evals/evaluator`
- `skills/prompt-evals-setup/framework/evals/prompts`

This plan never touches those paths, so the guard in Task 3 is a safety check, not a risk.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `skills/prompt-evals-run/SKILL.md` | The skill prose; §5 is the diagnosis-handoff section being rewritten | **Modify** (replace lines 177–187 only) |
| `.story/tickets/T-020.json` | Ticket status | **Modify** (status → complete, in the same change) |

No files are created. No test files — the verification is structural grep + diff + linter (Tasks 3–4), appropriate for a prose-only change with a deterministic acceptance contract.

---

## Task 1: Establish the pre-edit baseline

**Files:**
- Read: `skills/prompt-evals-run/SKILL.md`

- [ ] **Step 1: Confirm the four tokens are currently absent and capture the section boundary**

Run:
```bash
cd /home/dawti/je-dev-skills
echo "--- current token presence (expect all MISSING) ---"
for t in 'single-pass' 'prompt-engineering-improve/references/diagnosis.md' 'prompt-engineering-improve to automate' 'criteria-vs-prompt guard'; do
  if grep -qF -- "$t" skills/prompt-evals-run/SKILL.md; then echo "PRESENT : $t"; else echo "MISSING : $t"; fi
done
echo "--- section 5 boundary ---"
grep -n '^### 5\. Diagnose and iterate' skills/prompt-evals-run/SKILL.md
grep -n '^## Procedure — Path B' skills/prompt-evals-run/SKILL.md
```
Expected:
```
PRESENT : (none) — all four print MISSING
### 5. Diagnose and iterate      -> line 177
## Procedure — Path B            -> line 189
```
(So §5 occupies lines 177–187, with a blank line 188 before Path B at 189. If these line numbers differ, the file moved since this plan was written — re-locate the section by its `### 5. Diagnose and iterate` heading and the next `##` heading, and adjust the Edit anchors in Task 2 accordingly. Do not edit by line number; use the heading-anchored Edit below.)

- [ ] **Step 2: Re-read the exact current §5 text to use as the Edit `old_string`**

Run:
```bash
cd /home/dawti/je-dev-skills
sed -n '177,187p' skills/prompt-evals-run/SKILL.md
```
Expected (this is the block you will replace):
```markdown
### 5. Diagnose and iterate

- **Low scores from real output flaws** → fix the prompt and re-run against the **same**
  dataset, **or invoke `/je-dev-skills:prompt-engineering-improve` to automate the loop.**
- **Low scores from bad criteria** (off-scope, subjective) → the dataset is the problem.
  Fix via `/je-dev-skills:prompt-evals-create-dataset` (audit step).
- **Mandatory-criterion failures** cap a score at ≤ 3 — check `extra_criteria` first when
  scores cluster low.

Keep `SUBAGENT_JUDGE_MODEL` strong and **distinct** from `SUBAGENT_EXECUTOR_MODEL` to
avoid self-grading leakage; widen the dataset for higher confidence on close calls.
```

There is no commit at the end of this task — it is read-only baseline capture.

---

## Task 2: Replace the §5 section

**Files:**
- Modify: `skills/prompt-evals-run/SKILL.md` (the `### 5. Diagnose and iterate` block)

- [ ] **Step 1: Apply the replacement with the Edit tool**

Use the Edit tool on `skills/prompt-evals-run/SKILL.md`.

`old_string` (must match the file exactly — the entire current §5 block):
```markdown
### 5. Diagnose and iterate

- **Low scores from real output flaws** → fix the prompt and re-run against the **same**
  dataset, **or invoke `/je-dev-skills:prompt-engineering-improve` to automate the loop.**
- **Low scores from bad criteria** (off-scope, subjective) → the dataset is the problem.
  Fix via `/je-dev-skills:prompt-evals-create-dataset` (audit step).
- **Mandatory-criterion failures** cap a score at ≤ 3 — check `extra_criteria` first when
  scores cluster low.

Keep `SUBAGENT_JUDGE_MODEL` strong and **distinct** from `SUBAGENT_EXECUTOR_MODEL` to
avoid self-grading leakage; widen the dataset for higher confidence on close calls.
```

`new_string` (the verified replacement — copy verbatim, including the bare `prompt-engineering-improve to automate the loop` in the third bullet which is intentionally **not** wrapped in backticks):
```markdown
### 5. Diagnose and iterate

This is the **single-pass** "what's wrong; fix and re-run" step — diagnose once, then hand
off. The automated multi-round loop lives in `/je-dev-skills:prompt-engineering-improve`,
not here. Read the shared reference before diagnosing:
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md` (one home,
two readers — cite it, never fork it).

- **First gate — the criteria-vs-prompt guard** → before recommending any rewrite, decide
  whether the **prompt** is wrong or the **success criteria** are. If the judge wants content
  not in the inputs, the rubric demands an unstated format, the rationale conflicts with the
  rubric, or it needs hidden domain knowledge, the **dataset** is the problem — fix it via
  `/je-dev-skills:prompt-evals-create-dataset`, do **not** touch the prompt.
- **Mandatory-criterion failures first** → any case scoring **≤ 3** failed a mandatory
  criterion. Check `extra_criteria` and fix that gate before any secondary-criteria polish.
- **Genuine prompt flaws** → fix the prompt and re-run against the **same** dataset, or
  invoke prompt-engineering-improve to automate the loop.

Keep `SUBAGENT_JUDGE_MODEL` strong and **distinct** from `SUBAGENT_EXECUTOR_MODEL` to avoid
self-grading leakage; widen the dataset for higher confidence on close calls.
```

Why this text satisfies the spec's six edits (§2.2):
1. **Single-pass** — opening sentence: *"This is the single-pass … step — diagnose once, then hand off."*
2. **Citation restored** — *`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`* with the "one home, two readers — cite it, never fork it" gloss (parent spec §4/§7).
3. **Names the guard** — *"First gate — the criteria-vs-prompt guard"*.
4. **Mandatory-criterion-first kept** — *"Mandatory-criterion failures first → any case scoring ≤ 3 … fix that gate before any secondary-criteria polish"* (also retains the original `extra_criteria` hint).
5. **Points to the automated loop** — both the user-facing pointer `/je-dev-skills:prompt-engineering-improve` and the bare phrase *"invoke prompt-engineering-improve to automate the loop"*.
6. **Substrate untouched** — only this block changes; Path A §1–§4 and Path B are not in the edit.

- [ ] **Step 2: Verify the edit landed and the file still parses as the same document**

Run:
```bash
cd /home/dawti/je-dev-skills
sed -n '177,200p' skills/prompt-evals-run/SKILL.md
```
Expected: the new §5 text above, followed by a blank line and `## Procedure — Path B` (the Path B heading is unchanged — confirm it is still present and identical).

There is no commit yet — commit happens in Task 5 after verification passes.

---

## Task 3: Structural verification (the ticket's acceptance gate)

**Files:**
- Read: `skills/prompt-evals-run/SKILL.md`

- [ ] **Step 1: Assert all four literal tokens are present (grep -F)**

Run:
```bash
cd /home/dawti/je-dev-skills
fail=0
for t in 'single-pass' 'prompt-engineering-improve/references/diagnosis.md' 'prompt-engineering-improve to automate' 'criteria-vs-prompt guard'; do
  if grep -qF -- "$t" skills/prompt-evals-run/SKILL.md; then echo "FOUND   : $t"; else echo "MISSING : $t"; fail=1; fi
done
test "$fail" -eq 0 && echo "ALL TOKENS PRESENT" || { echo "TOKEN CHECK FAILED"; exit 1; }
```
Expected:
```
FOUND   : single-pass
FOUND   : prompt-engineering-improve/references/diagnosis.md
FOUND   : prompt-engineering-improve to automate
FOUND   : criteria-vs-prompt guard
ALL TOKENS PRESENT
```
If `prompt-engineering-improve to automate` shows MISSING, you hit the backtick trap — the third bullet's phrase got wrapped in or abutted by backticks. Re-open the edit and ensure `invoke prompt-engineering-improve to automate the loop` is plain text.

- [ ] **Step 2: Confirm the no-change constraint — evaluator/ and prompts/ untouched**

Run:
```bash
cd /home/dawti/je-dev-skills
git diff --name-only | grep -E 'skills/prompt-evals-setup/framework/evals/(evaluator|prompts)/' && { echo "FORBIDDEN PATH CHANGED"; exit 1; } || echo "NO CHANGES under evaluator/ or prompts/ (correct)"
```
Expected:
```
NO CHANGES under evaluator/ or prompts/ (correct)
```

- [ ] **Step 3: Confirm only the intended files changed**

Run:
```bash
cd /home/dawti/je-dev-skills
git diff --name-only
```
Expected: exactly `skills/prompt-evals-run/SKILL.md` (the ticket JSON is updated in Task 5). No other paths. If anything else appears, revert it — this change is scoped to the one section.

- [ ] **Step 4: Confirm the diff is confined to §5 (substrate wording intact)**

Run:
```bash
cd /home/dawti/je-dev-skills
git diff skills/prompt-evals-run/SKILL.md
```
Expected: the hunk(s) touch only the `### 5. Diagnose and iterate` block. The `## Procedure — Path B` section and §1–§4 must show **no** changes. Eyeball that no Path A/B mechanics lines appear in the diff.

---

## Task 4: Run the skill linter

**Files:**
- Read: `tools/skill_lint.py`

- [ ] **Step 1: Run the linter from the repo root**

Run:
```bash
cd /home/dawti/je-dev-skills
python3 tools/skill_lint.py --root .
```
Expected (paste the ACTUAL output into the handover — do not claim green from memory):
```
11 skills | 0 errors | 0 warnings
```
If the linter reports an error on `prompt-evals-run` (e.g. a malformed heading or broken reference), fix it and re-run before proceeding. The number of skills may differ from 11 if the repo changed; what matters is **0 errors**.

---

## Task 5: Mark the ticket complete and commit

**Files:**
- Modify: `.story/tickets/T-020.json` (via the storybloq tool/CLI)
- Modify: `skills/prompt-evals-run/SKILL.md` (already edited; committed here)

- [ ] **Step 1: Mark T-020 complete**

Use the storybloq MCP tool `storybloq_ticket_update` with `id: "T-020"`, `status: "complete"`.
(CLI equivalent, if MCP is unavailable: `storybloq ticket update T-020 --status complete`.)

- [ ] **Step 2: Stage and commit the change together with the ticket update**

Run:
```bash
cd /home/dawti/je-dev-skills
git add skills/prompt-evals-run/SKILL.md .story/tickets/T-020.json
git commit -m "feat: restore single-pass diagnosis handoff in prompt-evals-run (T-020)

Rewrite SKILL.md §5 'Diagnose and iterate' as an explicit single-pass
diagnosis handoff: name the criteria-vs-prompt guard, restore the citation
to prompt-engineering-improve/references/diagnosis.md, keep
mandatory-criterion-first, and point users to prompt-engineering-improve for
the automated multi-round loop. Substrate (Path A/B) unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Expected: a single commit containing exactly the two files.

---

## Task 6: Close-out per the working agreement (AGENTS.md)

This repo's working agreement (`AGENTS.md`) requires more than passing checks before a work stream is "done". Complete these in order.

- [ ] **Step 1: Two independent review rounds**

Per AGENTS.md step 5, run two independent reviews and address findings before declaring done. For a prose-only change the lightweight form is appropriate, e.g. `/code-review` on the diff and a second pass with `skill-reviewer` (or a second `code-review` at higher effort). Because the change is doc-only and the acceptance contract is the deterministic grep in Task 3, focus the reviews on: faithfulness to `diagnosis.md`, readability/voice match with the surrounding sections, and that no substrate wording drifted. Record findings; fix any that are valid.

- [ ] **Step 2: Write the handover**

Create a handover in `.story/handovers/` (via `storybloq_handover_create`, slug e.g. `t020-diagnosis-handoff`) summarizing: what changed (the §5 rewrite), the verification evidence (paste the actual Task 3 token output and the Task 4 linter line), the two-review outcome, and a reference to this plan's filename: `docs/superpowers/plans/2026-05-30-t020-diagnosis-handoff.md`.

- [ ] **Step 3: Capture a lesson only if one emerged**

If something non-obvious surfaced (e.g. the `grep -F` backtick trap on `prompt-engineering-improve to automate`), create a lesson via `storybloq_lesson_create`. Skip if nothing new — do not pad.

- [ ] **Step 4: Delete this plan on the feature branch before merge**

Per AGENTS.md ("Deleting plans once implemented"), the plan is ephemeral. After confirming its durable residue lives elsewhere (design decisions already in the spec §2; what-happened in the handover from Step 2), remove it:
```bash
cd /home/dawti/je-dev-skills
git rm docs/superpowers/plans/2026-05-30-t020-diagnosis-handoff.md
git commit -m "chore: delete implemented T-020 plan (residue in spec + handover)"
```
Reference this filename in the handover so history stays traceable.

- [ ] **Step 5: Integrate and clean up (local merge cleanup)**

Per AGENTS.md ("Integrating and cleaning up branches/worktrees") and lesson L-002, do not offer PR/keep-branch options. If this work was done on a feature branch/worktree:
1. Merge the branch back to the default branch locally.
2. Re-run verification on the merged result: the Task 3 token greps **and** `python3 tools/skill_lint.py --root .` (paste actual output).
3. Remove the worktree (if one was used).
4. Delete the local feature branch.

If the work was done directly on the default branch (no separate branch), this step reduces to: ensure the working tree is clean and the verification in Task 3–4 passed on the final state. The only exception to auto-merge is an explicit user instruction to pause before merge.

---

## Self-review notes (author)

- **Spec coverage:** All six §2.2 edits map to Task 2 Step 1's annotated rationale; all four §2.3 tokens are asserted in Task 3 Step 1; the two §2.3 no-change paths are guarded in Task 3 Step 2; §2.4 definition of done = Tasks 3 + 4 (tokens found, paths untouched, linter green). **T-017 deliberately excluded** per spec §5 scope boundary.
- **No placeholders:** every step has the exact command and the exact replacement text. The `new_string` was machine-verified (`grep -F` matched all four tokens; the byte immediately before `prompt-engineering-improve to automate` is a plain space).
- **Type/identifier consistency:** token strings, the `${CLAUDE_PLUGIN_ROOT}` path, and the `/je-dev-skills:` command prefix are identical everywhere they appear.
- **Scope:** single file (+ ticket JSON), one section, no code — focused enough for one plan; no decomposition needed.
