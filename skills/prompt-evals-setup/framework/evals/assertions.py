"""Deterministic structural assertions checked in code — cheaper and more reliable
than the LLM judge for must-haves with a definite shape (spec §13).

A standalone engine: given an output string + a list of assertion specs, return a
pass/fail result per assertion. Result keys are ``text``/``passed``/``evidence`` to
match skill-creator's grading.json convention (see CONTRIBUTING.md). Wiring this as a
pre-judge GATE inside the run loop is deferred to the run-path work — this engine is
the reusable core, callable from a run_function or as a post-run audit over output.json.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def check_assertion(output: str, spec: dict) -> dict:
    """Evaluate one assertion against ``output``. Raise ValueError on unknown type."""
    kind = spec.get("type")
    if kind == "contains":
        v = spec["value"]
        ok = v in output
        return {"text": f"contains {v!r}", "passed": ok, "evidence": f"{'found' if ok else 'missing'} {v!r}"}
    if kind == "not_contains":
        v = spec["value"]
        ok = v not in output
        return {"text": f"not_contains {v!r}", "passed": ok, "evidence": f"{'absent' if ok else 'found'} {v!r}"}
    if kind == "regex":
        p = spec["pattern"]
        m = re.search(p, output)
        return {"text": f"regex {p!r}", "passed": m is not None, "evidence": f"matched {m.group(0)!r}" if m else "no match"}
    if kind == "min_length":
        v = int(spec["value"])
        return {"text": f"min_length {v}", "passed": len(output) >= v, "evidence": f"len={len(output)}"}
    if kind == "max_length":
        v = int(spec["value"])
        return {"text": f"max_length {v}", "passed": len(output) <= v, "evidence": f"len={len(output)}"}
    if kind == "json_valid":
        try:
            json.loads(output)
            return {"text": "json_valid", "passed": True, "evidence": "valid JSON"}
        except (ValueError, TypeError):
            return {"text": "json_valid", "passed": False, "evidence": "invalid JSON"}
    if kind == "json_has_key":
        key = spec["key"]
        try:
            data = json.loads(output)
        except (ValueError, TypeError):
            return {"text": f"json_has_key {key!r}", "passed": False, "evidence": "invalid JSON"}
        ok = isinstance(data, dict) and key in data
        return {"text": f"json_has_key {key!r}", "passed": ok, "evidence": f"{'present' if ok else 'missing'} key {key!r}"}
    raise ValueError(f"unknown assertion type: {kind!r}")


def check_assertions(output: str, specs: list[dict]) -> list[dict]:
    return [check_assertion(output, s) for s in specs]


def all_passed(results: list[dict]) -> bool:
    return all(r["passed"] for r in results)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run structural assertions against an output file.")
    ap.add_argument("--output-file", required=True, help="path to the text output to check")
    ap.add_argument("--assertions", required=True, help="path to a JSON list of assertion specs")
    args = ap.parse_args(argv)
    try:
        output = Path(args.output_file).read_text(encoding="utf-8")
        specs = json.loads(Path(args.assertions).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    results = check_assertions(output, specs)
    for r in results:
        print(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['text']} — {r['evidence']}")
    return 0 if all_passed(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
