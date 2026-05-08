from __future__ import annotations
from core.action_access import get_action_type


def route_after_intent(state: dict):
    intent = state.get("interaction_intent")

    print(f"[ROUTE AFTER INTENT] intent = {intent}")

    if intent == "advisory":
        return "advisory_answer"

    if intent == "plan_only":
        return "plan_only"

    if intent == "execute_plan":
        return "execute_pending_plan"

    # Direct tool requests and unknown requests go to the unified supervisor path.
    return "supervisor"

def route_after_execute_pending_plan(state: dict):
    action = state.get("current_action")

    if action is not None:
        return "verify"

    return "end"

def route_after_supervisor(state: dict):
    """
    After supervisor:
    - tool_call -> verify
    - final_answer / ask_user -> deliverable_gate
    - max_steps reached -> end
    """
    action = state.get("current_action")

    if action and get_action_type(action) in ["final_answer", "ask_user"]:
        print("[ROUTE AFTER SUPERVISOR] final_answer -> deliverable_gate")
        return "deliverable_gate"

    if state.get("current_step", 0) >= state.get("max_steps", 12):
        print("[ROUTE AFTER SUPERVISOR] max_steps -> end")
        return "end"

    return "verify"