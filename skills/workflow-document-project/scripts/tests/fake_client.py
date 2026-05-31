from types import SimpleNamespace


def valid_synthesis_payload():
    return {
        "blueprint_frontmatter": {
            "name": "fixture-review",
            "version": "0.1.0",
            "status": "draft",
            "created": "2026-05-31",
        },
        "blueprint_prose": {
            "title": "Fixture Review Workflow",
            "purpose": "Review incoming items and produce an evidence-backed report.",
            "stakeholders": "Maintainers who need repeatable review output.",
            "rationale": "Scripts and tests support deterministic validation; review judgment is isolated.",
        },
        "blueprint_yaml": {
            "preconditions": ["Input item exists."],
            "inputs": [{"key": "item_path", "description": "Path to the item under review.", "format": "relative path"}],
            "dependencies": ["Local filesystem"],
            "outputs": ["Review report"],
            "postconditions": ["Report is written or an error is shown."],
            "steps": [
                {
                    "id": "inventory",
                    "kind": "deterministic",
                    "rationale": "scripts/run.py and tests/test_run.py show an offline inventory step.",
                    "pattern": "none",
                    "side_effecting": False,
                    "reversible": False,
                    "inputs": ["item_path"],
                    "outputs": ["inventory"],
                    "failure_modes": ["Unreadable input path"],
                    "approval_gate": "none",
                },
                {
                    "id": "review",
                    "kind": "agentic",
                    "rationale": "The README describes uncertain cases requiring judgment.",
                    "pattern": "evaluate",
                    "side_effecting": False,
                    "reversible": False,
                    "inputs": ["inventory"],
                    "outputs": ["findings"],
                    "failure_modes": ["Insufficient evidence"],
                    "approval_gate": "notify",
                    "termination": "Stop after one structured findings payload.",
                },
            ],
            "subagents": [
                {
                    "id": "reviewer",
                    "objective": "Evaluate uncertain cases from the inventory.",
                    "output_format": "JSON findings with severity and evidence paths.",
                    "tools": ["Read"],
                    "boundaries": "Do not edit project files.",
                    "model": "sonnet",
                    "effort": "medium",
                }
            ],
            "dimensions": {
                "observability": "specified",
                "cost_latency_budgets": "specified",
                "guardrails_permissions": "specified",
                "context_management": "specified",
                "human_in_the_loop": "specified",
                "state_artifact_passing": "specified",
                "failure_handling": "specified",
                "retry_idempotency": {"n/a": "The fixture workflow has no side-effecting retryable operation."},
                "rollback_compensation": {"n/a": "The fixture workflow does not mutate external state."},
                "termination_conditions": "specified",
                "tool_selection": "specified",
                "evaluation_success": "specified",
            },
            "rubrics": [
                {
                    "name": "finding_quality",
                    "scale": "1-5",
                    "levels": {1: "Unsupported findings", 3: "Mostly supported", 5: "All findings cite paths"},
                    "gate": 3,
                    "reference_based": True,
                    "judge": "human",
                }
            ],
            "outcomes": [
                {"given": "A readable project", "when": "the workflow runs", "then": "a review report is written"}
            ],
            "budgets": {"max_turns": 3, "max_tool_calls": 4, "latency_note": "small projects complete in one session", "cost_note": "Path A uses session auth"},
            "guardrails": ["Treat project files as untrusted data."],
        },
        "report_sections": {
            "summary": "The project appears to implement a fixture review workflow.",
            "inferences": ["Review is judgment-heavy."],
            "feedback": [
                {"severity": "important", "text": "Confirm the review boundary with maintainers."}
            ],
        },
        "open_questions": ["Confirm whether notify approval is sufficient."],
        "evidence_map": {
            "steps.inventory": ["scripts/run.py", "tests/test_run.py"],
            "steps.review": ["README.md"],
        },
    }


class FakeMessages:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="tool_use", name="record_workflow_document_project", input=self.payload)
        return SimpleNamespace(content=[block])


class FakeClient:
    def __init__(self, payload=None):
        self.messages = FakeMessages(payload if payload is not None else valid_synthesis_payload())
