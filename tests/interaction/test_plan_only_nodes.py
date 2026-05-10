import pandas as pd

from core.dataset_intelligence.profiler import profile_dataframe
from core.dataset_intelligence.capability_map import build_capability_map
from core.workflow.nodes.planning import plan_only_node
from core.workflow.nodes.interaction import advisory_answer_node


def make_state():
    df = pd.DataFrame({
        "y": [1.2, 2.4, 3.1, 4.7],
        "x": [10.5, 20.2, 30.8, 40.1],
        "group": ["A", "B", "A", "B"],
    })

    profile = profile_dataframe(df, data_version_id="raw_v1")
    capability_map = build_capability_map(profile)

    return {
        "user_request": "could you make up a plan and tell me?",
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": profile.model_dump(),
        "capability_map": capability_map.model_dump(),
        "dataset_summary": {
            "n_rows": 4,
            "n_cols": 3,
            "numeric_columns": ["y", "x"],
            "categorical_columns": ["group"],
            "binary_columns": ["group"],
            "id_like_columns": [],
            "missingness_summary": {"n_columns_with_missing": 0},
        },
    }


def test_plan_only_node_does_not_create_action(monkeypatch):
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

    state = make_state()
    result = plan_only_node(state)

    assert result["pending_plan"] is not None
    assert result["plan_status"] in {"draft", "verified", "partially_ready"}
    assert result["current_action"] is None
    assert result["current_execution"] is None
    assert result["current_verification"] is None

    assert "assistant_response" in result
    assert result["assistant_response"]["response_type"] == "plan"
    assert "No tools have been executed" in result["assistant_response"]["content"]

def test_advisory_answer_node_does_not_create_action():
    state = make_state()
    state["user_request"] = "what can I do?"

    result = advisory_answer_node(state)

    assert result["current_action"] is None
    assert result["current_execution"] is None
    assert result["current_verification"] is None

    assert "assistant_response" in result
    assert result["assistant_response"]["response_type"] == "advisory"
    assert "I have not run any analysis tools yet" in result["assistant_response"]["content"]