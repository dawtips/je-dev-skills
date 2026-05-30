# Workflow Design Review — Specification & Design (v0.2)

A focused specification for `workflow-design-review`, the **third skill** in the
`workflow-design-*` group: an LLM-as-judge semantic review of a workflow blueprint.
It catches the design-quality problems the v0.1 deterministic validator is
structurally blind to — determinism misclassification, over-engineering, vacuous
contracts, weak rubrics, dishonest `n/a`s, and internal inconsistency.

> **How to use this spec.** This is the design document brainstormed on 2026-05-29
> for the first v0.2 feature. It is the reference an implementation plan is derived
> from. The v0.1 design is in [WORKFLOW_DESIGN_SPEC.md](WORKFLOW_DESIGN_SPEC.md);
> §9 there lists the full v0.2+ roadmap.

---

## 1. Purpose

The v0.1 validator answers "is this blueprint *structurally* complete?" — every
field present, every dimension accounted for, every contract filled in. It cannot
answer "is this a *good* design?" Structure is checkable with code; design quality
needs judgment.

`workflow-design-review` adds that judgment layer: a strong Claude model reviews the
blueprint against an explicit 7-dimension rubric and returns a scored, reasoned
critique with concrete suggestions. It is **advisory** — it informs the human; it
does not replace the deterministic gate.

