"""Deterministic loop logic for prompt-engineering-improve.

Reads a round's evals/runs/<label>/output.json + a loop-state JSON and emits the
per-round delta, the running best version id (argmax), a continue|stop verdict, a
diagnosis tally, and an EXTRA_CRITERIA freeze-guard. NO model calls; NO float math,
argmax, tally, freeze-check, or serialization is done by the SKILL prose - only here.

CLI:
    python3 improve_step.py --output-json <path> --loop-state <path> \
        [--delta-out <path>] [--check-freeze]
    python3 improve_step.py --loop-state <path> --check-freeze
    python3 improve_step.py --loop-state <path> --final-report-out <path> \
        [--held-out-output-json <path>] [--check-freeze]

Exit codes: 0 = continue; 1 = stop (a stopping rule fired); 2 = bad input /
freeze violation. Mirrors workflow-design-validate/scripts/validate_blueprint.py.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass


PASS_THRESHOLD = 7  # mirrors config.PASS_THRESHOLD; mandatory-fail per grading.md is score <= 3.
MANDATORY_FAIL_MAX = 3


def load_output_json(path: str) -> dict:
    """Load an evals/runs/<label>/output.json.

    Raises FileNotFoundError if absent, ValueError if it lacks the {summary,
    results} shape report.py writes.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "summary" not in data or "results" not in data:
        raise ValueError(
            f"{path}: not a report (expected top-level 'summary' and 'results')")
    if not isinstance(data["summary"], dict) or "average_score" not in data["summary"]:
        raise ValueError(f"{path}: 'summary' missing 'average_score'")
    return data


def load_loop_state(path: str) -> dict:
    """Load the small loop-state JSON.

    Raises FileNotFoundError if absent, ValueError if it lacks 'params' or
    'rounds'.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key in ("params", "rounds"):
        if key not in data:
            raise ValueError(f"{path}: loop-state missing '{key}'")
    return data


@dataclass
class RoundRecord:
    """One completed round's headline numbers (read from its output.json summary)."""
    version: str
    avg: float
    pass_rate: float


def compute_delta(*, current_avg: float, prior_avg: float | None) -> float | None:
    """Avg-score change vs. the prior round, rounded to 2 dp. None on the baseline."""
    if prior_avg is None:
        return None
    return round(current_avg - prior_avg, 2)


def running_best(rounds: list[RoundRecord]) -> RoundRecord | None:
    """The highest-avg round so far (argmax). Ties -> earliest (stable max by index)."""
    if not rounds:
        return None
    best = rounds[0]
    for r in rounds[1:]:
        if r.avg > best.avg:  # strict > keeps the earliest on a tie
            best = r
    return best


@dataclass
class LoopParams:
    """The five loop params (run_eval.py constants block) + pass_threshold (config)."""
    pass_threshold: int
    pass_rate_target: float
    max_rounds: int
    epsilon: float
    diminishing_return_rounds: int
    regression_band: float


@dataclass
class Verdict:
    decision: str           # "continue" | "stop"
    rule: str | None        # threshold | pass_rate | diminishing-returns-K | regression_band | max_rounds
    detail: str = ""


def load_loop_params(state: dict) -> LoopParams:
    """Load loop params with a clean ValueError for missing/malformed fields."""
    try:
        return LoopParams(**state["params"])
    except KeyError as exc:
        raise ValueError("loop-state missing 'params'") from exc
    except TypeError as exc:
        raise ValueError(f"loop-state params invalid: {exc}") from exc


def stop_verdict(rounds: list[RoundRecord], params: LoopParams, *, round_index: int) -> Verdict:
    """Decide continue|stop:<rule> from the completed rounds.

    If several rules fire, report the first in this priority order so
    success/regression beat the budget cap: threshold, pass_rate,
    regression_band, diminishing-returns-K, max_rounds. The caller keeps the
    best version regardless.

    round_index convention: 0-based, where the baseline is round 0 and the
    improvement rounds are 1..max_rounds.
    """
    if not rounds:
        return Verdict("continue", None, "no rounds yet")
    latest = rounds[-1]

    if latest.avg >= params.pass_threshold:
        return Verdict("stop", "threshold",
                       f"avg {latest.avg} >= pass_threshold {params.pass_threshold}")
    if latest.pass_rate >= params.pass_rate_target * 100:
        return Verdict("stop", "pass_rate",
                       f"pass_rate {latest.pass_rate}% >= target {params.pass_rate_target * 100}%")
    reg = _regression_rule(rounds, params)
    if reg is not None:
        return reg
    dim = _diminishing_rule(rounds, params)
    if dim is not None:
        return dim
    if round_index >= params.max_rounds:
        return Verdict("stop", "max_rounds",
                       f"round_index {round_index} reached cap {params.max_rounds}")
    return Verdict("continue", None, f"round_index {round_index} of cap {params.max_rounds}")


