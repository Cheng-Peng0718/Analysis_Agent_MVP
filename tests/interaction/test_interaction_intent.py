from core.interaction_intent import (
    InteractionIntent,
    classify_interaction_intent,
)
from core.services.interaction_router import decide_interaction_intent


def test_what_can_i_do_is_advisory():
    intent = classify_interaction_intent(
        "I want to do analysis to this dataset, what can I do?"
    )

    assert intent == InteractionIntent.ADVISORY


def test_make_plan_and_tell_me_is_plan_only():
    intent = classify_interaction_intent(
        "could you make up a plan and tell me?"
    )

    assert intent == InteractionIntent.PLAN_ONLY


def test_run_the_plan_is_execute_plan():
    intent = classify_interaction_intent("run the plan")

    assert intent == InteractionIntent.EXECUTE_PLAN


def test_direct_regression_request_is_direct_tool():
    intent = classify_interaction_intent("run linear regression of GPA on SATM")

    assert intent == InteractionIntent.DIRECT_TOOL


def test_explicit_summary_statistics_requests_are_direct_tool():
    prompts = [
        "do summary statistics",
        "run summary statistics",
        "compute summary statistics",
        "summary stats",
        "descriptive statistics",
        "descriptive stats",
        "summarize numeric variables",
    ]

    for prompt in prompts:
        decision = decide_interaction_intent(prompt)

        assert decision.intent == "direct_analysis"
        assert decision.task_spec is not None
        assert decision.task_spec.goal_type == "dataset_overview"
        assert "summary_statistics" in decision.task_spec.requested_methods
        assert decision.should_execute is True
        assert classify_interaction_intent(prompt) == InteractionIntent.DIRECT_TOOL


def test_dataset_overview_summary_phrasing_remains_advisory():
    prompts = [
        "What does the data look like?",
        "summarize this dataset",
        "describe the dataset",
    ]

    for prompt in prompts:
        decision = decide_interaction_intent(prompt)

        assert decision.intent == "advisory"
        assert decision.task_spec is not None
        assert decision.task_spec.goal_type == "dataset_overview"
        assert decision.task_spec.requested_methods == ["dataset_overview"]
        assert decision.should_execute is False
        assert classify_interaction_intent(prompt) == InteractionIntent.ADVISORY


def test_structured_router_builds_dataset_overview_task_spec():
    decision = decide_interaction_intent("What does the data look like?")

    assert decision.intent == "advisory"
    assert decision.task_spec is not None
    assert decision.task_spec.goal_type == "dataset_overview"
    assert decision.should_execute is False


def test_structured_router_builds_regression_task_spec_with_roles():
    decision = decide_interaction_intent(
        "run linear regression of GPA on SATM",
        state={
            "dataset_profile_v2": {
                "columns": {
                    "GPA": {},
                    "SATM": {},
                }
            }
        },
    )

    assert decision.intent == "direct_analysis"
    assert decision.task_spec is not None
    assert decision.task_spec.goal_type == "regression_modeling"
    assert decision.task_spec.target_variables == ["GPA"]
    assert decision.task_spec.predictor_variables == ["SATM"]
    assert decision.task_spec.requested_methods == ["linear_regression"]


def test_structured_router_builds_cleaning_task_spec():
    decision = decide_interaction_intent(
        "drop rows with missing GPA",
        state={
            "dataset_profile_v2": {
                "columns": {
                    "GPA": {},
                }
            }
        },
    )

    assert decision.intent == "modify_data"
    assert decision.task_spec is not None
    assert decision.task_spec.goal_type == "data_cleaning"
    assert decision.task_spec.target_variables == ["GPA"]


def test_plan_regression_and_cleaning_routing_remain_unchanged():
    plan_decision = decide_interaction_intent("make a plan for this dataset")
    assert plan_decision.intent == "plan_analysis"
    assert classify_interaction_intent("make a plan for this dataset") == InteractionIntent.PLAN_ONLY

    regression_decision = decide_interaction_intent(
        "run linear regression of GPA on SATM",
        state={
            "dataset_profile_v2": {
                "columns": {
                    "GPA": {},
                    "SATM": {},
                }
            }
        },
    )
    assert regression_decision.intent == "direct_analysis"
    assert regression_decision.task_spec.goal_type == "regression_modeling"
    assert regression_decision.task_spec.requested_methods == ["linear_regression"]
    assert classify_interaction_intent("run linear regression of GPA on SATM") == InteractionIntent.DIRECT_TOOL

    cleaning_decision = decide_interaction_intent(
        "drop rows with missing GPA",
        state={
            "dataset_profile_v2": {
                "columns": {
                    "GPA": {},
                }
            }
        },
    )
    assert cleaning_decision.intent == "modify_data"
    assert cleaning_decision.task_spec.goal_type == "data_cleaning"
    assert cleaning_decision.task_spec.requested_methods == ["data_cleaning"]
    assert classify_interaction_intent("drop rows with missing GPA") == InteractionIntent.DIRECT_TOOL
