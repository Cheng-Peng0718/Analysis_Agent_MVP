import pytest

from core.app_backend.review import (
    approve_pending_review,
    get_pending_review,
    prepare_human_review_decision_state,
    reject_pending_review,
)


def _needs_review_state():
    return {
        "current_action": {
            "action_id": "act_clean",
            "action_type": "tool_call",
            "tool_name": "clean_data",
            "arguments": {
                "action_type": "drop",
                "strategy": "rows",
            },
            "reasoning_summary": "Drop rows with missing data.",
        },
        "current_verification": {
            "status": "needs_review",
            "feedback": "Data mutation requires approval.",
            "details": {
                "tool_name": "clean_data",
                "action_hash": "hash123",
                "canonical_arguments": {
                    "action_type": "drop",
                    "strategy": "rows",
                },
            },
        },
        "human_review_required": True,
        "pending_action": {
            "action_id": "act_clean",
            "action_type": "tool_call",
            "tool_name": "clean_data",
            "arguments": {
                "action_type": "drop",
                "strategy": "rows",
            },
        },
        "active_data_version_id": "raw_v1",
        "dataset_profile_v2": {
            "dataset_name": "student_data",
            "data_version_id": "raw_v1",
            "columns": {},
        },
    }


def test_get_pending_review_reads_review_payload():
    review = get_pending_review(_needs_review_state())

    assert review is not None
    assert review["status"] == "needs_review"
    assert review["tool_name"] == "clean_data"
    assert review["action_hash"] == "hash123"
    assert review["feedback"] == "Data mutation requires approval."


def test_get_pending_review_returns_none_without_review_state():
    assert get_pending_review({}) is None


def test_prepare_approval_state_sets_decision_and_hash():
    prepared = prepare_human_review_decision_state(
        _needs_review_state(),
        decision="approved",
    )

    assert prepared["human_review_decision"] == "approved"
    assert prepared["human_review_action_hash"] == "hash123"
    assert prepared["human_review_required"] is True
    assert prepared["human_review_rejection_reason"] is None


def test_prepare_rejection_state_sets_reason():
    prepared = prepare_human_review_decision_state(
        _needs_review_state(),
        decision="rejected",
        rejection_reason="Do not mutate the data.",
    )

    assert prepared["human_review_decision"] == "rejected"
    assert prepared["human_review_action_hash"] == "hash123"
    assert prepared["human_review_rejection_reason"] == "Do not mutate the data."


def test_prepare_review_decision_rejects_invalid_decision():
    with pytest.raises(ValueError, match="decision must be"):
        prepare_human_review_decision_state(
            _needs_review_state(),
            decision="yes",
        )


def test_approve_pending_review_invokes_graph_runner(monkeypatch):
    seen = {}

    def fake_resume_graph_once(state_update, *, config=None):
        seen["state_update"] = state_update
        seen["config"] = config

        updated = _needs_review_state()
        updated.update(state_update)
        updated["human_review_required"] = False
        updated["current_verification"] = {
            **updated["current_verification"],
            "status": "allowed",
            "feedback": "Human review approved this action for execution.",
        }
        return updated

    monkeypatch.setattr(
        "core.app_backend.review.resume_graph_once",
        fake_resume_graph_once,
    )

    result = approve_pending_review(
        _needs_review_state(),
        config={"configurable": {"thread_id": "s1"}},
    )

    assert seen["state_update"]["human_review_decision"] == "approved"
    assert seen["state_update"]["human_review_action_hash"] == "hash123"
    assert seen["config"] == {"configurable": {"thread_id": "s1"}}
    assert result["state"]["current_verification"]["status"] == "allowed"
    assert result["snapshot"]["review"]["human_review_required"] is False


def test_reject_pending_review_invokes_graph_runner(monkeypatch):
    seen = {}

    def fake_resume_graph_once(state_update, *, config=None):
        seen["state_update"] = state_update
        seen["config"] = config

        updated = _needs_review_state()
        updated.update(state_update)
        updated["human_review_required"] = False
        updated["pending_action"] = None
        updated["current_action"] = None
        updated["current_verification"] = None
        return updated

    monkeypatch.setattr(
        "core.app_backend.review.resume_graph_once",
        fake_resume_graph_once,
    )

    result = reject_pending_review(
        _needs_review_state(),
        rejection_reason="No.",
    )

    assert seen["state_update"]["human_review_decision"] == "rejected"
    assert seen["state_update"]["human_review_rejection_reason"] == "No."
    assert result["snapshot"]["review"]["human_review_required"] is False