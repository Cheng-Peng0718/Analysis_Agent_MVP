from core.workflow.nodes.plan_execution import execute_pending_plan_node
from core.workflow.nodes.summarization import summarize_node


def test_plan_step_id_survives_until_summarize_and_finalizes_step():
    state = {
        "user_request": "run the plan",
        "workspace_dir": ".",
        "current_step": 0,
        "max_steps": 5,
        "active_data_version_id": "raw_v1",
        "data_versions": [],
        "data_audit_log": [],
        "observations": [],
        "analysis_runs": [],
        "pending_plan": {
            "plan_id": "plan_test",
            "status": "verified",
            "steps": [
                {
                    "step_id": "s1",
                    "title": "Inspect dataset",
                    "tool_name": "inspect_dataset",
                    "status": "ready",
                    "execution_ready": True,
                    "arguments": {},
                }
            ],
        },
        "plan_status": "verified",
        "plan_execution_status": None,
        "current_plan_step_id": None,
        "dataset_profile_v2": {
            "dataset_name": "test",
            "data_version_id": "raw_v1",
            "n_rows": 2,
            "n_cols": 1,
            "columns": {},
            "warnings": [],
        },
    }

    updates = execute_pending_plan_node(state)
    state.update(updates)

    assert state["current_plan_step_id"] == "s1"

    state["current_execution"] = {
        "execution_id": "exec_1",
        "action_id": "act_1",
        "tool_name": "inspect_dataset",
        "status": "ok",
        "success": True,
        "message": "ok",
        "payload": {},
        "artifacts": [],
    }

    updates = summarize_node(state)
    state.update(updates)

    assert state["current_plan_step_id"] is None
    assert state["pending_plan"]["steps"][0]["execution_status"] == "completed"
    assert state["plan_status"] == "completed"