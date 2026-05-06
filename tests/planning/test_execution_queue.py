from core.planning.execution_queue import (
    find_next_executable_step,
    plan_step_to_action,
    mark_plan_step_started,
    mark_plan_step_after_execution,
)


def test_find_next_executable_step_skips_non_ready_steps():
    plan = {
        "plan_id": "plan_test",
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "tool_a",
                "status": "needs_user_choice",
                "execution_ready": False,
            },
            {
                "step_id": "s2",
                "tool_name": "tool_b",
                "status": "ready",
                "execution_ready": True,
                "arguments": {},
            },
        ],
    }

    step = find_next_executable_step(plan)

    assert step["step_id"] == "s2"


def test_find_next_executable_step_returns_none_when_no_ready_steps():
    plan = {
        "plan_id": "plan_test",
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "tool_a",
                "status": "needs_user_choice",
                "execution_ready": False,
            }
        ],
    }

    step = find_next_executable_step(plan)

    assert step is None



def test_plan_step_to_action_uses_verified_arguments():
    step = {
        "step_id": "s1",
        "tool_name": "generic_tool",
        "status": "ready",
        "execution_ready": True,
        "arguments": {"x": "GPA"},
    }

    action = plan_step_to_action(step)

    assert action.action_type == "tool_call"
    assert action.tool_name == "generic_tool"
    assert action.arguments == {"x": "GPA"}


def test_mark_plan_step_started():
    plan = {
        "plan_id": "plan_test",
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "tool_a",
                "status": "ready",
                "execution_ready": True,
            }
        ],
    }

    updated = mark_plan_step_started(plan, "s1", "act_123")

    step = updated["steps"][0]

    assert updated["status"] == "executing"
    assert step["execution_status"] == "running"
    assert step["action_id"] == "act_123"


def test_mark_plan_step_after_execution_completed():
    plan = {
        "plan_id": "plan_test",
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "tool_a",
                "status": "ready",
                "execution_ready": True,
                "execution_status": "running",
            }
        ],
    }

    updated = mark_plan_step_after_execution(
        plan,
        "s1",
        success=True,
        execution_id="exec_123",
        message="ok",
    )

    step = updated["steps"][0]

    assert step["execution_status"] == "completed"
    assert step["last_execution_id"] == "exec_123"
    assert updated["status"] == "completed"

def test_execute_pending_plan_creates_action_for_ready_step():
    from core.graph import execute_pending_plan_node

    state = {
        "active_data_version_id": "raw_v1",
        "pending_plan": {
            "plan_id": "plan_test",
            "status": "verified",
            "steps": [
                {
                    "step_id": "s1",
                    "title": "Ready Step",
                    "tool_name": "some_tool",
                    "status": "ready",
                    "execution_ready": True,
                    "arguments": {"x": "GPA"},
                }
            ],
        },
    }

    result = execute_pending_plan_node(state)

    assert result["current_action"] is not None
    assert result["current_action"].tool_name == "some_tool"
    assert result["current_plan_step_id"] == "s1"