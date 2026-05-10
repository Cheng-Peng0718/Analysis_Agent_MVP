import pandas as pd

from core.dataset_intelligence.capability_map import build_capability_map
from core.dataset_intelligence.profiler import profile_dataframe
from core.workflow.nodes.planning import plan_only_node


def make_state():
    df = pd.DataFrame({
        "GPA": [3.0, 3.2, 3.5, 3.8],
        "SATM": [600, 620, 650, 680],
        "Sex": ["F", "M", "F", "M"],
    })

    profile = profile_dataframe(
        df,
        dataset_name="student_data",
        data_version_id="raw_v1",
    )

    capability_map = build_capability_map(profile)

    return {
        "user_request": "make a plan",
        "interaction_intent": "plan_only",
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": profile.model_dump(),
        "capability_map": capability_map.model_dump(),
    }


def test_plan_only_node_creates_pending_plan_without_action(monkeypatch):
    from core.domain.plan import PlanProposal, PlanStep

    def fake_create_llm_plan_from_state(state):
        return PlanProposal(
            plan_id="plan_test",
            user_request=state.get("user_request", ""),
            data_version_id=state.get("active_data_version_id", "raw_v1"),
            mode="plan_only",
            status="partially_ready",
            summary="Fake LLM plan for test.",
            assumptions=["LLM planner is mocked in this unit test."],
            steps=[
                PlanStep(
                    step_id="step_inspect_dataset",
                    title="Inspect dataset",
                    tool_name="inspect_dataset",
                    method_family="overview",
                    status="ready",
                    execution_ready=True,
                    purpose="Inspect the dataset.",
                    rationale="Start with a dataset overview.",
                    arguments={},
                    variables={},
                )
            ],
            requires_user_confirmation_before_execution=True,
        )

    monkeypatch.setattr(
        "core.workflow.nodes.planning.create_llm_plan_from_state",
        fake_create_llm_plan_from_state,
    )

    result = plan_only_node(make_state())


def test_plan_only_node_blocks_when_profile_missing():
    result = plan_only_node({
        "user_request": "make a plan",
        "active_data_version_id": "raw_v1",
    })

    assert result["pending_plan"] is None
    assert result["plan_status"] == "blocked"
    assert result["assistant_response"]["response_type"] == "error"
    assert result["assistant_response"]["metadata"]["reason"] == (
        "missing_dataset_profile_or_capability_map"
    )