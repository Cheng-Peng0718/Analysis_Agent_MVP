from __future__ import annotations

from typing import Any, Dict, Optional

from core.app_backend.snapshot import build_ui_snapshot
from core.runtime.graph_runner import run_graph_once


def prepare_turn_state(
    state: Dict[str, Any],
    user_message: str,
) -> Dict[str, Any]:
    """
    Prepare graph state for a new user turn.

    This function does not route nodes manually. It only updates the user
    request and clears per-turn transient fields that should not be reused as
    fresh outputs before LangGraph runs.
    """
    if not isinstance(state, dict):
        raise TypeError("run_user_turn requires state to be a dictionary.")

    message = (user_message or "").strip()

    if not message:
        raise ValueError("user_message must not be empty.")

    next_state = dict(state)

    next_state["user_request"] = message

    # Backend commands are internal control signals, not user text. Plan
    # runner sets _backend_command_for_next_turn before invoking this public
    # turn adapter. Normal chat turns clear the command so stale execution
    # intent cannot leak into future messages.
    next_state["backend_command"] = next_state.pop(
        "_backend_command_for_next_turn",
        None,
    )

    # Per-turn outputs should be produced by the graph invocation, not reused
    # from the previous turn.
    next_state["assistant_response"] = {}
    next_state["current_execution"] = None
    next_state["current_verification"] = None
    next_state["execution_audit"] = {}

    next_state["last_summarized_action_origin"] = None
    next_state["last_summarized_plan_step_id"] = None

    return next_state


def run_user_turn(
    state: Dict[str, Any],
    user_message: str,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run one user message through the canonical LangGraph backend.

    UI code should call this function for normal chat turns. It returns both
    the updated graph state and a stable UI snapshot.
    """
    input_state = prepare_turn_state(state, user_message)

    updated_state = run_graph_once(
        input_state,
        config=config,
    )

    return {
        "state": updated_state,
        "snapshot": build_ui_snapshot(updated_state),
    }