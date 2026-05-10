import json

import pandas as pd

from core.controller.backend_turn import run_backend_turn
from core.ui_adapter.events import (
    apply_ui_event_to_state,
    make_approve_human_review_event,
    make_run_plan_event,
    make_user_message_event,
)

from core.controller import backend_turn as backend_turn_module
from core.schema import ActionProposal


def apply_updates(state, updates):
    merged = dict(state)
    merged.update(updates)
    return merged


def make_legacy_dataset_profile(*, with_missing=False):
    return {
        "n_rows": 5,
        "n_cols": 3,
        "columns": [
            {
                "name": "GPA",
                "dtype": "float64",
                "semantic_type": "continuous_numeric",
                "missing_count": 1 if with_missing else 0,
                "missing_rate": 0.2 if with_missing else 0.0,
                "n_unique": 4 if with_missing else 5,
            },
            {
                "name": "SATM",
                "dtype": "float64",
                "semantic_type": "continuous_numeric",
                "missing_count": 1 if with_missing else 0,
                "missing_rate": 0.2 if with_missing else 0.0,
                "n_unique": 4 if with_missing else 5,
            },
            {
                "name": "Sex",
                "dtype": "object",
                "semantic_type": "binary_categorical",
                "missing_count": 0,
                "missing_rate": 0.0,
                "n_unique": 2,
            },
        ],
    }


def make_workspace(tmp_path, *, with_missing=False):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    if with_missing:
        df = pd.DataFrame({
            "GPA": [3.0, 3.2, None, 3.8, 4.0],
            "SATM": [600, None, 650, 680, 700],
            "Sex": ["F", "M", "F", "M", "F"],
        })
    else:
        df = pd.DataFrame({
            "GPA": [3.0, 3.2, 3.5, 3.8, 4.0],
            "SATM": [600, 620, 650, 680, 700],
            "Sex": ["F", "M", "F", "M", "F"],
        })

    data_path = workspace_dir / "working_data.parquet"
    df.to_parquet(data_path)

    return workspace_dir, data_path


def make_base_state(tmp_path, *, with_missing=False):
    workspace_dir, data_path = make_workspace(
        tmp_path,
        with_missing=with_missing,
    )

    return {
        "user_request": "",
        "workspace_dir": str(workspace_dir),
        "current_step": 0,
        "max_steps": 5,
        "dataset_profile": make_legacy_dataset_profile(with_missing=with_missing),
        "observations": [],
        "analysis_runs": [],
        "data_versions": [
            {
                "version_id": "raw_v1",
                "path": str(data_path),
                "parent_version_id": None,
                "n_rows": 5,
                "n_cols": 3,
            }
        ],
        "data_audit_log": [],
        "active_data_version_id": "raw_v1",
        "pending_plan": None,
        "plan_status": None,
        "plan_execution_status": None,
        "current_plan_step_id": None,
        "current_action": None,
        "current_execution": None,
        "current_verification": None,
        "repair_attempts": [],
    }


def make_summary_pending_plan():
    return {
        "plan_id": "plan_controller_summary",
        "status": "partially_ready",
        "steps": [
            {
                "step_id": "s1",
                "title": "Compute summary statistics",
                "tool_name": "get_summary_stats",
                "status": "ready",
                "execution_ready": True,
                "execution_status": "not_started",
                "arguments": {},
                "reason": "Summarize active dataset.",
            }
        ],
        "blocked_or_not_recommended": [],
    }


def make_clean_pending_plan():
    return {
        "plan_id": "plan_controller_clean",
        "status": "partially_ready",
        "steps": [
            {
                "step_id": "s1",
                "title": "Drop rows with missing GPA or SATM",
                "tool_name": "clean_data",
                "status": "ready",
                "execution_ready": True,
                "execution_status": "not_started",
                "arguments": {
                    "action_type": "drop",
                    "strategy": "rows",
                    "columns": ["GPA", "SATM"],
                },
                "reason": "Remove rows with missing values.",
            }
        ],
        "blocked_or_not_recommended": [],
    }


