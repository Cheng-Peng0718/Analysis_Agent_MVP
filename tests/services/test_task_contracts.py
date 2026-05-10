import pytest
from pydantic import ValidationError

from core.domain.deliverable import TaskContract
from core.services.task_contracts import task_contract_to_state_dict


def _canonical_contract_dict():
    return {
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
        "constraints": [
            {
                "constraint_id": "no_data_mutation",
                "description": "Do not mutate data.",
                "type": "data_mutation",
            }
        ],
        "created_by": "supervisor",
        "status": "active",
    }


def test_task_contract_to_state_dict_validates_canonical_model():
    contract = TaskContract.model_validate(_canonical_contract_dict())

    result = task_contract_to_state_dict(contract)

    assert result["contract_id"] == "contract_01"
    assert result["required_deliverables"][0]["deliverable_id"] == "regression_model"
    assert result["required_deliverables"][0]["required_evidence"] == [
        "status_ok",
        "coef_table",
    ]


def test_task_contract_to_state_dict_validates_canonical_dict():
    result = task_contract_to_state_dict(_canonical_contract_dict())

    assert result["contract_id"] == "contract_01"
    assert result["required_deliverables"][0]["status"] == "pending"


def test_task_contract_to_state_dict_preserves_legacy_gate_contract():
    legacy_contract = {
        "required_tools": ["get_summary_stats"],
        "required_deliverables": ["brief summary"],
    }

    assert task_contract_to_state_dict(legacy_contract) == legacy_contract


def test_task_contract_to_state_dict_rejects_invalid_canonical_contract():
    with pytest.raises(ValidationError):
        task_contract_to_state_dict({
            "contract_id": "contract_01",
            "user_goal": "Fit a regression model.",
            "required_deliverables": [
                {
                    "deliverable_id": "regression_model",
                    "satisfied_by": ["run_multiple_regression"],
                    "required_evidence": ["status_ok", "coef_table"],
                    "status": "completed",
                }
            ],
        })
