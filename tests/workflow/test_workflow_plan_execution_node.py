from core.action_access import get_action_arguments, get_action_tool_name
from core.workflow.nodes.plan_execution import execute_pending_plan_node


def test_execute_pending_plan_without_plan_returns_response_only():
    result = execute_pending_plan_node({
        "pending_plan": None,
        "active_data_version_id": "raw_v1",
    })

    assert result["current_action"] is None
    assert result["current_execution"] is None
    assert result["current_verification"] is None
    assert result["plan_execution_status"] == "no_pending_plan"
    assert result["assistant_response"]["response_type"] == "plan_execution_status"


def test_execute_pending_plan_with_no_ready_step_does_not_create_action():
    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": {
            "plan_id": "plan_1",
            "status": "partially_ready",
            "steps": [
                {
                    "step_id": "s1",
                    "tool_name": "run_multiple_regression",
                    "status": "needs_user_choice",
                    "execution_ready": False,
                    "execution_status": "not_started",
                    "arguments": {},
                    "variables": {},
                    "required_user_choices": ["target_col"],
                }
            ],
        },
    }

    result = execute_pending_plan_node(state)

    assert result["current_action"] is None
    assert result["current_execution"] is None
    assert result["current_verification"] is None
    assert result["plan_execution_status"] == "waiting_for_user_choices"


def test_execute_pending_plan_creates_action_for_ready_step():
    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": {
            "plan_id": "plan_1",
            "status": "partially_ready",
            "steps": [
                {
                    "step_id": "s1",
                    "tool_name": "get_summary_stats",
                    "status": "ready",
                    "execution_ready": True,
                    "execution_status": "not_started",
                    "arguments": {
                        "columns": ["GPA"],
                    },
                    "variables": {},
                    "required_user_choices": [],
                }
            ],
        },
    }

    result = execute_pending_plan_node(state)

    assert result["current_action"] is not None
    assert get_action_tool_name(result["current_action"]) == "get_summary_stats"
    assert get_action_arguments(result["current_action"]) == {"columns": ["GPA"]}
    assert result["current_plan_step_id"] == "s1"
    assert result["plan_execution_status"] == "started_step"
    assert result["action_origin"] == "pending_plan"

def test_execute_pending_plan_creates_review_for_ready_mutating_step():
    from core.verification_access import get_verification_status
    from core.workflow.routes import route_after_execute_pending_plan

    state = {
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": {
            "dataset_name": "uploaded_dataset",
            "data_version_id": "raw_v1",
            "n_rows": 5,
            "n_cols": 2,
            "columns": {
                "GPA": {
                    "name": "GPA",
                    "semantic_type": "continuous_numeric",
                    "raw_dtype": "float64",
                    "measurement_scale": "continuous",
                    "n_missing": 1,
                    "missing_rate": 0.2,
                    "n_unique": 4,
                    "unique_rate": 0.8,
                },
                "SATM": {
                    "name": "SATM",
                    "semantic_type": "continuous_numeric",
                    "raw_dtype": "float64",
                    "measurement_scale": "continuous",
                    "n_missing": 1,
                    "missing_rate": 0.2,
                    "n_unique": 4,
                    "unique_rate": 0.8,
                },
            },
        },
        "pending_plan": {
            "plan_id": "plan_1",
            "status": "partially_ready",
            "steps": [
                {
                    "step_id": "clean_step",
                    "title": "Clean data",
                    "tool_name": "clean_data",
                    "status": "ready",
                    "execution_ready": True,
                    "execution_status": "not_started",
                    "arguments": {
                        "action_type": "drop",
                        "strategy": "rows",
                        "columns": ["GPA", "SATM"],
                    },
                    "variables": {},
                    "required_user_choices": [],
                }
            ],
        },
    }

    result = execute_pending_plan_node(state)

    assert result["plan_execution_status"] == "awaiting_review"
    assert result["human_review_required"] is True
    assert result["pending_action"] is not None
    assert get_action_tool_name(result["pending_action"]) == "clean_data"
    assert get_verification_status(result["current_verification"]) == "needs_review"
    assert result["current_plan_step_id"] == "clean_step"
    assert result["pending_plan"]["status"] == "awaiting_review"
    assert result["pending_plan"]["steps"][0]["execution_status"] == "awaiting_review"
    assert route_after_execute_pending_plan(result) == "human_review"

def test_route_after_summarize_ends_for_last_summarized_pending_plan_action():
    from core.workflow.routes import route_after_summarize

    state = {
        "action_origin": None,
        "last_summarized_action_origin": "pending_plan",
        "observations": [
            {
                "status": "ok",
                "success": True,
                "error_code": None,
                "raw_data": {},
            }
        ],
    }

    assert route_after_summarize(state) == "end"

def test_route_after_summarize_ends_for_last_summarized_direct_tool_action():
    from core.workflow.routes import route_after_summarize

    state = {
        "action_origin": None,
        "last_summarized_action_origin": "direct_tool",
        "observations": [
            {
                "status": "ok",
                "success": True,
                "error_code": None,
                "raw_data": {},
            }
        ],
    }

    assert route_after_summarize(state) == "end"
