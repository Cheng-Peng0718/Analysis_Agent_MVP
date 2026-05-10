from pydantic import ValidationError

from core.domain.plan import PlanProposal, PlanStep


def _active_plan_step(**overrides):
    data = {
        "step_id": "step_regression",
        "title": "Run regression",
        "purpose": "Fit the requested regression model.",
        "goal": "Fit a regression model.",
        "rationale": "Regression is the requested method.",
        "tool_name": "run_multiple_regression",
        "method_family": "regression",
        "status": "needs_user_choice",
        "execution_ready": False,
        "variables": {
            "target_col": "GPA",
            "feature_cols": ["SATM"],
        },
        "arguments": {
            "target_col": "GPA",
            "feature_cols": ["SATM"],
        },
        "candidate_variables": {
            "target_col": ["GPA"],
            "feature_cols": ["SATM", "SATV"],
        },
        "required_user_choices": ["feature_cols"],
        "applicability_check": {
            "status": "needs_user_choice",
            "reason": "User must choose predictors.",
        },
        "warnings": ["Confirm predictor variables before execution."],
        "suggested_alternatives": ["get_summary_stats"],
        "expected_deliverables": ["regression_model"],
        "requires_confirmation": False,
        "mutates_data": False,
    }
    data.update(overrides)
    return data


def test_plan_step_accepts_active_schema_fields():
    step = PlanStep.model_validate(_active_plan_step())

    dumped = step.model_dump()

    assert dumped["status"] == "needs_user_choice"
    assert dumped["execution_ready"] is False
    assert dumped["variables"]["target_col"] == "GPA"
    assert dumped["arguments"]["feature_cols"] == ["SATM"]
    assert dumped["candidate_variables"]["feature_cols"] == ["SATM", "SATV"]
    assert dumped["required_user_choices"] == ["feature_cols"]
    assert dumped["applicability_check"]["status"] == "needs_user_choice"


def test_plan_proposal_accepts_active_schema_fields_and_legacy_user_request():
    proposal = PlanProposal.model_validate({
        "plan_id": "plan_regression",
        "user_goal": "Fit GPA on SATM.",
        "user_request": "run linear regression of GPA on SATM",
        "data_version_id": "raw_v1",
        "mode": "plan_only",
        "status": "partially_ready",
        "summary": "Generated a regression plan.",
        "assumptions": ["No tools have been executed."],
        "warnings": ["Some steps need user choices."],
        "steps": [_active_plan_step()],
        "blocked_or_not_recommended": [
            _active_plan_step(
                step_id="step_blocked",
                title="Blocked step",
                status="not_applicable",
                execution_ready=False,
            )
        ],
        "requires_user_confirmation_before_execution": True,
    })

    dumped = proposal.model_dump()

    assert dumped["user_goal"] == "Fit GPA on SATM."
    assert dumped["user_request"] == "run linear regression of GPA on SATM"
    assert dumped["data_version_id"] == "raw_v1"
    assert dumped["mode"] == "plan_only"
    assert dumped["blocked_or_not_recommended"][0]["status"] == "not_applicable"
    assert dumped["requires_user_confirmation_before_execution"] is True
    assert dumped["steps"][0]["status"] == "needs_user_choice"
    assert dumped["steps"][0]["execution_ready"] is False
    assert dumped["steps"][0]["variables"]["target_col"] == "GPA"
    assert dumped["steps"][0]["arguments"]["target_col"] == "GPA"
    assert dumped["steps"][0]["candidate_variables"]["target_col"] == ["GPA"]
    assert dumped["steps"][0]["required_user_choices"] == ["feature_cols"]
    assert dumped["steps"][0]["applicability_check"]["reason"] == (
        "User must choose predictors."
    )


def test_plan_contract_rejects_ui_only_fields():
    step = PlanStep.model_validate(_active_plan_step())
    proposal = PlanProposal.model_validate({
        "plan_id": "plan_1",
        "steps": [step],
    })

    step_dump = step.model_dump()
    proposal_dump = proposal.model_dump()

    for key in [
        "selected_plan_step_id",
        "latest_ui_event",
        "ui_snapshot",
        "plan_execution_status",
    ]:
        assert key not in step_dump
        assert key not in proposal_dump


def test_plan_contract_rejects_unknown_status_values():
    try:
        PlanStep.model_validate(_active_plan_step(status="done"))
    except ValidationError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("PlanStep accepted an unknown status.")

    try:
        PlanProposal.model_validate({
            "plan_id": "plan_1",
            "status": "done",
        })
    except ValidationError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("PlanProposal accepted an unknown status.")
