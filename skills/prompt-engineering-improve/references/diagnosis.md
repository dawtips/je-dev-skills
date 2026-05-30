# Diagnosis: turning a scored report into the next move

Shared reference. Read by **prompt-engineering-improve** (at the diagnose step of the
loop) and cited by **prompt-evals-run** (its single-pass "what's wrong; fix and re-run,
or invoke prompt-engineering-improve to automate the loop" step). This file is part of
the group contract - it cannot move/rename without updating both readers
(`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`).

The numbers are computed by `improve_step.py` (mandatory-fail count, %-per-theme). This
file is the *interpretation*: which theme dominates, whether the prompt or the criteria
is at fault, and which technique rung to escalate to. The model names the dominant
theme; the script supplies the tally; the table below maps theme -> rung.

## 1. First gate: is it the prompt or the criteria? (criteria-vs-prompt guard)

Before changing the prompt, decide whether the *dataset* is the problem. Route to
`/je-dev-skills:prompt-evals-create-dataset` (do NOT rewrite the prompt) when:

- The judge complains about content that is **not in the inputs** (the case can't be solved).
- The rubric demands an **unstated style/format** the prompt was never told about.
- The judge's rationale **conflicts with the rubric** (the rubric itself is ambiguous).
- The answer needs **hidden domain knowledge** not provided to the prompt.

**Investigate** (possible prompt non-determinism, not a fix yet) when failures are
**inconsistent across similar cases** - same kind of input, divergent scores.

Do **NOT** route to create-dataset (it is a real prompt fix) when the prompt:
- **omitted instructions** the criteria clearly require,
- **ignored a stated format**, or
- **failed a recurring reasoning step**.

## 2. Mandatory criterion first

Any case scoring **<= 3** failed a mandatory criterion (the global `EXTRA_CRITERIA`, per
`prompts/grading.md`: "Any violation of a MANDATORY criterion forces a score of 3 or
below"). `improve_step.py` reports `mandatory_fail_count`. **Fix that gate before any
secondary-criteria polish** - a single mandatory miss caps the score no matter how good
the rest is.

## 3. Theme → next ladder rung

Map the **dominant** failure theme (the one the tally shows across the most cases) to the
cheapest technique rung that addresses it. Rungs are defined in
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/techniques.md`.

| Dominant failure theme | Tally key | Next rung to escalate to |
|---|---|---|
| Mandatory-criterion failures (score <= 3) | `mandatory_fail_count` | Fix that gate **first** |
| Missing required content | `missing_content` | Process steps; examples showing the requirement |
| Format / structure drift, inconsistency | `format_structure` | XML structure + multishot examples |
| Shallow / wrong reasoning on hard cases | `reasoning` | Adaptive thinking / reasoning scaffolding |
| Tone / style off | `tone_style` | Role framing + output guidelines + examples |
| Conflicting / ambiguous instructions | `conflicting` | Resolve the conflict (anti-pattern) - do not add more |

## 4. Priority + tie-break (the order improve_step.py applies)

When several themes are present, address them in this priority order:

1. Mandatory-criterion failures.
2. Failures across **>= 30%** of cases (`theme_pct >= 30`).
3. Largest score-impacting weakness.
4. Format / structure.
5. Tone / style.

**Ties -> earliest item** in this list, unless the user overrides. Pick the **minimum**
rung that fixes the diagnosed weakness - do not max out the ladder (see
`rewrite-procedure.md`).

## 5. Hand-off to the rewrite

Once the dominant theme and rung are chosen, follow
`${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-author/references/rewrite-procedure.md`
to produce the next prompt version + a short changelog of techniques applied.
