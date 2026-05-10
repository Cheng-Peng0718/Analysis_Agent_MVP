from core.context_builder import (
    build_context,
    format_deliverable_gate_feedback,
    format_task_contract_summary,
)


def test_format_deliverable_gate_feedback_supports_string_labels():
    feedback = format_deliverable_gate_feedback({
        "status": "needs_more_work",
        "message": "Required deliverables are missing.",
        "satisfied": ["tool:run_multiple_regression"],
        "missing": [
            "deliverable:regression_model",
            "criterion:evidence:coef_table",
        ],
        "blocked": ["tool_failed:run_multiple_regression"],
    })

    assert "status: needs_more_work" in feedback
    assert "Satisfied deliverables/evidence" in feedback
    assert "- tool:run_multiple_regression" in feedback
    assert "Missing deliverables/evidence" in feedback
    assert "- criterion:evidence:coef_table" in feedback
    assert "Blocked deliverables/evidence" in feedback
    assert "- tool_failed:run_multiple_regression" in feedback
    assert "Do not produce final_answer yet" in feedback


def test_build_context_includes_needs_more_work_gate_feedback_without_crashing():
    context = build_context(
        step=1,
        max_steps=12,
        user_request="Fit a regression model.",
        profile={
            "n_rows": 10,
            "columns": {
                "y": {},
                "x": {},
            },
        },
        observations=[],
        workspace_dir="./tmp",
        deliverable_check={
            "status": "needs_more_work",
            "message": "Required deliverables are missing.",
            "satisfied": ["tool:run_multiple_regression"],
            "missing": ["criterion:evidence:coef_table"],
            "blocked": [],
        },
    )

    assert "Deliverable Gate Feedback" in context.context_text
    assert "- criterion:evidence:coef_table" in context.context_text
    assert "Do not produce final_answer yet" in context.context_text


def test_format_task_contract_summary_includes_canonical_deliverables():
    summary = format_task_contract_summary({
        "contract_id": "contract_01",
        "user_goal": "Fit a regression model.",
        "status": "active",
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
    })

    assert "Task Contract" in summary
    assert "contract_id: contract_01" in summary
    assert "deliverable_id: regression_model" in summary
    assert "satisfied_by: ['run_multiple_regression']" in summary
    assert "required_evidence: ['status_ok', 'coef_table']" in summary
    assert "Preserve this task_contract" in summary


def test_build_context_includes_existing_task_contract():
    context = build_context(
        step=1,
        max_steps=12,
        user_request="Fit a regression model.",
        profile={
            "n_rows": 10,
            "columns": {
                "y": {},
                "x": {},
            },
        },
        observations=[],
        workspace_dir="./tmp",
        task_contract={
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
        },
    )

    assert "Task Contract" in context.context_text
    assert "contract_id: contract_01" in context.context_text
    assert "deliverable_id: regression_model" in context.context_text
    assert "Preserve this task_contract" in context.context_text