def test_backend_turn_controller_handles_advisory_user_message(tmp_path):
    state = make_base_state(tmp_path)

    updates = apply_ui_event_to_state(
        state,
        make_user_message_event(
            "I want to do analysis to this dataset, what can I do?"
        ),
    )
    state = apply_updates(state, updates)

    result = run_backend_turn(state)

    assert result["status"] == "ok"
    assert result["node_trace"] == [
        "intent_router_node",
        "advisory_answer_node",
    ]

    snapshot = result["ui_snapshot"]

    assert snapshot["assistant_response"]["response_type"] == "advisory"
    assert snapshot["runtime"]["has_current_action"] is False

    json.dumps(result)


def test_backend_turn_controller_runs_safe_plan_step_to_summary(tmp_path):
    state = make_base_state(tmp_path)
    state["pending_plan"] = make_summary_pending_plan()
    state["plan_status"] = "partially_ready"

    updates = apply_ui_event_to_state(
        state,
        make_run_plan_event(),
    )
    state = apply_updates(state, updates)

    result = run_backend_turn(state)

    assert result["status"] == "ok"

    assert result["node_trace"] == [
        "intent_router_node",
        "execute_pending_plan_node",
        "verify_node",
        "execute_node",
        "summarize_node",
    ]

    state = result["state"]
    snapshot = result["ui_snapshot"]

    assert len(state["analysis_runs"]) == 1
    assert state["analysis_runs"][0]["tool_name"] == "get_summary_stats"
    assert state["analysis_runs"][0]["success"] is True

    assert snapshot["analysis"]["analysis_runs"][0]["tool_name"] == "get_summary_stats"
    assert snapshot["runtime"]["has_current_action"] is False
    assert snapshot["audits"]["execution_audit"]["status"] == "ok"

    json.dumps(result)


def test_backend_turn_controller_stops_for_clean_data_human_review(tmp_path):
    state = make_base_state(
        tmp_path,
        with_missing=True,
    )
    state["pending_plan"] = make_clean_pending_plan()
    state["plan_status"] = "partially_ready"

    updates = apply_ui_event_to_state(
        state,
        make_run_plan_event(),
    )
    state = apply_updates(state, updates)

    result = run_backend_turn(state)

    assert result["status"] == "needs_review"

    assert result["node_trace"] == [
        "intent_router_node",
        "execute_pending_plan_node",
        "verify_node",
    ]

    snapshot = result["ui_snapshot"]

    assert snapshot["human_review"]["required"] is True
    assert snapshot["human_review"]["action"]["tool_name"] == "clean_data"
    assert snapshot["runtime"]["has_current_action"] is True

    json.dumps(result)


def test_backend_turn_controller_approval_continues_clean_data_execution(tmp_path):
    state = make_base_state(
        tmp_path,
        with_missing=True,
    )
    state["pending_plan"] = make_clean_pending_plan()
    state["plan_status"] = "partially_ready"

    updates = apply_ui_event_to_state(
        state,
        make_run_plan_event(),
    )
    state = apply_updates(state, updates)

    first_result = run_backend_turn(state)

    assert first_result["status"] == "needs_review"

    state = first_result["state"]
    action_hash = first_result["ui_snapshot"]["human_review"]["action_hash"]

    updates = apply_ui_event_to_state(
        state,
        make_approve_human_review_event(action_hash=action_hash),
    )
    state = apply_updates(state, updates)

    second_result = run_backend_turn(state)

    assert second_result["status"] == "ok"

    assert second_result["node_trace"] == [
        "human_review_node",
        "execute_node",
        "summarize_node",
    ]

    state = second_result["state"]
    snapshot = second_result["ui_snapshot"]

    assert len(state["analysis_runs"]) == 1
    assert state["analysis_runs"][0]["tool_name"] == "clean_data"
    assert state["analysis_runs"][0]["success"] is True

    assert snapshot["human_review"]["required"] is False
    assert snapshot["data"]["active_data_version_id"] != "raw_v1"
    assert snapshot["analysis"]["analysis_runs"][0]["tool_name"] == "clean_data"
    assert snapshot["runtime"]["has_current_action"] is False

    json.dumps(second_result)


