from core.deliverables.contracts import DeliverableGateContract, normalize_task_contract
from core.domain.deliverable import DeliverableCheckResult


def test_normalize_empty_contract():
    contract = normalize_task_contract(None)

    assert isinstance(contract, DeliverableGateContract)
    assert contract.required_tools == []
    assert contract.required_artifacts == []
    assert contract.required_deliverables == []
    assert contract.success_criteria == []
    assert contract.allow_partial is False


def test_normalize_legacy_task_contract_dict():
    contract = normalize_task_contract({
        "required_tools": "get_summary_stats",
        "required_artifacts": ["plot"],
        "required_deliverables": ("summary", "limitations"),
        "success_criteria": "mention missingness",
        "allow_partial": True,
        "custom_field": "kept",
    })

    assert contract.required_tools == ["get_summary_stats"]
    assert contract.required_artifacts == ["plot"]
    assert contract.required_deliverables == ["summary", "limitations"]
    assert contract.success_criteria == ["mention missingness"]
    assert contract.allow_partial is True
    assert contract.metadata["custom_field"] == "kept"


def test_normalize_canonical_domain_task_contract_dict():
    contract = normalize_task_contract({
        "contract_id": "contract_01",
        "user_goal": "Fit a regression model.",
        "required_deliverables": [
            {
                "deliverable_id": "regression_model",
                "description": "Fit OLS regression.",
                "satisfied_by": ["run_multiple_regression"],
                "required_evidence": ["status_ok", "coef_table", "r_squared"],
                "status": "pending",
            }
        ],
    })

    assert contract.required_tools == ["run_multiple_regression"]
    assert contract.required_deliverables == ["regression_model"]
    assert contract.success_criteria == [
        "evidence:status_ok",
        "evidence:coef_table",
        "evidence:r_squared",
    ]


def test_deliverable_check_result_accepts_gate_and_legacy_statuses():
    for status in ["needs_more_work", "missing", "blocked"]:
        result = DeliverableCheckResult(status=status)

        assert result.status == status
        assert result.model_dump()["status"] == status
