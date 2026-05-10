import json

import pytest
from pydantic import ValidationError

from core.action_codec import action_from_state, action_to_state_dict
from core.schema import ActionProposal


def test_action_to_state_dict_serializes_action_proposal():
    action = ActionProposal(
        action_id="act_1",
        action_type="tool_call",
        tool_name="get_summary_stats",
        arguments={"columns": ["GPA"]},
        reasoning_summary="Compute summary statistics.",
    )

    payload = action_to_state_dict(action)

    assert isinstance(payload, dict)
    assert payload["action_id"] == "act_1"
    assert payload["tool_name"] == "get_summary_stats"
    assert payload["arguments"] == {"columns": ["GPA"]}

    json.dumps(payload)


def test_action_from_state_rehydrates_dict_to_action_proposal():
    payload = {
        "action_id": "act_2",
        "action_type": "tool_call",
        "tool_name": "run_multiple_regression",
        "arguments": {
            "target_col": "GPA",
            "feature_cols": ["SATM"],
        },
        "reasoning_summary": "Run regression.",
    }

    action = action_from_state(payload)

    assert isinstance(action, ActionProposal)
    assert action.action_id == "act_2"
    assert action.tool_name == "run_multiple_regression"
    assert action.arguments == {
        "target_col": "GPA",
        "feature_cols": ["SATM"],
    }


def test_action_codec_normalizes_legacy_summary_field():
    payload = {
        "action_id": "act_3",
        "action_type": "tool_call",
        "tool_name": "get_summary_stats",
        "arguments": {},
        "summary": "Legacy summary.",
    }

    action = action_from_state(payload)

    assert action.reasoning_summary == "Legacy summary."


def test_action_codec_handles_none():
    assert action_to_state_dict(None) is None
    assert action_from_state(None) is None


def test_action_to_state_dict_serializes_canonical_task_contract():
    action = ActionProposal(
        action_id="act_4",
        action_type="tool_call",
        tool_name="run_multiple_regression",
        arguments={"target_col": "GPA", "feature_cols": ["SATM"]},
        reasoning_summary="Run regression.",
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

    payload = action_to_state_dict(action)

    assert payload["task_contract"]["contract_id"] == "contract_01"
    assert payload["task_contract"]["required_deliverables"][0] == {
        "deliverable_id": "regression_model",
        "description": "Fit OLS regression.",
        "satisfied_by": ["run_multiple_regression"],
        "required_evidence": ["status_ok", "coef_table"],
        "status": "pending",
    }

    json.dumps(payload)


def test_action_from_state_rehydrates_canonical_task_contract():
    action = action_from_state({
        "action_id": "act_5",
        "action_type": "tool_call",
        "tool_name": "run_multiple_regression",
        "arguments": {"target_col": "GPA", "feature_cols": ["SATM"]},
        "reasoning_summary": "Run regression.",
        "task_contract": {
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
    })

    assert action.task_contract.contract_id == "contract_01"
    assert action.task_contract.required_deliverables[0].deliverable_id == (
        "regression_model"
    )


def test_action_from_state_rejects_legacy_task_contract_inside_action_payload():
    with pytest.raises(ValidationError):
        action_from_state({
            "action_id": "act_6",
            "action_type": "tool_call",
            "tool_name": "get_summary_stats",
            "arguments": {},
            "reasoning_summary": "Compute summary.",
            "task_contract": {
                "required_tools": ["get_summary_stats"],
                "required_deliverables": ["brief summary"],
            },
        })
