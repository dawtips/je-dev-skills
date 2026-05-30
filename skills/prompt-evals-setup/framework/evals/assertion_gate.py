"""Assertion gating orchestration for deterministic pre-judge checks."""

from evals.assertions import check_assertions


ASSERTION_POLICIES = {"gate_mandatory", "annotate_only"}
ASSERTION_SEVERITIES = {"mandatory", "advisory"}
ASSERTION_ACTION_OVERRIDES = {"gate", "annotate"}


def evaluate_assertion_gate(output: str, assertions: list[dict], policy: str = "gate_mandatory") -> dict:
    """Run structural assertions and decide whether the LLM judge should be skipped."""
    if policy not in ASSERTION_POLICIES:
        raise ValueError(f"unknown assertion gate policy: {policy!r}")

    for assertion in assertions:
        severity = assertion.get("severity")
        if severity not in ASSERTION_SEVERITIES:
            raise ValueError(f"unknown assertion severity: {severity!r}")
        assertion_policy = assertion.get("policy")
        if assertion_policy is not None and assertion_policy not in ASSERTION_ACTION_OVERRIDES:
            raise ValueError(f"unknown assertion policy override: {assertion_policy!r}")
        if severity == "advisory" and assertion_policy == "gate":
            raise ValueError("gate override is invalid for advisory assertions")
        if policy == "annotate_only" and assertion_policy == "gate":
            raise ValueError("gate override is invalid under annotate_only policy")

    checked = check_assertions(output, assertions)
    results = []
    mandatory_failed = False
    judge_skipped = False

    for assertion, result in zip(assertions, checked):
        severity = assertion["severity"]
        action = _action_for_assertion(assertion, result, policy)
        enriched = dict(result)
        enriched["severity"] = severity
        enriched["action"] = action
        results.append(enriched)

        if severity == "mandatory" and not result["passed"]:
            mandatory_failed = True
        if action == "gate" and not result["passed"]:
            judge_skipped = True

    return {
        "policy": policy,
        "results": results,
        "mandatory_failed": mandatory_failed,
        "judge_skipped": judge_skipped,
    }


def synthetic_gated_verdict(gate: dict) -> dict:
    """Return the deterministic score floor used when assertion gating skips judging."""
    weaknesses = [
        f"{result['text']}: {result['evidence']}"
        for result in gate["results"]
        if result["action"] == "gate" and not result["passed"]
    ]
    return {
        "score": 1,
        "strengths": [],
        "weaknesses": weaknesses,
        "reasoning": "Skipped judge because mandatory assertions failed.",
    }


def _action_for_assertion(assertion: dict, result: dict, policy: str) -> str:
    if assertion.get("policy") is not None:
        return assertion["policy"]
    if policy == "gate_mandatory" and assertion["severity"] == "mandatory" and not result["passed"]:
        return "gate"
    return "annotate"
