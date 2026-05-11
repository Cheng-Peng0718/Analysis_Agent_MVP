from pathlib import Path


def test_graph_state_declares_plan_runtime_fields():
    text = Path("core/state.py").read_text(encoding="utf-8")

    expected = [
        "pending_plan",
        "plan_status",
        "plan_execution_status",
        "current_plan_step_id",
        "action_origin",
    ]

    for name in expected:
        assert name in text