def test_backend_turn_controller_dispatches_direct_regression_to_execution(
    tmp_path,
    monkeypatch,
):
    calls = []

    def fake_supervisor_node(state):
        calls.append("supervisor")
        assert state["interaction_intent"] == "direct_tool"
        assert state["intent_decision"]["intent"] == "direct_analysis"
        assert state["task_spec"]["goal_type"] == "regression_modeling"

        return {
            "current_action": ActionProposal(
                action_id="act_direct_regression",
                action_type="tool_call",
                tool_name="run_multiple_regression",
                arguments={
                    "target_col": "GPA",
                    "feature_cols": ["SATM"],
                },
                reasoning_summary="Run direct regression.",
            ),
        }

    def fake_verify_node(state):
        calls.append("verify")
        assert state["current_action"].tool_name == "run_multiple_regression"
        return {
            "current_verification": {
                "status": "allowed",
                "feedback": "ok",
                "details": {},
            },
            "human_review_required": False,
        }

    def fake_execute_node(state):
        calls.append("execute")
        return {
            "current_execution": {
                "execution_id": "exec_direct_regression",
                "action_id": "act_direct_regression",
                "tool_name": "run_multiple_regression",
                "status": "ok",
                "success": True,
                "message": "Regression completed.",
                "payload": {
                    "metrics": {"r_squared": 0.72},
                },
                "artifacts": [],
            }
        }

    def fake_summarize_node(state):
        calls.append("summarize")
        return {
            "observations": [
                {
                    "observation_id": "obs_direct_regression",
                    "source_action_id": "act_direct_regression",
                    "tool_name": "run_multiple_regression",
                    "status": "ok",
                    "success": True,
                    "summary": "Regression completed.",
                    "structured_data": {
                        "r_squared": 0.72,
                    },
                    "raw_data": {},
                }
            ],
            "analysis_runs": [
                {
                    "run_id": "run_direct_regression",
                    "tool_name": "run_multiple_regression",
                    "status": "ok",
                    "success": True,
                    "metrics": {"r_squared": 0.72},
                    "artifacts": [],
                }
            ],
            "current_action": None,
            "current_execution": None,
            "current_verification": None,
        }

    monkeypatch.setattr(backend_turn_module, "supervisor_node", fake_supervisor_node)
    monkeypatch.setattr(backend_turn_module, "verify_node", fake_verify_node)
    monkeypatch.setattr(backend_turn_module, "execute_node", fake_execute_node)
    monkeypatch.setattr(backend_turn_module, "summarize_node", fake_summarize_node)

    state = make_base_state(tmp_path)
    state["assistant_response"] = {
        "response_id": "resp_stale",
        "response_type": "advisory",
        "content": "stale advisory fallback",
        "source_node": "advisory_answer",
        "metadata": {},
    }

    updates = apply_ui_event_to_state(
        state,
        make_user_message_event("run linear regression of GPA on SATM"),
    )
    state = apply_updates(state, updates)

    result = run_backend_turn(state)

    assert result["status"] == "ok"
    assert result["node_trace"] == [
        "intent_router_node",
        "supervisor_node",
        "verify_node",
        "execute_node",
        "summarize_node",
    ]
    assert calls == ["supervisor", "verify", "execute", "summarize"]

    state = result["state"]
    response = result["ui_snapshot"]["assistant_response"]

    assert state["interaction_intent"] == "direct_tool"
    assert state["intent_decision"]["intent"] == "direct_analysis"
    assert state["analysis_runs"][0]["tool_name"] == "run_multiple_regression"
    assert response["source_node"] == "backend_turn_direct_tool"
    assert response["content"] != "stale advisory fallback"
    assert "run_multiple_regression" in response["content"]

    json.dumps(result)