def _regression_rule(rounds, params):
    """Stop when latest is more than regression_band below the prior best."""
    if len(rounds) < 2:
        return None
    best = running_best(rounds[:-1])
    latest = rounds[-1]
    if best is not None and (best.avg - latest.avg) > params.regression_band:
        return Verdict(
            "stop", "regression_band",
            f"avg {latest.avg} is {round(best.avg - latest.avg, 2)} below best "
            f"{best.avg} (> band {params.regression_band}); revert to {best.version}")
    return None


def _diminishing_rule(rounds, params):
    """Stop when the last K consecutive per-round deltas are all below epsilon."""
    k = params.diminishing_return_rounds
    if len(rounds) < k + 1:
        return None
    deltas = [round(rounds[i].avg - rounds[i - 1].avg, 2) for i in range(1, len(rounds))]
    last_k = deltas[-k:]
    if all(d < params.epsilon for d in last_k):
        return Verdict(
            "stop", f"diminishing-returns-{k}",
            f"last {k} deltas {last_k} all < epsilon {params.epsilon}")
    return None


# Weakness-theme keyword table. Deterministic substring match over each verdict's
# 'weaknesses' strings. Mirrors references/diagnosis.md's themes. A case counts once
# per theme it matches. NOT a classifier - it tallies what the judge already wrote so
# the model can name the dominant theme against real counts.
THEME_KEYWORDS = {
    "missing_content": ["missing", "omitted", "absent", "did not include", "left out"],
    "format_structure": ["format", "structure", "inconsistent", "ordering", "schema"],
    "reasoning": ["reasoning", "logic", "incorrect", "wrong", "shallow"],
    "tone_style": ["tone", "style", "voice", "register", "verbose", "terse",
                   "filler", "boilerplate"],
    "conflicting": ["conflict", "ambiguous", "contradict", "unclear instruction"],
}

# Fabrication = content the model ADDED that the input does not support — the failure a
# positive instruction can't prevent (diagnosis.md routes it to the Rung 3 named-prohibition
# guardrail, not to more "be accurate" prose). It is high-priority, so precision matters and
# it needs morphology-aware, word-boundary matching that plain substrings cannot express.
# These patterns catch invent/invents/invented/inventing and "made up a <noun>" WITHOUT
# firing on "inventory", "made up of", creative-writing critiques, or criteria-problem
# phrasing ("content not in the input" = a §1 dataset problem, the opposite of fabrication).
FABRICATION_PATTERNS = [re.compile(p) for p in (
    r"\bfabricat",                                       # fabricate / -d / -ion
    r"\binvent(s|ed|ing)?\b",                            # invent / -s / -ed / -ing (not inventory)
    r"\bhallucinat",                                     # hallucinate / -d / -ion
    r"\bmade[- ]up\s+(?:a |an |the )?"
    r"(?:claim|fact|statistic|citation|quote|detail|number|source)",   # not "made up of"
    r"\bunsupported\s+(?:claim|fact|content|statistic|source|citation)",
)]


def diagnose_tally(results: list[dict]) -> dict:
    """Count mandatory-fails and percent-of-cases per weakness theme.

    Mandatory-fail means score <= 3, per grading.md. This is a pure tally over
    the verdict JSON - no model call.
    """
    total = len(results)
    if total == 0:
        return {"mandatory_fail_count": 0, "total_cases": 0,
                "mandatory_fail_pct": 0.0, "theme_pct": {}}
    mandatory = sum(1 for r in results if int(r.get("score", 0)) <= MANDATORY_FAIL_MAX)
    theme_hits = {theme: 0 for theme in THEME_KEYWORDS}
    theme_hits["fabrication"] = 0
    for r in results:
        weaknesses = " ".join(r.get("verdict", {}).get("weaknesses", [])).lower()
        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in weaknesses for kw in keywords):
                theme_hits[theme] += 1
        if any(p.search(weaknesses) for p in FABRICATION_PATTERNS):
            theme_hits["fabrication"] += 1
    theme_pct = {
        theme: round(100.0 * hits / total, 1)
        for theme, hits in theme_hits.items() if hits > 0
    }
    return {
        "mandatory_fail_count": mandatory,
        "total_cases": total,
        "mandatory_fail_pct": round(100.0 * mandatory / total, 1),
        "theme_pct": theme_pct,
    }


