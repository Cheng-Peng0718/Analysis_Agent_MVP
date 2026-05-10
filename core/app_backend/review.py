from __future__ import annotations

from typing import Any, Dict, Optional

from core.app_backend.snapshot import build_ui_snapshot
from core.runtime.graph_runner import run_graph_once


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, dict) else {}

    if hasattr(value, "dict"):
        dumped = value.dict()
        return dict(dumped) if isinstance(dumped, dict) else {}

    return {}


def _verification_status(state: Dict[str, Any]) -> Optional[str]:
    verification = _as_dict(state.get("current_verification"))
    status = verification.get("status")

    return str(status) if status is not None else None


def _verification_details(state: Dict[str, Any]) -> Dict[str, Any]:
    verification = _as_dict(state.get("current_verification"))
    details = verification.get("details")

    return details if isinstance(details, dict) else {}


def get_pending_review(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return the pending human-review payload, if the current state requires one.

    This is UI-facing read logic only. It does not mutate state and does not
    invoke LangGraph.
    """
    state = dict(state or {})
    status = _verification_status(state)

    if not state.get("human_review_required") and status != "needs_review":
        return None

    action = (
        _as_dict(state.get("pending_action"))
        or _as_dict(state.get("current_action"))
    )
    verification = _as_dict(state.get("current_verification"))
    details = _verification_details(state)

    action_hash = (
        state.get("human_review_action_hash")
        or details.get("action_hash")
    )

    return {
        "status": status,
        "pending_action": action or None,
        "current_verification": verification or None,
        "action_hash": action_hash,
        "feedback": verification.get("feedback"),
        "tool_name": (
            action.get("tool_name")
            if isinstance(action, dict)
            else None
        ),
    }


def prepare_human_review_decision_state(
    state: Dict[str, Any],
    *,
    decision: str,
    rejection_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepare graph state for a human-review decision.

    The UI should not write human_review_decision/action_hash directly.
    """
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be 'approved' or 'rejected'.")

    pending_review = get_pending_review(state)

    if pending_review is None:
        raise ValueError("No pending human review is available in state.")

    action_hash = pending_review.get("action_hash")

    if not action_hash:
        raise ValueError("Pending human review is missing action_hash.")

    next_state = dict(state)

    next_state["human_review_decision"] = decision
    next_state["human_review_action_hash"] = action_hash
    next_state["human_review_required"] = True

    if decision == "rejected":
        next_state["human_review_rejection_reason"] = (
            rejection_reason or "User rejected the human-review action."
        )
    else:
        next_state["human_review_rejection_reason"] = None

    return next_state


def submit_human_review_decision(
    state: Dict[str, Any],
    *,
    decision: str,
    rejection_reason: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Submit a human-review decision through the canonical graph runtime.

    This function does not call workflow nodes directly. It prepares state and
    invokes the graph runner, preserving the app_backend -> runtime boundary.
    """
    prepared_state = prepare_human_review_decision_state(
        state,
        decision=decision,
        rejection_reason=rejection_reason,
    )

    updated_state = run_graph_once(
        prepared_state,
        config=config,
    )

    return {
        "state": updated_state,
        "snapshot": build_ui_snapshot(updated_state),
    }


def approve_pending_review(
    state: Dict[str, Any],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return submit_human_review_decision(
        state,
        decision="approved",
        config=config,
    )


def reject_pending_review(
    state: Dict[str, Any],
    *,
    rejection_reason: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return submit_human_review_decision(
        state,
        decision="rejected",
        rejection_reason=rejection_reason,
        config=config,
    )