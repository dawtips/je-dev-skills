# Session handover — code-review audit + fix wave (plugin 0.3.2 → 0.3.7)

## What this session did

Ran a full `/code-review` deep audit of the plugin, then shipped the actionable findings as five focused PRs (all merged to `main`, Codex-reviewed), introduced a versioning convention, and logged the one deferred item as a ticket.

### Audit
Four parallel `code-reviewer` agents (one per skill cluster) ran all 7 passes. Result: **0 CRITICAL after disciplined severity review** — a mature, well-tested codebase. The eval-framework agent's three "CRITICAL"s were downgraded after I verified the architecture: the framework is **plugin-resident, never copied into projects** (the README's "copied into a project" line was stale and was fixed). Findings were grouped into batches.

### Merged PRs
- **#6 (batch 1, WARN/PRUNE):** stale model IDs `4-5/4-1 → 4-6/4-8` in `advise_model.py` + `citations.md`; `client._NO_SAMPLING_PREFIXES` → minor-version parse (Opus 4.7+ only; 2 Codex P2 rounds: 4.6 family over-reach, then snapshot-date misparse); reject `gate: 0` in `scaffold.py`; add 3 missing test suites to the AGENTS.md gate; `python`→`python3` in 3 SKILL.md run commands; fix advise→citations ref path; README plugin-resident correction; `skill_lint` single-read.
- **#7 (batch 2):** `live_run` per-case resilience — one bad/transient case (429, malformed grade, hung adapter) is recorded as a scored-1 result with an `error` field + `meta.errors` instead of aborting the whole run; `run_command_adapter` gains `config.ADAPTER_TIMEOUT_SECONDS`. 3 Codex P2 rounds, all the same principle: deterministic config/schema/contract errors must fail loudly (added `_validate_cases` up-front type+presence validation; re-raise `MissingPlaceholderError`), only transient runtime errors get isolated.
- **#8 (batch A):** `document_project.write_artifacts` is now truly all-or-nothing (stage to unique `mkstemp` temps → publish → roll back the blueprint if the project-doc rename fails); every `OSError` → clean exit-2 `DocumentProjectError`; frontmatter rendered via `yaml.safe_dump` (was f-string concat); validator failures warn on stderr instead of silently reading `not run`. 3 Codex P2 rounds (second-rename gap, then fixed `.bak` clobbering a user's backup → unique names).
- **#9 (batch B, WR-018):** `agent-build-scaffold` tests now run the generated bash artifacts via an explicit `bash` (skip if none on PATH) and normalize path separators — **30/30 green on Windows-native Python** (was 26/4). Codex clean first try.
- **#10 (batch C1, PRUNE):** removed dead `PromptEvaluator.run_evaluation` (+ unused imports; kept `_map`), inlined `report_analyst.analysis_from_paths`, deleted unused `variance_runner.output_paths_for_labels` + its test, fixed 2 stale docstrings + the framework spec's minimal-usage flow (→ `live_run.run_evaluation`). Net ≈ −77 LOC.

### Conventions / process
- New **Versioning** section in `AGENTS.md`: after every PR merge, bump the plugin version with a direct commit to `main` (semver), keeping **both** `.claude-plugin/plugin.json` and `marketplace.json` `plugins[].version` identical. Applied after each merge (0.3.2 → 0.3.7). One miss caught by the user: I'd bumped only plugin.json once — both files are now synced and the rule names both.
- Worktree-per-stream throughout (`.worktrees/<slug>`), removed after each verified local merge.

### Remaining
- **T-025 (open, backlog):** split the 812-line `document_project.py` into focused modules (no behavior change; the 35-test suite is the gate). Deferred — most churn for least functional gain. This is the only open audit item.

## State at handover
- `main` @ green: `skill_lint` 14/0/0, all offline suites pass, framework smoke PASS.
- Plugin version **0.3.7** (both files synced).
- No active branches/worktrees; all 5 PRs merged + remote branches deleted.

## Notes for next session
- Codex auto-review was flaky on PR #8 (needed a manual `@codex review` once); the others auto-reviewed. Poll reactions/reviews/inline-comments; 👍 = clean.
- storybloq tickets MUST be created via `storybloq ticket create`, not by writing the JSON directly — a hand-written T-025.json was silently skipped (it omitted the `completedDate` field storybloq's schema requires). The MCP storybloq server is rooted at the session launch dir (WinGet), not this repo, so drive storybloq via the CLI here.
