from core.workflow.nodes.plan_execution import execute_pending_plan_node
from core.workflow.routes import route_after_verify

def test_execute_pending_plan_without_plan_returns_response_only():
    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": None,
    }

    result = execute_pending_plan_node(state)

    assert result["current_action"] is None
    assert result["current_execution"] is None
    assert result["current_verification"] is None
    assert result["assistant_response"]["response_type"] == "plan_execution_status"


def test_execute_pending_plan_with_no_ready_step_does_not_create_action():
    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": {
            "plan_id": "plan_test",
            "status": "partially_ready",
            "steps": [
                {
                    "step_id": "s1",
                    "title": "Needs variables",
                    "tool_name": "get_summary_stats",
                    "status": "needs_user_choice",
                    "execution_ready": False,
                    "required_user_choices": ["outcome"],
                }
            ],
        },
    }

    result = execute_pending_plan_node(state)

    assert result["current_action"] is None
    assert result["current_execution"] is None
    assert result["current_verification"] is None
    assert result["plan_execution_status"] == "waiting_for_user_choices"
    assert result["assistant_response"]["metadata"]["reason"] == "waiting_for_user_choices"


def test_execute_pending_plan_creates_action_for_ready_step():
    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": {
            "plan_id": "plan_test",
            "status": "verified",
            "steps": [
                {
                    "step_id": "s1",
                    "title": "Ready Step",
                    "tool_name": "get_summary_stats",
                    "status": "ready",
                    "execution_ready": True,
                    "arguments": {},
                }
            ],
        },
    }

    result = execute_pending_plan_node(state)

    assert result["current_action"] is not None
    assert result["current_action"]["tool_name"] == "get_summary_stats"
    assert result["current_action"]["arguments"] == {}
    assert result["current_plan_step_id"] == "s1"
    assert result["plan_execution_status"] == "started_step"
    assert result["action_origin"] == "pending_plan"


class DummyVerification:
    def __init__(self, status):
        self.status = status


def test_route_after_verify_ends_for_rejected_pending_plan_action():
    state = {
        "action_origin": "pending_plan",
        "current_verification": DummyVerification("rejected_recoverable"),
    }

    assert route_after_verify(state) == "end"

def test_execute_pending_plan_does_not_report_completed_when_unfinished_steps_remain():
    from core.workflow.nodes.plan_execution import execute_pending_plan_node

    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": {
            "plan_id": "plan_test",
            "status": "completed",
            "steps": [
                {
                    "step_id": "s1",
                    "tool_name": "inspect_dataset",
                    "status": "ready",
                    "execution_ready": True,
                    "execution_status": "completed",
                    "arguments": {},
                },
                {
                    "step_id": "s2",
                    "tool_name": "run_multiple_regression",
                    "status": "needs_user_choice",
                    "execution_ready": False,
                    "arguments": {},
                },
            ],
        },
        "plan_status": "completed",
    }

    result = execute_pending_plan_node(state)

    assert result["plan_execution_status"] == "waiting_for_user_choices"
    assert result["plan_status"] == "partially_executed"
    assert result["pending_plan"]["status"] == "partially_executed"
    assert result["current_plan_step_id"] is None
    assert result["action_origin"] is None