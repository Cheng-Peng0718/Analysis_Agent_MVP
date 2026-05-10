from pathlib import Path


def test_legacy_interaction_intent_has_no_phrase_pattern_lists():
    text = Path("core/interaction_intent.py").read_text(encoding="utf-8")

    forbidden = [
        "ADVISORY_PATTERNS",
        "PLAN_ONLY_PATTERNS",
        "EXECUTE_PLAN_PATTERNS",
        "DIRECT_TOOL_PATTERNS",
    ]

    offenders = [term for term in forbidden if term in text]
    assert offenders == []


def test_workflow_interaction_node_uses_structured_router_service():
    text = Path("core/workflow/nodes/interaction.py").read_text(encoding="utf-8")

    assert "decide_interaction_intent" in text
    assert "intent_decision" in text
    assert "task_spec" in text
    assert "classify_interaction_intent" not in text


def test_structured_router_does_not_import_ui_or_execute_tools():
    text = Path("core/services/interaction_router.py").read_text(encoding="utf-8")

    forbidden = [
        "streamlit",
        "core.ui_adapter",
        "execute_node",
        "execute_analysis_tool",
        "get_plugin",
        "PLUGIN_REGISTRY",
    ]

    offenders = [term for term in forbidden if term in text]
    assert offenders == []
