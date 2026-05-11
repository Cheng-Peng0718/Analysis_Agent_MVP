from core.app_backend.plan_runner import (
    run_pending_plan_until_pause,
    should_pause_plan_execution,
)


def _state(plan_status="verified", plan_execution_status=None):
    return {
        "pending_plan": {
            "plan_id": "plan_1",
            "status": plan_status,
            "steps": [
                {
                    "step_id": "s1",
                    "status": "ready",
                    "execution_ready": True,
                }
            ],
        },
        "plan_status": plan_status,
        "plan_execution_status": plan_execution_status,
        "assistant_response": {},
        "dataset_profile_v2": {
            "dataset_name": "student_data",
            "data_version_id": "raw_v1",
            "columns": {},
        },
        "active_data_version_id": "raw_v1",
        "data_versions": [
            {
                "version_id": "raw_v1",
                "path": "workspace/data_versions/raw_v1.parquet",
            }
        ],
    }


def test_should_pause_when_no_pending_plan():
    paused, reason = should_pause_plan_execution({})

    assert paused is True
    assert reason == "no_pending_plan"


def test_should_pause_when_plan_completed():
    paused, reason = should_pause_plan_execution(_state(plan_status="completed"))

    assert paused is True
    assert reason == "terminal_plan_status:completed"


def test_should_pause_when_human_review_required():
    state = _state()
    state["human_review_required"] = True

    paused, reason = should_pause_plan_execution(state)

    assert paused is True
    assert reason == "human_review_required"


def test_should_continue_for_verified_pending_plan():
    paused, reason = should_pause_plan_execution(_state())

    assert paused is False
    assert reason == "continue"

def test_should_pause_when_waiting_for_user_choices():
    paused, reason = should_pause_plan_execution(
        _state(
            plan_status="partially_executed",
            plan_execution_status="waiting_for_user_choices",
        )
    )

    assert paused is True
    assert reason == "plan_execution_status:waiting_for_user_choices"


def test_run_pending_plan_until_pause_runs_multiple_turns_until_completed(monkeypatch):
    calls = []

    def fake_run_user_turn(state, user_message, *, config=None):
        calls.append(user_message)

        updated = dict(state)

        if len(calls) == 1:
            updated["pending_plan"] = {
                "plan_id": "plan_1",
                "status": "partially_executed",
                "steps": [],
            }
            updated["plan_status"] = "partially_executed"
            updated["plan_execution_status"] = "started_step"
            updated["assistant_response"] = {
                "response_type": "plan_execution_status",
                "content": "Step 1 completed.",
            }
            return {
                "state": updated,
                "snapshot": {},
            }

        updated["pending_plan"] = {
            "plan_id": "plan_1",
            "status": "completed",
            "steps": [],
        }
        updated["plan_status"] = "completed"
        updated["plan_execution_status"] = "completed"
        updated["assistant_response"] = {
            "response_type": "plan_execution_status",
            "content": "Plan completed.",
        }
        return {
            "state": updated,
            "snapshot": {},
        }

    monkeypatch.setattr(
        "core.app_backend.plan_runner.run_user_turn",
        fake_run_user_turn,
    )

    result = run_pending_plan_until_pause(_state())

    assert calls == [
        "Run the pending plan.",
        "Run the pending plan.",
    ]
    assert result["plan_run"]["status"] == "completed"
    assert result["plan_run"]["reason"] == "terminal_plan_status:completed"
    assert result["plan_run"]["n_iterations"] == 2
    assert result["snapshot"]["schema_version"] == "ui_snapshot_v2"

def test_run_pending_plan_until_pause_stops_for_waiting_for_user_choices(monkeypatch):
    calls = []

    def fake_run_user_turn(state, user_message, *, config=None):
        calls.append(user_message)

        updated = dict(state)
        updated["pending_plan"] = {
            "plan_id": "plan_1",
            "status": "partially_executed",
            "steps": [
                {
                    "step_id": "s1",
                    "status": "needs_user_choice",
                    "execution_ready": False,
                    "required_user_choices": ["target_col"],
                }
            ],
        }
        updated["plan_status"] = "partially_executed"
        updated["plan_execution_status"] = "waiting_for_user_choices"
        updated["assistant_response"] = {
            "response_type": "plan_execution_status",
            "content": "The pending plan is waiting for more information.",
            "metadata": {
                "reason": "waiting_for_user_choices",
            },
        }
        return {
            "state": updated,
            "snapshot": {},
        }

    monkeypatch.setattr(
        "core.app_backend.plan_runner.run_user_turn",
        fake_run_user_turn,
    )

    result = run_pending_plan_until_pause(_state())

    assert calls == ["Run the pending plan."]
    assert result["plan_run"]["status"] == "paused"
    assert result["plan_run"]["reason"] == "plan_execution_status:waiting_for_user_choices"
    assert result["plan_run"]["n_iterations"] == 1

def test_run_pending_plan_until_pause_stops_for_human_review(monkeypatch):
    def fake_run_user_turn(state, user_message, *, config=None):
        updated = dict(state)
        updated["human_review_required"] = True
        updated["current_verification"] = {
            "status": "needs_review",
            "feedback": "Approval required.",
            "details": {},
        }
        return {
            "state": updated,
            "snapshot": {},
        }

    monkeypatch.setattr(
        "core.app_backend.plan_runner.run_user_turn",
        fake_run_user_turn,
    )

    result = run_pending_plan_until_pause(_state())

    assert result["plan_run"]["status"] == "paused"
    assert result["plan_run"]["reason"] == "human_review_required"
    assert result["plan_run"]["n_iterations"] == 1


def test_run_pending_plan_until_pause_stops_at_max_iterations(monkeypatch):
    def fake_run_user_turn(state, user_message, *, config=None):
        updated = dict(state)
        updated["plan_status"] = "partially_executed"
        updated["pending_plan"] = {
            "plan_id": "plan_1",
            "status": "partially_executed",
            "steps": [],
        }
        return {
            "state": updated,
            "snapshot": {},
        }

    monkeypatch.setattr(
        "core.app_backend.plan_runner.run_user_turn",
        fake_run_user_turn,
    )

    result = run_pending_plan_until_pause(
        _state(),
        max_iterations=3,
    )

    assert result["plan_run"]["status"] == "paused"
    assert result["plan_run"]["reason"] == "max_iterations_reached"
    assert result["plan_run"]["n_iterations"] == 3

def test_run_pending_plan_until_pause_invokes_until_terminal(monkeypatch):
    states = [
        {
            "pending_plan": {
                "plan_id": "p1",
                "status": "partially_executed",
            },
            "plan_status": "partially_executed",
        },
        {
            "pending_plan": {
                "plan_id": "p1",
                "status": "completed",
            },
            "plan_status": "completed",
        },
    ]

    calls = []

    def fake_run_user_turn(state, message, *, config=None):
        calls.append((state, message, config))
        return {"state": states[len(calls) - 1]}

    monkeypatch.setattr(
        "core.app_backend.plan_runner.run_user_turn",
        fake_run_user_turn,
    )

    result = run_pending_plan_until_pause(
        {
            "pending_plan": {
                "plan_id": "p1",
                "status": "verified",
                "steps": [],
            },
            "plan_status": "verified",
        },
        config={"configurable": {"thread_id": "s1"}},
    )

    assert len(calls) == 2
    assert result["plan_run"]["status"] == "completed"
    assert result["plan_run"]["reason"] == "terminal_plan_status:completed"

