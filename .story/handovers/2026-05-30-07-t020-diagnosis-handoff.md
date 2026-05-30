# Session 2026-05-30 — T-020 restore single-pass diagnosis handoff

## Summary
Implemented **T-020** (phase `prompt-engineering`): rewrote the *Diagnose and iterate*
section (§5) of `skills/prompt-evals-run/SKILL.md` so it is an explicit **single-pass
diagnosis handoff** rather than describing an in-skill iterate loop. The automated
multi-round loop is now clearly attributed to `prompt-engineering-improve`. Branch:
`t020-diagnosis-handoff` (local merge cleanup per AGENTS.md). Plan (deleted before merge):
`docs/superpowers/plans/2026-05-30-t020-diagnosis-handoff.md`.

Doc-only change, one file (+ the ticket JSON). The spec (`§5`) is explicit that T-020 is the
only buildable item — **T-017 / §8 future enhancements were deliberately not touched.**

## What changed
`skills/prompt-evals-run/SKILL.md` §5 now:
1. Opens with the **single-pass** "what's wrong; fix and re-run — diagnose once, then hand
   off" framing; states the automated loop lives in `/je-dev-skills:prompt-engineering-improve`,
   "not here".
2. Restores the citation to the shared reference
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`
   ("one home, two readers — cite it, never fork it").
3. Names the **criteria-vs-prompt guard** as the first gate, reproducing diagnosis.md §1's
   four routing triggers (content not in inputs / unstated format / rationale conflicts with
   rubric / hidden domain knowledge) → route to `prompt-evals-create-dataset`, don't touch
   the prompt.
4. Keeps **mandatory-criterion-first** (≤ 3 cap, check `extra_criteria` first).
5. Points users to `/je-dev-skills:prompt-engineering-improve` for the automated loop, plus
   the bare phrase "invoke prompt-engineering-improve to automate the loop".
6. Leaves the Path A/B substrate (§1–§4 and Procedure — Path B) byte-for-byte unchanged.

## Verification (actual output)
- Token grep (`grep -F`) of the edited SKILL.md — all four present:
  `FOUND : single-pass` / `FOUND : prompt-engineering-improve/references/diagnosis.md` /
  `FOUND : prompt-engineering-improve to automate` / `FOUND : criteria-vs-prompt guard` →
  `ALL TOKENS PRESENT`.
- No-change guard: `NO CHANGES under evaluator/ or prompts/ (correct)`; `git diff --name-only`
  showed only `skills/prompt-evals-run/SKILL.md` (the ticket JSON committed alongside).
- `git diff` hunk confined to the §5 block (`@@ -176,15 +176,24 @@`); `git diff --check` clean.
- Skill linter: `python3 tools/skill_lint.py --root .` → `11 skills | 0 errors | 0 warnings`.
- Commit `e2db17c` (feat) on top of plan commit `be79c87`.

## Reviews (two independent rounds)
Ran a two-lens review on the final committed text — **faithfulness/correctness** and
**clarity/voice/scope**. Both returned **ship**, no blocking/important findings, no dropped
guidance, no scope creep. Non-blocking notes, all deliberately not actioned:
- §5 omits diagnosis.md's third "INVESTIGATE / non-determinism" branch — acceptable for a
  single-pass summary that cites the full reference (adding it works against the file's terse
  norm).
- `extra_criteria` (config key) vs reference's `EXTRA_CRITERIA` (global constant) — carried
  over verbatim from the prior shipped section; distinct identifiers.
- Bare `prompt-engineering-improve` in bullet 3 vs slash-command form in the intro — this is
  the machine-verified required grep token, intentionally bare.

## How it was built
Used the superpowers loop: read the spec + the cited diagnosis.md + parent spec §4/§7 for
ground truth, then orchestrated the rewrite with a workflow — 3 independent drafts (distinct
angles) each adversarially verified against the six edits + four literal tokens + the
no-change constraint. Selected the faithful-min-diff draft, then **machine-verified** its
bytes (`grep -F` + a byte-before-phrase check for the backtick trap) before writing the plan.
A second workflow ran the two final review rounds.

## Gotcha worth remembering
The token `prompt-engineering-improve to automate` is a contiguous phrase that spans a word
(`prompt-engineering-improve`) which is *also* used as an inline-code slash command elsewhere.
If the phrase had been written as `` `/je-dev-skills:prompt-engineering-improve` `` ` to automate`,
the backtick before the space breaks `grep -F`. The fix: keep at least one **bare, plain-text**
occurrence of the contiguous phrase outside any code span. Captured as a lesson.

## Recommended next
Per `storybloq_recommend`, the remaining `prompt-engineering` phase work is done; the open
backlog items (T-015 model-selection advisor, T-016 visual viewer, T-017 §8 enhancements)
are all **gated/deferred** — build only when their gate fires, each needs a design pass first.