def test_backend_turn_controller_direct_clean_data_stops_for_human_review(
    tmp_path,
    monkeypatch,
):
    calls = []

    def fake_supervisor_node(state):
        calls.append("supervisor")
        assert state["interaction_intent"] == "direct_tool"
        assert state["intent_decision"]["intent"] == "modify_data"
        assert state["task_spec"]["goal_type"] == "data_cleaning"

        return {
            "current_action": ActionProposal(
                action_id="act_direct_clean",
                action_type="tool_call",
                tool_name="clean_data",
                arguments={
                    "action_type": "drop",
                    "strategy": "rows",
                    "columns": ["GPA"],
                },
                reasoning_summary="Drop rows with missing GPA.",
            ),
        }

    def fail_execute_node(state):
        raise AssertionError("clean_data executed before human review")

    monkeypatch.setattr(backend_turn_module, "supervisor_node", fake_supervisor_node)
    monkeypatch.setattr(backend_turn_module, "execute_node", fail_execute_node)

    state = make_base_state(tmp_path, with_missing=True)

    updates = apply_ui_event_to_state(
        state,
        make_user_message_event("drop rows with missing GPA"),
    )
    state = apply_updates(state, updates)

    result = run_backend_turn(state)

    assert result["status"] == "needs_review"
    assert result["node_trace"] == [
        "intent_router_node",
        "supervisor_node",
        "verify_node",
        "human_review_node",
    ]
    assert calls == ["supervisor"]

    state = result["state"]
    snapshot = result["ui_snapshot"]

    assert state["interaction_intent"] == "direct_tool"
    assert state["intent_decision"]["intent"] == "modify_data"
    assert state["current_verification"]["status"] == "needs_review"
    assert state["current_verification"]["details"]["tool_name"] == "clean_data"
    assert state["current_verification"]["details"]["requires_confirmation"] is True
    assert state["current_verification"]["details"]["mutates_data"] is True
    assert state["pending_action"]["tool_name"] == "clean_data"
    assert snapshot["human_review"]["required"] is True
    assert snapshot["human_review"]["action"]["tool_name"] == "clean_data"
    assert snapshot["runtime"]["has_current_action"] is True
    assert state["analysis_runs"] == []
    assert state["observations"] == []
    assert state["data_versions"][0]["version_id"] == "raw_v1"
    assert state["active_data_version_id"] == "raw_v1"
    assert snapshot["assistant_response"]["source_node"] == "backend_turn_direct_tool"
    assert "No data has been changed yet" in snapshot["assistant_response"]["content"]

    json.dumps(result)


def test_backend_turn_controller_direct_tool_without_action_gets_fresh_response(
    tmp_path,
    monkeypatch,
):
    def fake_intent_router_node(state):
        return {
            "interaction_intent": "direct_tool",
            "intent_decision": {
                "intent": "direct_analysis",
                "confidence": 0.9,
                "reason": "test direct request",
                "should_execute": True,
            },
        }

    def fake_supervisor_node(state):
        return {
            "current_action": None,
        }

    monkeypatch.setattr(
        backend_turn_module,
        "intent_router_node",
        fake_intent_router_node,
    )
    monkeypatch.setattr(backend_turn_module, "supervisor_node", fake_supervisor_node)

    state = make_base_state(tmp_path)
    state["assistant_response"] = {
        "response_id": "resp_stale",
        "response_type": "advisory",
        "content": "stale advisory fallback",
        "source_node": "advisory_answer",
        "metadata": {},
    }

    result = run_backend_turn(state)

    assert result["status"] == "blocked"
    assert result["node_trace"] == [
        "intent_router_node",
        "supervisor_node",
    ]

    response = result["ui_snapshot"]["assistant_response"]

    assert response["response_id"] != "resp_stale"
    assert response["response_type"] == "error"
    assert response["source_node"] == "backend_turn_direct_tool"
    assert response["content"] != "stale advisory fallback"
    assert "No tools were executed" in response["content"]

    json.dumps(result)