class FreezeViolation(RuntimeError):
    """Raised when EXTRA_CRITERIA changed after the freeze snapshot."""


def extra_criteria_hash(text: str | None) -> str:
    """SHA-256 of the stripped EXTRA_CRITERIA text. None -> hash of empty string."""
    normalized = (text or "").strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def assert_freeze(*, frozen_hash: str, current_text: str | None) -> str:
    """Assert EXTRA_CRITERIA is unchanged vs. the loop-start snapshot."""
    current = extra_criteria_hash(current_text)
    if current != frozen_hash:
        raise FreezeViolation(
            f"EXTRA_CRITERIA changed during the loop (frozen {frozen_hash[:12]}..., "
            f"now {current[:12]}...). Held-out claims are forfeit; regenerate a held-out set.")
    return current


def extra_criteria_text(
    *, state: dict, output: dict | None = None, require_output_meta: bool = False
) -> str | None:
    """Return the actual evaluated criteria text when the report records it."""
    if output is not None:
        meta = output.get("meta", {})
        if isinstance(meta, dict) and "extra_criteria" in meta:
            return meta.get("extra_criteria")
        if require_output_meta:
            raise ValueError("held-out output.json missing meta.extra_criteria")
    return state.get("extra_criteria")


def build_delta_payload(*, output: dict, state: dict) -> dict:
    """Assemble the deterministic delta.json payload from this round's output.json."""
    params = load_loop_params(state)
    summary = output["summary"]
    version = state.get("current_version", "v?")

    prior = state.get("rounds", [])
    if any(r.get("version") == version for r in prior):
        raise ValueError(
            f"loop-state rounds already include current_version {version!r}; "
            "rounds must contain prior completed rounds only")
    prior_records = [RoundRecord(version=r["version"], avg=r["avg"],
                                 pass_rate=r["pass_rate"]) for r in prior]
    prior_avg = prior_records[-1].avg if prior_records else None

    this_round = RoundRecord(version=version, avg=summary["average_score"],
                             pass_rate=summary["pass_rate"])
    all_rounds = prior_records + [this_round]
    round_index = len(all_rounds) - 1

    delta = compute_delta(current_avg=this_round.avg, prior_avg=prior_avg)
    best = running_best(all_rounds)
    verdict = stop_verdict(all_rounds, params, round_index=round_index)
    tally = diagnose_tally(output["results"])

    return {
        "version": version,
        "round_index": round_index,
        "delta": delta,
        "best": {"version": best.version, "avg": best.avg, "pass_rate": best.pass_rate},
        "verdict": {"decision": verdict.decision, "rule": verdict.rule, "detail": verdict.detail},
        "tally": tally,
        "params": asdict(params),
        "extra_criteria_hash": state.get("extra_criteria_hash", ""),
    }


