import pandas as pd

from core.data.context_refresh import refresh_dataset_context_from_df
from core.services.llm_planner import build_llm_planner_input, create_llm_plan_from_state
from core.services.llm_planner import (
    build_llm_planner_input,
    create_llm_plan_from_state,
    normalize_llm_plan_draft,
)
from core.services.llm_planner_contracts import LLMPlanDraft, LLMPlanStepDraft

def _state():
    refreshed = refresh_dataset_context_from_df(
        pd.DataFrame({
            "GPA": [3.0, 3.2, 3.8, 4.0],
            "SATM": [600, 620, 650, 700],
            "Sex": ["F", "M", "F", "M"],
        }),
        dataset_name="student_data",
        data_version_id="raw_v1",
    )

    updates = refreshed.to_state_updates()

    updates.update({
        "user_request": "What analysis can I do with this data?",
        "interaction_intent": "plan_only",
        "active_data_version_id": "raw_v1",
    })

    return updates


def test_build_llm_planner_input_includes_dataset_profile_and_tools():
    planner_input = build_llm_planner_input(_state())

    assert planner_input.user_request == "What analysis can I do with this data?"
    assert planner_input.dataset.dataset_name == "student_data"
    assert planner_input.dataset.data_version_id == "raw_v1"
    assert "GPA" in planner_input.dataset.columns
    assert planner_input.dataset.columns["GPA"]["semantic_type"] == "continuous_numeric"

    tool_names = {
        tool.tool_name
        for tool in planner_input.tools
    }

    assert "inspect_dataset" in tool_names
    assert "run_multiple_regression" in tool_names
    assert "clean_data" in tool_names


def test_build_llm_planner_input_exposes_tool_contracts():
    planner_input = build_llm_planner_input(_state())

    regression_tool = next(
        tool
        for tool in planner_input.tools
        if tool.tool_name == "run_multiple_regression"
    )

    assert "regression_modeling" in regression_tool.supported_goal_types
    assert regression_tool.argument_schema["required"]["target_col"] == "str"
    assert regression_tool.task_argument_bindings
    assert regression_tool.requires_confirmation is False
    assert regression_tool.mutates_data is False

    clean_data_tool = next(
        tool
        for tool in planner_input.tools
        if tool.tool_name == "clean_data"
    )

    assert clean_data_tool.requires_confirmation is True
    assert clean_data_tool.mutates_data is True
    assert clean_data_tool.required_planning_choices == [
        "action_type",
        "strategy",
    ]


def test_create_llm_plan_from_state_returns_plan_proposal():
    plan = create_llm_plan_from_state(_state())

    assert plan.plan_id.startswith("plan_")
    assert plan.steps
    assert plan.status in {
        "draft",
        "ready",
        "verified",
        "partially_ready",
        "needs_clarification",
        "blocked",
    }

def test_normalize_llm_plan_draft_builds_verified_plan_from_valid_tool_step():
    state = _state()

    draft = LLMPlanDraft(
        user_goal="Fit a regression model.",
        summary="Plan a regression and diagnostics workflow.",
        assumptions=[
            "The user selected GPA as outcome and SATM as predictor.",
        ],
        steps=[
            LLMPlanStepDraft(
                title="Fit linear regression",
                tool_name="run_multiple_regression",
                purpose="Estimate the relationship between SATM and GPA.",
                rationale="Both variables are numeric and suitable for a simple regression.",
                status="ready",
                arguments={
                    "target_col": "GPA",
                    "feature_cols": ["SATM"],
                },
                variables={
                    "target_col": "GPA",
                    "feature_cols": ["SATM"],
                },
            ),
        ],
    )

    plan = normalize_llm_plan_draft(
        draft=draft,
        state=state,
    )

    assert plan.plan_id.startswith("plan_")
    assert plan.steps
    assert plan.steps[0].tool_name == "run_multiple_regression"
    assert plan.steps[0].arguments == {
        "target_col": "GPA",
        "feature_cols": ["SATM"],
    }
    assert plan.steps[0].requires_confirmation is False
    assert plan.steps[0].mutates_data is False
    assert plan.steps[0].expected_deliverables == ["regression_model"]


def test_normalize_llm_plan_draft_moves_unknown_tool_to_blocked():
    state = _state()

    draft = LLMPlanDraft(
        user_goal="Run an invented tool.",
        summary="This draft includes an invalid tool.",
        steps=[
            LLMPlanStepDraft(
                title="Invented analysis",
                tool_name="invented_tool",
                purpose="This should not be executable.",
                rationale="The tool does not exist.",
                status="ready",
                arguments={},
            ),
        ],
    )

    plan = normalize_llm_plan_draft(
        draft=draft,
        state=state,
    )

    assert plan.steps == []
    assert plan.blocked_or_not_recommended
    assert plan.blocked_or_not_recommended[0].tool_name == "invented_tool"
    assert plan.blocked_or_not_recommended[0].status in {
        "blocked",
        "not_applicable",
    }


def test_normalize_llm_plan_draft_preserves_required_choices_for_missing_arguments():
    state = _state()

    draft = LLMPlanDraft(
        user_goal="Fit a regression model.",
        summary="Regression needs variable choices.",
        steps=[
            LLMPlanStepDraft(
                title="Fit linear regression",
                tool_name="run_multiple_regression",
                purpose="Fit a regression model.",
                rationale="This requires an outcome and predictors.",
                status="needs_user_choice",
                arguments={},
                required_user_choices=[
                    "target_col",
                    "feature_cols",
                ],
            ),
        ],
    )

    plan = normalize_llm_plan_draft(
        draft=draft,
        state=state,
    )

    assert plan.steps
    step = plan.steps[0]
    assert step.tool_name == "run_multiple_regression"
    assert "target_col" in step.required_user_choices
    assert "feature_cols" in step.required_user_choices
    assert step.execution_ready is False