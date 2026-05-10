from pathlib import Path


def test_plan_only_node_uses_intelligent_planner_service():
    text = Path("core/workflow/nodes/planning.py").read_text(encoding="utf-8")

    assert "create_plan_from_state" in text
    assert "build_plan_from_capability_map(" not in text


def test_intelligent_planner_does_not_import_ui_or_execute_tools():
    text = Path("core/services/intelligent_planner.py").read_text(encoding="utf-8")

    forbidden = [
        "streamlit",
        "core.ui_adapter",
        "execute_analysis_tool",
        "execute_node",
        ".run(",
    ]

    offenders = [term for term in forbidden if term in text]
    assert offenders == []
