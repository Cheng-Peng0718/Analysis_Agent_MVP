import pandas as pd

from core.dataset_intelligence.profiler import profile_dataframe
from core.domain.intent import IntentDecision
from core.domain.task import TaskSpec
from core.workflow.nodes import interaction as interaction_node
from core.workflow.nodes.interaction import apply_pending_plan_clarification, intent_router_node


def _profile_dict():
    df = pd.DataFrame({
        "GPA": [3.1, 3.4, 3.8, 3.6, 3.9],
        "SATM": [620.0, 650.0, 700.0, 680.0, 720.0],
        "Major": ["A", "B", "A", "B", "A"],
    })
    return profile_dataframe(df, data_version_id="raw_v1").model_dump()


def _regression_pending_plan():
    return {
        "plan_id": "plan_1",
        "status": "partially_ready",
        "steps": [
            {
                "step_id": "s_reg",
                "title": "Fit regression",
                "tool_name": "run_multiple_regression",
                "status": "needs_user_choice",
                "execution_ready": False,
                "execution_status": "not_started",
                "arguments": {},
                "variables": {},
                "required_user_choices": ["target_col", "feature_cols"],
            }
        ],
    }


def test_apply_pending_plan_clarification_uses_plugin_task_bindings():
    decision = IntentDecision(
        intent="clarification",
        confidence=1.0,
        reason="User supplied missing plan variables.",
        task_spec=TaskSpec(
            goal_type="regression_modeling",
            user_goal="Use GPA as outcome and SATM as predictor.",
            source_user_request="Use GPA as outcome and SATM as predictor.",
            target_variables=["GPA"],
            predictor_variables=["SATM"],
        ),
    )

    result = apply_pending_plan_clarification(
        {
            "dataset_profile_v2": _profile_dict(),
            "pending_plan": _regression_pending_plan(),
        },
        decision,
    )

    assert result["applied"] is True
    step = result["pending_plan"]["steps"][0]
    assert step["status"] == "ready"
    assert step["execution_ready"] is True
    assert step["required_user_choices"] == []
    assert step["arguments"] == {
        "target_col": "GPA",
        "feature_cols": ["SATM"],
    }


def test_intent_router_applies_plan_clarification_and_routes_to_execution(monkeypatch):
    decision = IntentDecision(
        intent="clarification",
        confidence=1.0,
        reason="User supplied missing plan variables.",
        task_spec=TaskSpec(
            goal_type="regression_modeling",
            user_goal="Use GPA as outcome and SATM as predictor.",
            source_user_request="Use GPA as outcome and SATM as predictor.",
            target_variables=["GPA"],
            predictor_variables=["SATM"],
        ),
    )

    monkeypatch.setattr(
        interaction_node,
        "decide_llm_interaction_intent",
        lambda user_request, state=None: decision,
    )

    updates = intent_router_node({
        "user_request": "Use GPA as outcome and SATM as predictor.",
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": _profile_dict(),
        "pending_plan": _regression_pending_plan(),
    })

    assert updates["interaction_intent"] == "execute_plan"
    assert updates["plan_execution_status"] == "clarification_applied"
    assert updates["pending_plan"]["steps"][0]["status"] == "ready"


def test_intent_router_returns_chat_clarification_when_column_does_not_match(monkeypatch):
    decision = IntentDecision(
        intent="clarification",
        confidence=1.0,
        reason="User supplied missing plan variables.",
        task_spec=TaskSpec(
            goal_type="regression_modeling",
            user_goal="Use Grade as outcome and SATM as predictor.",
            source_user_request="Use Grade as outcome and SATM as predictor.",
            target_variables=["Grade"],
            predictor_variables=["SATM"],
        ),
    )

    monkeypatch.setattr(
        interaction_node,
        "decide_llm_interaction_intent",
        lambda user_request, state=None: decision,
    )

    updates = intent_router_node({
        "user_request": "Use Grade as outcome and SATM as predictor.",
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": _profile_dict(),
        "pending_plan": _regression_pending_plan(),
        "plan_status": "partially_ready",
    })

    assert updates["interaction_intent"] == "end"
    assert updates["assistant_response"]["response_type"] == "clarification"
    assert "Grade" in updates["assistant_response"]["content"]
    assert "Available columns" in updates["assistant_response"]["content"]


def _cleaning_pending_plan():
    return {
        "plan_id": "plan_clean",
        "status": "partially_executed",
        "steps": [
            {
                "step_id": "s_done",
                "title": "Inspect dataset",
                "tool_name": "inspect_dataset",
                "status": "ready",
                "execution_ready": True,
                "execution_status": "completed",
                "arguments": {},
                "variables": {},
                "required_user_choices": [],
            },
            {
                "step_id": "s_clean",
                "title": "Data Cleaning",
                "tool_name": "clean_data",
                "status": "needs_user_choice",
                "execution_ready": False,
                "execution_status": "not_started",
                "arguments": {},
                "variables": {},
                "required_user_choices": ["action_type", "strategy"],
            },
        ],
    }


def test_intent_router_treats_modify_data_assignment_as_pending_plan_clarification(monkeypatch):
    user_message = "For data cleaning, use action_type = drop, strategy = rows, columns = GPA, SATM."
    decision = IntentDecision(
        intent="modify_data",
        confidence=1.0,
        reason="User supplied data modification details.",
        task_spec=TaskSpec(
            goal_type="data_cleaning",
            user_goal=user_message,
            source_user_request=user_message,
            constraints={},
        ),
        should_execute=True,
    )

    monkeypatch.setattr(
        interaction_node,
        "decide_llm_interaction_intent",
        lambda user_request, state=None: decision,
    )

    updates = intent_router_node({
        "user_request": user_message,
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": _profile_dict(),
        "pending_plan": _cleaning_pending_plan(),
        "plan_status": "partially_executed",
    })

    assert updates["interaction_intent"] == "execute_plan"
    step = updates["pending_plan"]["steps"][1]
    assert step["status"] == "ready"
    assert step["execution_ready"] is True
    assert step["arguments"] == {
        "action_type": "drop",
        "strategy": "rows",
        "columns": ["GPA", "SATM"],
    }