def test_backend_turn_controller_does_not_execute_after_plan_choice_update(tmp_path):
    state = make_base_state(tmp_path)
    state["pending_plan"] = {
        "plan_id": "plan_choice_update",
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "run_multiple_regression",
                "status": "needs_user_choice",
                "execution_ready": False,
                "execution_status": "not_started",
                "variables": {},
                "arguments": {},
                "required_user_choices": ["target_col", "feature_cols"],
            }
        ],
    }

    updates = apply_ui_event_to_state(
        state,
        {
            "event_type": "update_plan_step_choices",
            "payload": {
                "step_id": "s1",
                "choices": {
                    "target_col": "GPA",
                    "feature_cols": ["SATM"],
                },
            },
        },
    )
    state = apply_updates(state, updates)

    result = run_backend_turn(state)

    assert result["status"] == "ok"
    assert result["node_trace"] == []
    assert result["ui_snapshot"]["plan"]["pending_plan"]["steps"][0]["status"] == "ready"
    assert result["ui_snapshot"]["runtime"]["has_current_action"] is False

    json.dumps(result)

def test_backend_turn_exposes_assistant_response_for_verification_rejection(monkeypatch):
    def fake_intent_router_node(state):
        return {
            "interaction_intent": "execute_plan",
        }

    def fake_execute_pending_plan_node(state):
        return {
            "current_action": ActionProposal(
                action_id="act_clean_bad",
                action_type="tool_call",
                tool_name="clean_data",
                arguments={
                    "action_type": "drop rows",
                    "strategy": "drop",
                },
                reasoning_summary="Bad clean_data request.",
            ),
            "action_origin": "pending_plan",
            "plan_execution_status": "started_step",
        }

    def fake_verify(action, profile):
        return (
            "rejected_recoverable",
            "Invalid clean_data arguments.",
            {
                "status": "rejected_recoverable",
                "feedback": "Invalid clean_data arguments.",
                "error_code": "INVALID_TOOL_ARGUMENTS",
                "details": {},
            },
        )

    monkeypatch.setattr(
        backend_turn_module,
        "intent_router_node",
        fake_intent_router_node,
    )
    monkeypatch.setattr(
        backend_turn_module,
        "execute_pending_plan_node",
        fake_execute_pending_plan_node,
    )
    monkeypatch.setattr(
        "core.workflow.nodes.verification.verify",
        fake_verify,
    )

    result = run_backend_turn({
        "user_request": "run the plan",
        "workspace_dir": "./",
        "current_step": 1,
        "max_steps": 5,
        "dataset_profile": {
            "columns": ["GPA"],
        },
        "observations": [],
        "analysis_runs": [],
        "data_versions": [],
        "data_audit_log": [],
        "repair_attempts": [],
        "active_data_version_id": "raw_v1",
    })

    assert result["status"] == "blocked"

    response = result["state"]["assistant_response"]
    assert response["response_type"] == "error"
    assert response["metadata"]["semantic_type"] == "verification_blocked"
    assert "INVALID_TOOL_ARGUMENTS" in response["content"]

    snapshot = result["ui_snapshot"]

    assert snapshot["assistant_response"]["response_type"] == "error"
    assert snapshot["assistant_response"]["metadata"]["semantic_type"] == "verification_blocked"
    assert snapshot["repair"]["decision"]["status"] in {
        "repairable",
        "needs_user",
        "terminal",
    }
    assert snapshot["runtime"]["current_verification"]["status"] == "rejected_recoverable"
