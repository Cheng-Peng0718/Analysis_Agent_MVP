from __future__ import annotations

from core.action_access import (
    get_action_arguments,
    get_action_id,
    get_action_tool_name,
)
from core.action_codec import action_to_state_dict
from core.planning.execution_queue import (
    find_next_actionable_step,
    make_review_state_update,
    mark_plan_step_started,
)
from core.responses import make_response_update
from core.workflow.profile_access import get_dataset_profile_v2

DONE_EXECUTION_STATUSES = {
    "completed",
    "skipped",
}


def _plan_has_unfinished_steps(pending_plan: dict) -> bool:
    steps = pending_plan.get("steps", []) or []

    for step in steps:
        if not isinstance(step, dict):
            continue

        if step.get("execution_status") not in DONE_EXECUTION_STATUSES:
            return True

    return False


def _normalize_plan_for_pause(pending_plan: dict) -> dict:
    """
    Normalize a paused plan.

    A plan is not completed merely because no execution-ready steps remain.
    If unfinished steps still exist, keep it partially_executed so the UI/runner
    can explain the pause instead of treating the plan as done.
    """
    plan = dict(pending_plan or {})

    if plan.get("status") == "completed" and _plan_has_unfinished_steps(plan):
        plan["status"] = "partially_executed"

    return plan


def _step_title(step: dict | None) -> str:
    if not isinstance(step, dict):
        return "unknown step"

    return step.get("title") or step.get("step_id") or "unknown step"


def _step_tool(step: dict | None) -> str:
    if not isinstance(step, dict):
        return "unknown_tool"

    return step.get("tool_name") or "unknown_tool"


def _format_candidate_variables(step: dict | None) -> list[str]:
    if not isinstance(step, dict):
        return []

    candidates = step.get("candidate_variables") or {}

    if not isinstance(candidates, dict):
        return []

    lines: list[str] = []

    for role, values in candidates.items():
        if not values:
            continue

        if isinstance(values, list):
            rendered = ", ".join(str(value) for value in values)
        else:
            rendered = str(values)

        lines.append(f"- {role}: {rendered}")

    return lines


def _make_pause_response(*, state: dict, pending_plan: dict, decision, reason_code: str):
    paused_plan = _normalize_plan_for_pause(pending_plan)
    readiness = decision.readiness
    step = decision.step

    reason = decision.reason or (
        readiness.reason if readiness is not None else "No candidate step found."
    )
    missing_choices = (
        readiness.missing_user_choices
        if readiness is not None
        else []
    )

    lines = []

    if decision.kind == "ask_user":
        lines.append("The pending plan is waiting for more information before it can continue.")
    else:
        lines.append("The pending plan cannot continue automatically right now.")

    lines.append("")
    lines.append(f"Next step: {_step_title(step)}")
    lines.append(f"Tool: {_step_tool(step)}")
    lines.append(f"Reason: {reason}")

    if missing_choices:
        lines.append("")
        lines.append("Missing choices:")
        for choice in missing_choices:
            lines.append(f"- {choice}")

    candidate_lines = _format_candidate_variables(step)
    if candidate_lines:
        lines.append("")
        lines.append("Candidate variables:")
        lines.extend(candidate_lines)

    lines.append("")
    if decision.kind == "ask_user":
        lines.append("Reply in chat with the missing variables or choices; no UI buttons are required.")
    else:
        lines.append("No tools were executed.")

    content = "\n".join(lines)

    updates = make_response_update(
        response_type="plan_execution_status",
        content=content,
        source_node="execute_pending_plan",
        data_version_id=state.get("active_data_version_id"),
        plan_id=paused_plan.get("plan_id"),
        plan_status=paused_plan.get("status"),
        metadata={
            "reason": reason_code,
            "action_kind": decision.kind,
            "step_id": step.get("step_id") if isinstance(step, dict) else None,
            "tool_name": step.get("tool_name") if isinstance(step, dict) else None,
            "readiness": (
                readiness.model_dump()
                if readiness is not None
                else None
            ),
        },
    )

    updates.update({
        "pending_plan": paused_plan,
        "plan_status": paused_plan.get("status"),
        "plan_execution_status": reason_code,
        "current_plan_step_id": None,
        "action_origin": None,
        "current_action": None,
        "current_execution": None,
        "current_verification": None,
        "human_review_required": False,
        "pending_action": None,
    })

    return updates


def _make_completed_response(*, state: dict, pending_plan: dict, reason: str):
    completed_plan = dict(pending_plan or {})
    completed_plan["status"] = "completed"

    updates = make_response_update(
        response_type="plan_execution_status",
        content="The pending plan is complete. No remaining tools need to run.",
        source_node="execute_pending_plan",
        data_version_id=state.get("active_data_version_id"),
        plan_id=completed_plan.get("plan_id"),
        plan_status="completed",
        metadata={
            "reason": reason,
        },
    )
    updates.update({
        "pending_plan": completed_plan,
        "plan_status": "completed",
        "plan_execution_status": "completed",
        "current_plan_step_id": None,
        "action_origin": None,
        "current_action": None,
        "current_execution": None,
        "current_verification": None,
        "human_review_required": False,
        "pending_action": None,
    })
    return updates


