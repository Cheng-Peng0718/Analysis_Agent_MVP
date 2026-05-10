import pandas as pd

from core.data.context_refresh import refresh_dataset_context_from_df
from core.domain.task import TaskSpec
from core.services.intelligent_planner import create_plan


def _context(df):
    refreshed = refresh_dataset_context_from_df(
        df,
        dataset_name="student_data",
        data_version_id="raw_v1",
    )
    return refreshed.dataset_profile_v2, refreshed.capability_map


def _tool_names(plan):
    return [step.tool_name for step in plan.steps]


def test_dataset_overview_plan_does_not_include_modeling_or_cleaning_tools():
    profile, capability_map = _context(pd.DataFrame({
        "GPA": [3.0, 3.2, None, 4.0],
        "SATM": [600, 620, 650, 700],
        "Sex": ["F", "M", "F", "M"],
    }))

    plan = create_plan(
        user_request="What does the data look like?",
        task_spec=TaskSpec(
            goal_type="dataset_overview",
            user_goal="Understand the dataset.",
            source_user_request="What does the data look like?",
        ),
        dataset_profile=profile,
        capability_map=capability_map,
    )

    tools = _tool_names(plan)

    assert "inspect_dataset" in tools
    assert "missingness_report" in tools
    assert "get_summary_stats" in tools
    assert "run_multiple_regression" not in tools
    assert "run_anova" not in tools
    assert "run_chi_square" not in tools
    assert "clean_data" not in tools

    inspect_step = next(step for step in plan.steps if step.tool_name == "inspect_dataset")
    assert inspect_step.status == "ready"
    assert inspect_step.execution_ready is True
    assert inspect_step.required_user_choices == []
    assert not any(
        "Plugin has no variable role contract" in warning
        for warning in inspect_step.warnings
    )


def test_regression_plan_uses_regression_related_steps_only():
    profile, capability_map = _context(pd.DataFrame({
        "GPA": [3.0, 3.2, 3.8, 4.0],
        "SATM": [600, 620, 650, 700],
        "Sex": ["F", "M", "F", "M"],
    }))

    plan = create_plan(
        user_request="run linear regression of GPA on SATM",
        task_spec=TaskSpec(
            goal_type="regression_modeling",
            user_goal="Fit a regression model.",
            source_user_request="run linear regression of GPA on SATM",
            target_variables=["GPA"],
            predictor_variables=["SATM"],
            requested_methods=["linear_regression"],
        ),
        dataset_profile=profile,
        capability_map=capability_map,
    )

    tools = _tool_names(plan)

    assert "run_multiple_regression" in tools
    assert "regression_diagnostics" in tools
    assert "generate_residual_histogram" in tools
    assert "run_anova" not in tools
    assert "run_chi_square" not in tools
    assert "clean_data" not in tools

    regression_step = next(step for step in plan.steps if step.tool_name == "run_multiple_regression")
    assert regression_step.arguments["target_col"] == "GPA"
    assert regression_step.arguments["feature_cols"] == ["SATM"]


def test_cleaning_plan_requires_user_choices_and_confirmation():
    profile, capability_map = _context(pd.DataFrame({
        "GPA": [3.0, None, 3.8, 4.0],
        "SATM": [600, 620, 650, 700],
    }))

    plan = create_plan(
        user_request="drop rows with missing GPA",
        task_spec=TaskSpec(
            goal_type="data_cleaning",
            user_goal="Clean missing GPA rows.",
            source_user_request="drop rows with missing GPA",
            target_variables=["GPA"],
            requested_methods=["data_cleaning"],
        ),
        dataset_profile=profile,
        capability_map=capability_map,
    )

    tools = _tool_names(plan)

    assert tools == ["clean_data"]
    step = plan.steps[0]

    assert step.mutates_data is True
    assert step.requires_confirmation is True
    assert step.execution_ready is False
    assert "action_type" in step.required_user_choices
    assert "strategy" in step.required_user_choices
