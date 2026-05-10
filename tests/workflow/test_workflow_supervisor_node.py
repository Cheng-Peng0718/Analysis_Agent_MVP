from core.schema import ActionProposal
from core.workflow.nodes import supervisor as supervisor_module


class DummyContext:
    context_text = "dummy context"


def test_supervisor_node_sets_current_action(monkeypatch):
    def fake_build_context(**kwargs):
        return DummyContext()

    def fake_call_supervisor(context_pkg):
        return ActionProposal(
            action_id="act_1",
            action_type="tool_call",
            tool_name="get_summary_stats",
            arguments={"columns": ["GPA"]},
            reasoning_summary="Compute summary statistics.",
        )

    monkeypatch.setattr(supervisor_module, "build_context", fake_build_context)
    monkeypatch.setattr(supervisor_module, "call_supervisor", fake_call_supervisor)

    updates = supervisor_module.supervisor_node({
        "workspace_dir": "./tmp",
        "dataset_profile": {"columns": []},
        "user_request": "do summary stats",
        "observations": [],
        "current_step": 1,
        "max_steps": 12,
    })

    assert updates["current_action"].action_id == "act_1"
    assert updates["current_action"].tool_name == "get_summary_stats"
    assert "task_contract" not in updates


def test_supervisor_node_extracts_task_contract_from_dict_action(monkeypatch):
    def fake_build_context(**kwargs):
        return DummyContext()

    def fake_call_supervisor(context_pkg):
        return {
            "action_id": "act_final",
            "action_type": "final_answer",
            "tool_name": None,
            "arguments": {},
            "reasoning_summary": "Prepare final answer.",
            "task_contract": {
                "required_tools": ["get_summary_stats"],
                "required_deliverables": ["brief summary"],
            },
        }

    monkeypatch.setattr(supervisor_module, "build_context", fake_build_context)
    monkeypatch.setattr(supervisor_module, "call_supervisor", fake_call_supervisor)

    updates = supervisor_module.supervisor_node({
        "workspace_dir": "./tmp",
        "dataset_profile": {"columns": []},
        "user_request": "give me final answer",
        "observations": [],
        "current_step": 1,
        "max_steps": 12,
    })

    assert updates["current_action"]["action_id"] == "act_final"
    assert updates["task_contract"] == {
        "required_tools": ["get_summary_stats"],
        "required_deliverables": ["brief summary"],
    }


def test_supervisor_node_passes_existing_task_contract_to_context(monkeypatch):
    captured = {}

    def fake_build_context(**kwargs):
        captured.update(kwargs)
        return DummyContext()

    def fake_call_supervisor(context_pkg):
        return ActionProposal(
            action_id="act_1",
            action_type="tool_call",
            tool_name="run_multiple_regression",
            arguments={"target_col": "y", "feature_cols": ["x"]},
            reasoning_summary="Continue the existing contract.",
        )

    existing_contract = {
        "contract_id": "contract_01",
        "user_goal": "Fit a regression model.",
        "required_deliverables": [
            {
                "deliverable_id": "regression_model",
                "satisfied_by": ["run_multiple_regression"],
                "required_evidence": ["status_ok", "coef_table"],
                "status": "pending",
            }
        ],
    }

    monkeypatch.setattr(supervisor_module, "build_context", fake_build_context)
    monkeypatch.setattr(supervisor_module, "call_supervisor", fake_call_supervisor)

    supervisor_module.supervisor_node({
        "workspace_dir": "./tmp",
        "dataset_profile": {"columns": []},
        "user_request": "continue",
        "observations": [],
        "current_step": 2,
        "max_steps": 12,
        "task_contract": existing_contract,
    })

    assert captured["task_contract"] == existing_contract


def test_supervisor_node_stores_canonical_task_contract_as_state_dict(monkeypatch):
    def fake_build_context(**kwargs):
        return DummyContext()

    def fake_call_supervisor(context_pkg):
        return ActionProposal(
            action_id="act_1",
            action_type="tool_call",
            tool_name="run_multiple_regression",
            arguments={"target_col": "y", "feature_cols": ["x"]},
            reasoning_summary="Start the regression contract.",
            task_contract={
                "contract_id": "contract_01",
                "user_goal": "Fit a regression model.",
                "required_deliverables": [
                    {
                        "deliverable_id": "regression_model",
                        "description": "Fit OLS regression.",
                        "satisfied_by": ["run_multiple_regression"],
                        "required_evidence": ["status_ok", "coef_table"],
                        "status": "pending",
                    }
                ],
                "constraints": [],
                "created_by": "supervisor",
                "status": "active",
            },
        )

    monkeypatch.setattr(supervisor_module, "build_context", fake_build_context)
    monkeypatch.setattr(supervisor_module, "call_supervisor", fake_call_supervisor)

    updates = supervisor_module.supervisor_node({
        "workspace_dir": "./tmp",
        "dataset_profile": {"columns": []},
        "user_request": "fit regression",
        "observations": [],
        "current_step": 1,
        "max_steps": 12,
    })

    assert updates["task_contract"]["contract_id"] == "contract_01"
    assert updates["task_contract"]["required_deliverables"][0] == {
        "deliverable_id": "regression_model",
        "description": "Fit OLS regression.",
        "satisfied_by": ["run_multiple_regression"],
        "required_evidence": ["status_ok", "coef_table"],
        "status": "pending",
    }