def build_final_report(*, state: dict) -> dict:
    """Assemble the deterministic final-report.json for a finished loop."""
    params = load_loop_params(state)
    rounds_raw = state.get("rounds", [])
    records = [RoundRecord(version=r["version"], avg=r["avg"], pass_rate=r["pass_rate"])
               for r in rounds_raw]

    trace = []
    prior_avg = None
    for i, r in enumerate(rounds_raw):
        delta = compute_delta(current_avg=r["avg"], prior_avg=prior_avg)
        trace.append({
            "round_index": i,
            "version": r["version"],
            "avg": r["avg"],
            "pass_rate": r["pass_rate"],
            "delta": delta,
            "technique": r.get("technique", ""),
            "decision": r.get("decision", ""),
            "run_dir": r.get("run_dir", ""),
        })
        prior_avg = r["avg"]

    best = running_best(records)
    held = state.get("held_out")
    if held is None:
        held_out_run_count = 0
        held_out_result = "skipped"
    else:
        held_out_run_count = int(held.get("run_count", 0))
        if held_out_run_count > 1:
            raise ValueError(
                f"held_out.run_count must be <= 1, got {held_out_run_count}")
        held_out_result = held.get("result", "skipped")

    return {
        "name": state.get("name", ""),
        "params": asdict(params),
        "rounds": trace,
        "best_version": best.version if best is not None else None,
        "best": ({"version": best.version, "avg": best.avg, "pass_rate": best.pass_rate}
                 if best is not None else None),
        "held_out_run_count": held_out_run_count,
        "held_out_result": held_out_result,
        "extra_criteria_hash": state.get("extra_criteria_hash", ""),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic per-round loop logic for prompt-engineering-improve.")
    parser.add_argument("--output-json", required=False, default=None,
                        help="this round's evals/runs/<label>/output.json")
    parser.add_argument("--loop-state", required=True,
                        help="the loop-state JSON (params, prior rounds, frozen hash)")
    parser.add_argument("--delta-out", default=None,
                        help="where to write delta.json (default: alongside loop-state)")
    parser.add_argument("--final-report-out", default=None,
                        help="finalize mode: write the deterministic final-report.json "
                             "(round trace + best version + held_out_run_count + hash) "
                             "and exit; --output-json is not required in this mode")
    parser.add_argument("--held-out-output-json", default=None,
                        help="finalize mode: held-out run output.json to freeze-check "
                             "against its recorded meta.extra_criteria")
    parser.add_argument("--check-freeze", action="store_true",
                        help="assert EXTRA_CRITERIA hash unchanged before emitting")
    args = parser.parse_args(argv)

    if args.final_report_out is None and args.output_json is None and args.check_freeze:
        try:
            state = load_loop_state(args.loop_state)
            assert_freeze(frozen_hash=state.get("extra_criteria_hash", ""),
                          current_text=extra_criteria_text(state=state))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}")
            return 2
        except FreezeViolation as exc:
            print(f"FREEZE VIOLATION: {exc}")
            return 2
        print("freeze check: ok")
        return 0

    if args.final_report_out is not None:
        try:
            state = load_loop_state(args.loop_state)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}")
            return 2
        try:
            report = build_final_report(state=state)
        except (ValueError, TypeError, KeyError) as exc:
            print(f"ERROR: {exc}")
            return 2
        if report["held_out_run_count"] > 0:
            if not args.check_freeze:
                print("ERROR: --check-freeze is required when held_out.run_count > 0")
                return 2
            if args.held_out_output_json is None:
                print("ERROR: --held-out-output-json is required when held_out.run_count > 0")
                return 2
        if args.check_freeze:
            try:
                held_out_output = (
                    load_output_json(args.held_out_output_json)
                    if args.held_out_output_json is not None else None
                )
                assert_freeze(frozen_hash=state.get("extra_criteria_hash", ""),
                              current_text=extra_criteria_text(
                                  state=state,
                                  output=held_out_output,
                                  require_output_meta=report["held_out_run_count"] > 0))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"ERROR: {exc}")
                return 2
            except FreezeViolation as exc:
                print(f"FREEZE VIOLATION: {exc}")
                return 2
        try:
            with open(args.final_report_out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"ERROR: {exc}")
            return 2
        print(f"best version: {report['best_version']}")
        print(f"held_out_run_count: {report['held_out_run_count']}")
        print(f"wrote {args.final_report_out}")
        return 0

    if args.output_json is None:
        print("ERROR: --output-json is required unless --final-report-out is given")
        return 2
    try:
        output = load_output_json(args.output_json)
        state = load_loop_state(args.loop_state)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.check_freeze:
        try:
            assert_freeze(frozen_hash=state.get("extra_criteria_hash", ""),
                          current_text=extra_criteria_text(state=state, output=output))
        except FreezeViolation as exc:
            print(f"FREEZE VIOLATION: {exc}")
            return 2

    try:
        payload = build_delta_payload(output=output, state=state)

        delta_out = args.delta_out
        if delta_out is None:
            delta_out = os.path.join(os.path.dirname(args.loop_state) or ".", "delta.json")
        with open(delta_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2

    d = payload["delta"]
    print(f"delta: {d if d is not None else 'baseline (no prior)'}")
    print(f"best: {payload['best']['version']} (avg {payload['best']['avg']})")
    print(f"verdict: {payload['verdict']['decision']}"
          + (f":{payload['verdict']['rule']}" if payload['verdict']['rule'] else ""))
    print(f"mandatory-fails: {payload['tally']['mandatory_fail_count']}/"
          f"{payload['tally']['total_cases']}; themes: {payload['tally']['theme_pct']}")
    print(f"wrote {delta_out}")

    return 1 if payload["verdict"]["decision"] == "stop" else 0


if __name__ == "__main__":
    sys.exit(main())