def _make_review_response(*, state: dict, pending_plan: dict, decision):
    action = decision.action
    step = decision.step
    readiness = decision.readiness

    verification = None
    if readiness is not None:
        verification = readiness.validation_details

    # `assess_plan_step_readiness` stores the full VerificationResult only as
    # a validation status/reason/details tuple. Re-run the canonical validator
    # here would duplicate logic. Instead, the readiness object has already
    # accepted the action as reviewable and its details contain canonical
    # verification details. Build a minimal review verification through the
    # runtime validator in `execute_pending_plan_node` below.
    from core.analysis_tool_plugins.validation import validate_plugin_action

    review_verification = validate_plugin_action(
        action,
        profile=get_dataset_profile_v2(state),
    )

    updates = make_review_state_update(
        pending_plan=pending_plan,
        step=step,
        action=action,
        verification=review_verification,
    )

    content = (
        "The next plan step is ready, but it requires human review before execution.\n\n"
        f"Step: {_step_title(step)}\n"
        f"Tool: {get_action_tool_name(action)}\n"
        f"Arguments: {get_action_arguments(action)}\n\n"
        "Review the pending action and approve or reject it."
    )

    response_update = make_response_update(
        response_type="plan_execution_status",
        content=content,
        source_node="execute_pending_plan",
        data_version_id=state.get("active_data_version_id"),
        plan_id=updates["pending_plan"].get("plan_id"),
        plan_status=updates["pending_plan"].get("status"),
        metadata={
            "reason": "human_review_required",
            "step_id": step.get("step_id"),
            "tool_name": get_action_tool_name(action),
        },
    )
    updates.update(response_update)
    return updates


def execute_pending_plan_node(state: dict):
    print("\n" + "=" * 40)
    print("[EXECUTE PENDING PLAN NODE ENTERED]")
    print(f"plan_status = {state.get('plan_status')}")
    print(f"has_pending_plan = {state.get('pending_plan') is not None}")
    print("=" * 40 + "\n")

    pending_plan = state.get("pending_plan")

    if not pending_plan:
        content = (
            "There is no pending plan to execute. "
            "Please ask me to make a plan first."
        )

        updates = make_response_update(
            response_type="plan_execution_status",
            content=content,
            source_node="execute_pending_plan",
            data_version_id=state.get("active_data_version_id"),
            metadata={
                "reason": "no_pending_plan",
            },
        )

        updates.update({
            "current_action": None,
            "current_execution": None,
            "current_verification": None,
            "current_plan_step_id": None,
            "action_origin": None,
            "human_review_required": False,
            "pending_action": None,
            "plan_execution_status": "no_pending_plan",
        })

        return updates

    dataset_profile = get_dataset_profile_v2(state)

    decision = find_next_actionable_step(
        pending_plan,
        profile=dataset_profile,
    )

    print("\n" + "=" * 40)
    print("[PLAN CONTROLLER DECISION]")
    print(f"kind = {decision.kind}")
    print(f"reason = {decision.reason}")
    print(f"step_id = {decision.step.get('step_id') if isinstance(decision.step, dict) else None}")
    print(f"tool_name = {decision.step.get('tool_name') if isinstance(decision.step, dict) else None}")
    print("=" * 40 + "\n")

    if decision.kind == "complete":
        return _make_completed_response(
            state=state,
            pending_plan=pending_plan,
            reason=decision.reason or "plan_complete",
        )

    if decision.kind == "ask_user":
        return _make_pause_response(
            state=state,
            pending_plan=pending_plan,
            decision=decision,
            reason_code="waiting_for_user_choices",
        )

    if decision.kind == "blocked":
        return _make_pause_response(
            state=state,
            pending_plan=pending_plan,
            decision=decision,
            reason_code="blocked_no_actionable_step",
        )

    if decision.kind == "request_review":
        print("\n" + "=" * 40)
        print("[EXECUTE PENDING PLAN -> REVIEW]")
        print(f"plan_id = {pending_plan.get('plan_id')}")
        print(f"step_id = {decision.step.get('step_id') if decision.step else None}")
        print(f"tool_name = {get_action_tool_name(decision.action)}")
        print(f"arguments = {get_action_arguments(decision.action)}")
        print("readiness_status = needs_review")
        print("=" * 40 + "\n")
        return _make_review_response(
            state=state,
            pending_plan=pending_plan,
            decision=decision,
        )

    if decision.kind != "execute" or decision.action is None or decision.step is None:
        return _make_pause_response(
            state=state,
            pending_plan=pending_plan,
            decision=decision,
            reason_code="blocked_invalid_plan_controller_decision",
        )

    action = decision.action
    next_step = decision.step
    readiness = decision.readiness

    updated_plan = mark_plan_step_started(
        pending_plan,
        step_id=next_step["step_id"],
        action_id=get_action_id(action),
    )

    print("\n" + "=" * 40)
    print("[EXECUTE PENDING PLAN]")
    print(f"plan_id = {pending_plan.get('plan_id')}")
    print(f"step_id = {next_step.get('step_id')}")
    print(f"tool_name = {get_action_tool_name(action)}")
    print(f"arguments = {get_action_arguments(action)}")
    print(f"readiness_status = {readiness.status if readiness else 'unknown'}")
    print("=" * 40 + "\n")

    return {
        "pending_plan": updated_plan,
        "plan_status": updated_plan.get("status"),
        "current_plan_step_id": next_step["step_id"],
        "plan_execution_status": "started_step",

        # Important for S4:
        # This action came from a pending plan, not a direct user tool request.
        "action_origin": "pending_plan",

        # Existing verify -> execute path.
        "current_action": action_to_state_dict(action),
        "current_execution": None,
        "current_verification": None,
        "human_review_required": False,
        "pending_action": None,
    }
