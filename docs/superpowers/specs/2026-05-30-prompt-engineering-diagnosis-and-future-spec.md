# Prompt-Engineering Diagnosis Handoff & Future Enhancements — Specification

A design contract for the prompt-engineering skill group's **diagnosis intelligence**:
one concrete near-term fix (restore the single-pass diagnosis handoff in
`prompt-evals-run`) and the deferred §8 future-enhancement roadmap (agentic technique
catalogue, held-out split, message-role frontmatter, re-measure-on-tie).

> **Tickets covered:** [T-020] Restore `prompt-evals-run` Task 17 diagnosis handoff
> (phase `prompt-engineering`, near-term), [T-017] prompt-engineering §8 future
> enhancements (phase `backlog`, deferred).
>
> **Parent spec.** `2026-05-29-prompt-engineering-skills-design.md` — §4/§7 own the
> diagnosis seam, §8 owns the future-enhancements list. This spec makes T-020 buildable
> now and records the §8 roadmap as a tracked-but-deferred contract.

---

## 1. Purpose & why grouped

Both tickets concern the **diagnosis→technique intelligence** shared across
`prompt-evals-run` and `prompt-engineering-improve`. T-020 is a precise, verifiable
near-term fix to the *handoff* wording; T-017 is the deferred roadmap of *intelligence*
upgrades to that same seam. Grouping them keeps the one diagnosis contract in a single
document — but they ship on **different clocks**: T-020 now, T-017 only when a concrete
need arises.

---

## 2. T-020 — Restore the single-pass diagnosis handoff (near-term)

### 2.1 Goal
Implement **Task 17** from the (deleted, ephemeral) plan
`docs/superpowers/plans/2026-05-29-prompt-engineering-skills.md`: re-scope the current
`skills/prompt-evals-run/SKILL.md` *Diagnose/iterate* section to a **single-pass
diagnosis handoff** — not an in-skill multi-round improvement loop.

### 2.2 Required edits to `skills/prompt-evals-run/SKILL.md`
The Diagnose/iterate section must:

1. Be **single-pass**: "here's what's wrong; fix and re-run" — it diagnoses once and
   hands off, rather than owning the iterate loop.
2. **Restore the explicit citation** to
   `${CLAUDE_PLUGIN_ROOT}/skills/prompt-engineering-improve/references/diagnosis.md`
   (the shared diagnosis→technique reference — one physical home, two readers, per the
   parent spec §4/§7).
3. **Name the `criteria-vs-prompt guard`** (distinguish "the prompt is wrong" from "the
   success criteria are wrong" before recommending a rewrite).
4. Keep the **mandatory-criterion-first** guidance (diagnose cases failing a mandatory
   criterion first; parent spec §4).
5. **Point users to `/je-dev-skills:prompt-engineering-improve`** when they want the
   **automated multi-round loop** (that skill owns the loop; `prompt-evals-run` only
   diagnoses single-pass and hands off).
6. **Leave the later Path A / Path B substrate wording intact** (no changes to it).

### 2.3 Verification (from the ticket — structural, deterministic)
Structural grep of the edited `SKILL.md` must find all of:

- `single-pass`
- `prompt-engineering-improve/references/diagnosis.md`
- `prompt-engineering-improve to automate`
- `criteria-vs-prompt guard`

And confirm **no changes** under:

- `skills/prompt-evals-setup/framework/evals/evaluator`
- `skills/prompt-evals-setup/framework/evals/prompts`

### 2.4 Definition of done (T-020)
All six edits present; all four grep tokens found; the two no-change paths confirmed
untouched; skill linter passes with actual output shown.

---

## 3. T-017 — §8 future enhancements (deferred roadmap)

Tracked-but-deferred per the parent spec §8. Each is **additive** to the shipped v1 and
pursued only when a concrete need appears — this section is the contract for *what* each
means and *what gates it*, not a build order.

### 3.1 Agentic technique catalogue + trajectory-aware diagnosis
Extend the technique catalogue and the diagnosis mapping beyond single-shot prompts to
**agentic** prompts (system prompts, tool descriptions, process/trajectory grading). The
eval substrate is already agentic-capable on the keyed path (`Trajectory`); this is the
*authoring/diagnosis* layer catching up. **Gate:** a real agentic-prompt authoring need
on the keyed path.

### 3.2 Built-in held-out split
A framework-native train/held-out split, replacing the v1 "use a separate second dataset"
approach. Must follow `skill-creator/scripts/run_loop.py`'s **overfitting-aware
selection** — 60/40 split, sample each case for a reliable rate, and **select the best
version by held-out score, not training score** (methodology-transferable, not a code
drop-in; parent spec §8 addendum). Must preserve the hardened held-out invariants (parent
spec §6: runs once, `held_out_run_count ≤ 1`, `EXTRA_CRITERIA` frozen before any held-out
run, independence of scenarios). **Gate:** demand for built-in split ergonomics over the
documented second-dataset workflow.

### 3.3 Message-role frontmatter (`system:` / `user_template:`)
A real `system`/`user` message split via prompt frontmatter, replacing v1's in-text
"role" convention (parent spec §5). **Gate:** a prompt whose system/user split materially
changes grading and cannot be expressed in-text.

### 3.4 Re-measure-on-tie smoothing
On a tie between prompt versions, average **K re-grades** to break it, instead of the
current deterministic tie-break in `improve_step.py` (parent spec §6/§7 note it as a
deferred option to keep cost bounded). **Gate:** observed tie instability the
deterministic tie-break handles poorly. **Note:** this overlaps the eval framework's
variance work (`2026-05-30-eval-live-path-integration-spec.md` T-019 / `variance.py`'s
`suggested_regression_band`) — prefer consuming the variance band over a bespoke
re-measure path if that lands first.

### 3.5 Deferred-roadmap definition of done
T-017 stays **open** as a tracked backlog item. "Done" for each sub-item = its gate fires,
it is split into its own ticket + (if non-obvious) spec, built with the parent spec's
determinism/held-out invariants intact, and this section is updated to point at it.

---

## 4. Shared design rules

1. **One diagnosis home, two readers.** The diagnosis→technique mapping, the
   criteria-vs-prompt guard, and mandatory-criterion-first all live in the single shared
   `prompt-engineering-improve/references/diagnosis.md`; `prompt-evals-run` cites it,
   never forks it (parent spec §4/§7).
2. **Single-pass run, automated loop elsewhere.** `prompt-evals-run` diagnoses once and
   hands off; `prompt-engineering-improve` owns the multi-round loop. T-020 enforces this
   boundary in the SKILL prose.
3. **Determinism preserved.** Any §8 item touching loop math (held-out selection, tie
   smoothing) keeps the closed-form, offline-tested `improve_step.py` discipline.
4. **Prefer consuming shipped cores.** §3.4 re-measure should reuse the variance band, not
   re-implement variance.

---

## 5. Scope boundaries

- **T-020 is the only buildable item now.** T-017 remains a deferred backlog contract;
  do not build §3 items speculatively.
- **Not here:** the eval *engine* changes those §8 items would consume — variance band
  (T-019), held-out mechanics already shipped in the framework. This spec owns the
  prompt-engineering-side intelligence, not the eval substrate.
- **Not here:** any change to `evaluator/` or `prompts/` under
  `prompt-evals-setup/framework` (T-020 explicitly forbids it; §2.3).