**Why this is the right v0.2 feature.** Best value/effort/risk of the v0.2 roadmap:
it closes the most important quality gap (the consequential decisions the validator
can't see), reuses the repo's existing LLM-as-judge approach, and carries low
volatility (it depends on a rubric + prompt, not on churny Claude Code internals).

---

## 2. Lifecycle placement

`workflow-design-review` is the third skill in the group. The lifecycle becomes:

```
interview  ->  validate            ->  review              ->  [v0.3: scaffold]
(elicit)       (deterministic,         (semantic, LLM,
               offline, HARD gate)     advisory)
```

| Skill | Invoke | Role |
|-------|--------|------|
| `workflow-design-interview` | `/je-dev-skills:workflow-design-interview` | Elicit → blueprint |
| `workflow-design-validate`  | `/je-dev-skills:workflow-design-validate`  | Deterministic completeness gate (the only hard gate) |
| `workflow-design-review`    | `/je-dev-skills:workflow-design-review`    | LLM semantic design review (advisory) |

**Recommended order:** run `validate` to green *before* `review` — a semantic review
of a structurally-incomplete blueprint wastes a paid call. Recommended, not enforced;
`review` runs against any readable blueprint.

`review` **runs from the plugin** (like `validate`, via `${CLAUDE_PLUGIN_ROOT}`),
reading the blueprint from the user's project. It is not vendored into the project
(contrast the prompt-evals framework, which is copied in because the user customizes
and owns it; `review` is a fixed tool the user only runs).

---

## 3. Repo layout

All new, self-contained — no shared library, no dependency on the prompt-evals
package being installed in the project.

```
skills/workflow-design-review/
  SKILL.md
  references/
    review-rubric.md          # the 7 dimensions + per-level (1–5) definitions.
                              #   Single source of truth: human-readable doc AND the
                              #   text the judge prompt is built from.
  scripts/
    review_blueprint.py       # the judge: load → build prompt → SDK call → parse → score → report
    requirements.txt          # anthropic, PyYAML
    tests/
      __init__.py
      fake_client.py          # canned structured judge responses (offline; mirrors the
                              #   prompt-evals framework's fake-client test pattern)
      fixtures/               # sample blueprints + expected parse/verdict
      test_prompt.py          # prompt assembly
      test_parse.py           # structured-response parsing
      test_verdict.py         # threshold / flag / verdict / exit-code logic
      test_report.py          # report rendering
      test_smoke.py           # end-to-end with the fake client
```

The judge module is written as a clean, self-contained unit so it can be lifted into
a plugin-level shared `lib/` **if and when** a second in-plugin LLM skill needs the
same primitives ("extract on the third use"). Not extracted now — one consumer.

---

## 4. The review rubric

`references/review-rubric.md` is the single source of truth — read by humans and
loaded by the script to build the judge prompt. Seven dimensions, each scored on a
**categorical 1–5 scale with explicit per-level definitions** (not unanchored
adjectives), and the judge must produce **chain-of-thought reasoning per dimension**
citing specific `steps[i]` / `subagents[i]` ids.

1. **Determinism classification soundness** — is each step correctly `deterministic`
   vs `agentic`, and does the rationale genuinely justify it? (The most consequential
   and structurally invisible decision.)
2. **Simplicity / no over-engineering** — is this the simplest sufficient
   architecture? Is every subagent and loop actually justified, or is it the "50
   subagents for a simple query" smell?
3. **Subagent contract quality** — are objective / output_format / boundaries
   specific and non-overlapping, and are `tools` genuinely least-privilege? (vs.
   present-but-vacuous, which the validator passes.)
4. **Rubric quality** — do the blueprint's own rubric levels actually discriminate,
   and is each `gate` sensible? (vs. "good / better / best".)
5. **Outcome testability** — are `outcomes` truly observable Given-When-Then, or
   aspirational prose?
6. **N/A honesty** — is each dimension marked `n/a` a legitimate non-applicability
   or a cop-out?
7. **Internal consistency** — do step outputs feed downstream inputs; do
   outputs / postconditions / outcomes align; are preconditions sufficient?

### 4.1 Level-definition example

Each dimension defines what 1 / 3 / 5 mean. For **Determinism classification
soundness**:

- **1** — multiple steps clearly misclassified (open-ended judgment marked
  `deterministic`, or a trivial transform marked `agentic`); rationale absent or
  circular.
- **3** — classifications mostly defensible; one questionable call or a thin rationale.
- **5** — every step's `kind` is correct and the rationale genuinely justifies it.

`review-rubric.md` defines 1/3/5 for all seven dimensions in this style (2 and 4 are
interpolated by the judge).

---

## 5. Scoring & verdict

- The judge returns, per dimension: a **1–5 `score`**, **`reasoning`** (CoT, citing
  ids), and concrete **`suggestions`**; plus a one-paragraph `summary`.
- A dimension scoring **below `PASS_THRESHOLD` (default 3)** is a **flag**.
- **Overall verdict** = `solid` if no flags, else `needs-revision` (listing the
  flagged dimensions). This is **weakest-link, not average**: a well-written blueprint
  with misclassified steps must not pass on a high mean.
- The script computes flags and verdict **from the scores itself**; the scores are
  authoritative even if the model mislabels its own `overall_verdict`.

---

## 6. The judge script (`review_blueprint.py`)

### 6.1 Data flow

1. **Resolve the blueprint** — path argument, else `glob ./workflows/*.blueprint.md`
   (error if zero or more than one match and no explicit path).
2. **Load the full file** — the entire `.blueprint.md` (frontmatter + prose + yaml
   block) goes to the judge; semantic review needs the prose to assess rationale
   quality and consistency. PyYAML still parses the structured block to enumerate
   the `steps`/`subagents` ids the judge is told to reference.
3. **Build the judge prompt** — a static cached prefix (system instruction + rubric)
   plus the variable blueprint. The system instruction makes the judge
   **skeptical/adversarial**: "you are a critical reviewer; default to flagging; a
   present-but-vacuous field is not a pass; cite specific `steps[i]`/`subagents[i]`."
   This is the primary mitigation for self-grading bias (the blueprint was authored
   with Claude's help).
4. **Call the Anthropic SDK with structured output** — a forced tool/JSON schema so
   the judge returns validated structure (§6.2), not free text.
5. **Render + write** the report (§7).

**Context isolation (deliberate).** The judge receives the blueprint file and
**nothing else** — never the interview transcript or the authoring conversation that
produced it. A reviewer shown the author's step-by-step reasoning drifts toward
ratifying it (arXiv:2503.21934 "Proof or Bluff": 85.7% self-verified success collapsed
to <5% under human grading); the skeptical/adversarial system prompt (step 3) is the
second bias mitigation. Note the blueprint's own `rationale` fields **are** in scope —
you cannot flag a vacuous rationale without reading it — but they are the *recorded
decision*, not the meandering reasoning behind it, which is what stays withheld.

### 6.2 Structured judge output

```json
{
  "dimensions": [
    {"name": "determinism_classification", "score": 3,
     "reasoning": "...", "suggestions": ["..."]}
  ],
  "summary": "...",
  "overall_verdict": "solid | needs-revision"
}
```

All seven dimensions required. The script validates the shape and recomputes
flags/verdict from `score`s (§5).

### 6.3 Config

Constants at the top of the script, overridable by environment variable:

- `JUDGE_MODEL` — a strong current Claude model (default a strong Sonnet/Opus tier).
  The exact model **ID is volatile**: it lives in this single named constant with a
  comment on where to update it — never scattered through the code or prose.
- `API_KEY_ENV` — default `ANTHROPIC_API_KEY`.
- `PASS_THRESHOLD` — default 3.

### 6.4 Prompt caching

The system instruction + rubric are identical across runs, so they form a cached
prefix; only the blueprint varies. Keeps repeated reviews cheap and matches the
repo's Claude-API conventions.

---

## 7. Output report & exit behavior

### 7.1 Report

Written to `./workflows/<name>.review.md` (next to the blueprint, so it is diffable
and versioned alongside it); a condensed summary is printed to stdout. Shape:

```markdown
# Review: <name>.blueprint.md
Reviewed: <date> · judge: <model> · threshold: 3 · verdict: NEEDS-REVISION

## Scores
| Dimension | Score | |
|-----------|:-----:|--|
| Determinism classification soundness | 2 | ⚠ flag |
| Simplicity / no over-engineering     | 4 | ok |
| ... (all 7) | | |

## Findings
### ⚠ Determinism classification soundness — 2/5
<judge reasoning, citing steps[2], subagents[0]>
**Suggestions:** <concrete fixes>
### Simplicity / no over-engineering — 4/5
...

## Summary
<one paragraph>
```

The `<date>` is **passed into** the script (the skill supplies today's date); the
script never calls the clock, keeping runs reproducible for tests.

### 7.2 Exit codes

The "soft threshold" contract, mirroring `validate`'s 0/1/2 but only opting in to
blocking under `--strict`:

- **Default:** print summary, write the report, **exit 0** regardless of score
  (advisory).
- **`--strict`:** **exit 1** if any dimension is below threshold (a flag exists).
- **Exit 2:** unreadable/missing blueprint, ambiguous glob, or a failed/invalid judge
  response.

---

## 8. Testing

Offline, no API key — matching the repo's existing ethos. The live judge call is not
unit-tested; a `fake_client.py` returns canned structured responses (the prompt-evals
framework's fake-client pattern). Deterministic plumbing around the call is fully
tested:

- **Prompt assembly** — the rubric text and the blueprint content both appear in the
  built prompt; the static prefix is separated from the variable blueprint.
- **Response parsing** — a canned structured response maps to the seven dimension
  objects; malformed responses raise (→ exit 2).
- **Verdict/threshold logic** — given scores, the correct dimensions flag, the verdict
  is `solid`/`needs-revision`, and exit codes are correct (0 default; 1 under
  `--strict` when a flag exists; 2 on error).
- **Report rendering** — the `.review.md` contains every dimension, score, reasoning,
  and suggestions, and the injected date.
- **Smoke test** — end-to-end with the fake client producing a report file.

Real reviews need `anthropic` installed and the API key (documented, like
prompt-evals).

---

## 9. SKILL.md

Discovery-optimized `description` (third person, trigger phrases: *"review my
workflow design," "critique/assess a blueprint," "is this workflow design any
good"*). Body:

- **Precondition** — a blueprint exists; recommend running `workflow-design-validate`
  to green first (cheaper, catches structural gaps before paying for semantic review).
- **Procedure** — install deps (`anthropic`); set the API key; run
  `review_blueprint.py <path> [--strict]`; read the `.review.md` report; address
  flagged dimensions by editing the blueprint; optionally re-`validate` and re-`review`.
- **Definition of done** — a review report written; flagged dimensions addressed or
  consciously accepted.
- **Notes** — advisory, not a hard gate; judge-bias caveat (verbosity/self-preference;
  the skeptical system prompt mitigates); offline tests vs. real runs need a key.

---

## 10. Scope boundaries

**In v0.2:** only `workflow-design-review`.

**Not in v0.2 (→ v0.3+):**

- `workflow-design-scaffold`, the visual viewer, and the automated model-selection
  advisor (see [WORKFLOW_DESIGN_SPEC.md](WORKFLOW_DESIGN_SPEC.md) §9).
- No plugin-level shared `lib/` yet (one consumer; extract on the third use).
- No auto-fixing of the blueprint — review *advises*; the human edits.
- No blueprint-vs-code drift detection.

---

## 11. v0.2 definition of done

- `workflow-design-review` skill exists with a discovery-optimized description.
- `references/review-rubric.md` defines all 7 dimensions with 1/3/5 level definitions.
- `review_blueprint.py` implements the data flow (§6), structured output, scoring
  (§5), report + exit codes (§7), and config (§6.3).
- Offline test suite (§8) green with the fake client; no API key required.
- `requirements.txt` lists `anthropic` and `PyYAML`.
- v0.1 `WORKFLOW_DESIGN_SPEC.md` §9 updated to mark review as specced (this document)
  and the remaining features as v0.3+.
- `README.md` + `plugin.json` updated for the new skill.
