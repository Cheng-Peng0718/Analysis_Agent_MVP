from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.app_backend.snapshot import build_ui_snapshot
from core.app_backend.turn import run_user_turn


TERMINAL_PLAN_STATUSES = {
    "completed",
    "cancelled",
    "blocked",
    "partially_failed",
}

PAUSE_PLAN_EXECUTION_STATUSES = {
    # No plan / no runnable continuation.
    "no_pending_plan",

    # New PlanRunController pause states.
    "waiting_for_user_choices",
    "awaiting_review",
    "blocked_no_actionable_step",
    "blocked_invalid_plan_controller_decision",

    # Verification / execution failure states.
    "step_verification_failed",

    # Legacy compatibility states. Keep for older tests / stale UI paths.
    "blocked_no_ready_steps",
    "blocked_pending_data_cleaning",
}

PAUSE_VERIFICATION_STATUSES = {
    "needs_review",
    "rejected_recoverable",
    "rejected_terminal",
}

PAUSE_EXECUTION_STATUSES = {
    "blocked",
    "failed",
}


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


def _status_from_mapping(value: Any) -> Optional[str]:
    payload = _as_dict(value)
    status = payload.get("status")

    if status is None:
        return None

    return str(status)


def should_pause_plan_execution(state: Dict[str, Any]) -> tuple[bool, str]:
    """
    Decide whether the backend plan execution loop must pause.

    This is not a planner. It only interprets graph state after each canonical
    graph invocation and stops when user input, approval, or error handling is
    required.
    """
    state = dict(state or {})

    pending_plan = _as_dict(state.get("pending_plan"))
    plan_status = state.get("plan_status") or pending_plan.get("status")
    plan_execution_status = state.get("plan_execution_status")

    if not pending_plan:
        return True, "no_pending_plan"

    if plan_status in TERMINAL_PLAN_STATUSES:
        return True, f"terminal_plan_status:{plan_status}"

    if plan_execution_status in PAUSE_PLAN_EXECUTION_STATUSES:
        return True, f"plan_execution_status:{plan_execution_status}"

    if state.get("human_review_required") is True:
        return True, "human_review_required"

    verification_status = _status_from_mapping(state.get("current_verification"))

    if verification_status in PAUSE_VERIFICATION_STATUSES:
        return True, f"verification_status:{verification_status}"

    current_execution = _as_dict(state.get("current_execution"))
    execution_status = current_execution.get("status")

    if execution_status in PAUSE_EXECUTION_STATUSES:
        return True, f"execution_status:{execution_status}"

    if current_execution and current_execution.get("success") is False:
        return True, "execution_success_false"

    return False, "continue"


def run_pending_plan_until_pause(
    state: Dict[str, Any],
    *,
    config: Optional[Dict[str, Any]] = None,
    max_iterations: int = 20,
    execution_message: str = "Run the pending plan.",
) -> Dict[str, Any]:
    """
    Execute a pending plan continuously until the graph reaches a pause point.

    UI code should call this after the user confirms a plan. The UI should not
    manually execute one plan step at a time.
    """
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive.")

    current_state = dict(state or {})
    iterations: List[Dict[str, Any]] = []

    for index in range(max_iterations):
        should_pause, reason = should_pause_plan_execution(current_state)

        if should_pause:
            status = (
                "completed"
                if str(reason).startswith("terminal_plan_status:completed")
                else "paused"
            )

            return {
                "state": current_state,
                "snapshot": build_ui_snapshot(current_state),
                "plan_run": {
                    "status": status,
                    "reason": reason,
                    "iterations": iterations,
                    "n_iterations": len(iterations),
                },
            }

        command_state = dict(current_state)
        command_state["_backend_command_for_next_turn"] = "execute_pending_plan"

        turn_result = run_user_turn(
            command_state,
            execution_message,
            config=config,
        )

        current_state = turn_result["state"]

        should_pause, reason = should_pause_plan_execution(current_state)

        iterations.append({
            "iteration": index + 1,
            "reason": reason,
            "plan_status": current_state.get("plan_status"),
            "plan_execution_status": current_state.get("plan_execution_status"),
            "current_plan_step_id": current_state.get("current_plan_step_id"),
            "human_review_required": bool(current_state.get("human_review_required")),
        })

        if should_pause:
            status = (
                "completed"
                if str(reason).startswith("terminal_plan_status:completed")
                else "paused"
            )

            return {
                "state": current_state,
                "snapshot": build_ui_snapshot(current_state),
                "plan_run": {
                    "status": status,
                    "reason": reason,
                    "iterations": iterations,
                    "n_iterations": len(iterations),
                },
            }

    return {
        "state": current_state,
        "snapshot": build_ui_snapshot(current_state),
        "plan_run": {
            "status": "paused",
            "reason": "max_iterations_reached",
            "iterations": iterations,
            "n_iterations": len(iterations),
        },
    }