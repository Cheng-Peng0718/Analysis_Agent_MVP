from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.action_access import (
    get_action_arguments,
    get_action_id,
    get_action_tool_name,
)
from core.action_codec import action_to_state_dict
from core.analysis_tool_plugins import get_plugin
from core.planning.readiness import (
    PlanStepReadiness,
    assess_plan_step_readiness,
)
from core.verification_access import get_verification_details, set_verification_fields
from core.verification_codec import verification_to_state_dict
from core.workflow.runtime_utils import get_action_hash

TERMINAL_EXECUTION_STATUSES = {
    "running",
    "completed",
    "failed",
    "skipped",
    "blocked",
    "awaiting_review",
}

DONE_EXECUTION_STATUSES = {
    "completed",
    "skipped",
}


@dataclass
class NextPlanAction:
    """Controller-level decision for the next pending-plan transition.

    A pending plan does not only need the next executable step. It may need to
    ask for arguments, create a review request, execute a low-risk tool, report
    a validation/dependency blocker, or mark itself complete. Keeping this as a
    single decision object prevents the router, queue, verifier, and review
    nodes from each owning only a fragment of the plan state machine.
    """

    kind: str
    step: Optional[Dict[str, Any]] = None
    readiness: Optional[PlanStepReadiness] = None
    reason: str = ""
    action: Optional[Any] = None
    verification: Optional[Any] = None
    prerequisite_step: Optional[Dict[str, Any]] = None

    def step_id(self) -> Optional[str]:
        if not isinstance(self.step, dict):
            return None
        return self.step.get("step_id")

    def tool_name(self) -> Optional[str]:
        if not isinstance(self.step, dict):
            return None
        return self.step.get("tool_name")


def _get_field(value: Any, field_name: str, default=None):
    if value is None:
        return default

    if isinstance(value, dict):
        return value.get(field_name, default)

    return getattr(value, field_name, default)


def _is_step_done(step: Dict[str, Any]) -> bool:
    return step.get("execution_status") in DONE_EXECUTION_STATUSES


def _is_step_failed(step: Dict[str, Any]) -> bool:
    return step.get("execution_status") == "failed"


def _is_step_blocked(step: Dict[str, Any]) -> bool:
    return (
        step.get("execution_status") == "blocked"
        or step.get("status") == "blocked"
    )


def _is_step_unfinished(step: Dict[str, Any]) -> bool:
    return not _is_step_done(step)


def _is_step_ready_for_future_execution(step: Dict[str, Any]) -> bool:
    if step.get("execution_status") in TERMINAL_EXECUTION_STATUSES:
        return False

    return step.get("status") == "ready" and step.get("execution_ready") is True


def _readiness_blocked_by_execution_status(
    step: Dict[str, Any],
) -> PlanStepReadiness:
    execution_status = step.get("execution_status")
    step_id = step.get("step_id") or "unknown_step"

    return PlanStepReadiness(
        status="not_executable",
        executable=False,
        reason=(
            f"Plan step {step_id} already has execution_status="
            f"{execution_status}; it will not be selected again."
        ),
        action=None,
        missing_user_choices=[],
    )


def _planning_metadata_for_step(step: Any):
    tool_name = _get_field(step, "tool_name")

    if not tool_name:
        return None

    plugin = get_plugin(tool_name)

    if plugin is None:
        return None

    return getattr(plugin, "planning_metadata", None)


def _step_tags(step: Any) -> set[str]:
    metadata = _planning_metadata_for_step(step)

    if metadata is None:
        return set()

    return set(getattr(metadata, "planning_tags", []) or [])


def _wait_for_step_tags(step: Any) -> set[str]:
    metadata = _planning_metadata_for_step(step)

    if metadata is None:
        return set()

    return set(getattr(metadata, "wait_for_step_tags", []) or [])


def _step_satisfies_dependency(candidate: Any, dependent: Any) -> bool:
    required_tags = _wait_for_step_tags(dependent)

    if not required_tags:
        return False

    return bool(_step_tags(candidate) & required_tags)


def _pending_prerequisites_for_step(
    *,
    step: Dict[str, Any],
    steps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        candidate
        for candidate in steps
        if candidate is not step
        and _step_satisfies_dependency(candidate, step)
        and not _is_step_done(candidate)
    ]


def _make_verification_payload_for_review(action: Any, verification: Any) -> Any:
    tool_name = get_action_tool_name(action)
    arguments = get_action_arguments(action)
    details = dict(get_verification_details(verification) or {})
    details["action_hash"] = get_action_hash(tool_name, arguments)
    verification = set_verification_fields(verification, details=details)
    return verification_to_state_dict(verification)


def _plan_step_title(step: Optional[Dict[str, Any]]) -> str:
    if not isinstance(step, dict):
        return "unknown step"

    return step.get("title") or step.get("step_id") or "unknown step"


def find_next_actionable_step(
    pending_plan: Dict[str, Any],
    profile: Any = None,
) -> NextPlanAction:
    """Return the next plan controller transition.

    This is intentionally broader than `find_next_executable_step`:
    - ask_user: the next unfinished step is missing choices/arguments
    - request_review: the next step is valid but high-risk/mutating
    - execute: the next step is valid and low-risk
    - blocked: validation/dependency state prevents progress
    - complete: there are no unfinished steps
    """
    steps = [step for step in (pending_plan.get("steps", []) or []) if isinstance(step, dict)]

    if not steps:
        return NextPlanAction(
            kind="complete",
            reason="The plan has no remaining steps.",
        )

    first_actionable_blocker: Optional[NextPlanAction] = None
    first_terminal_blocker: Optional[NextPlanAction] = None

    for step in steps:
        execution_status = step.get("execution_status")

        if execution_status in TERMINAL_EXECUTION_STATUSES:
            if first_terminal_blocker is None:
                blocker = _readiness_blocked_by_execution_status(step)
                first_terminal_blocker = NextPlanAction(
                    kind="blocked",
                    step=step,
                    readiness=blocker,
                    reason=blocker.reason,
                )
            continue

        prerequisites = _pending_prerequisites_for_step(step=step, steps=steps)
        if prerequisites:
            prereq = prerequisites[0]
            prereq_readiness = assess_plan_step_readiness(
                step=prereq,
                profile=profile,
            )

            if prereq_readiness.executable:
                if prereq_readiness.status == "needs_review":
                    return NextPlanAction(
                        kind="request_review",
                        step=prereq,
                        readiness=prereq_readiness,
                        reason=prereq_readiness.reason,
                        action=prereq_readiness.action,
                    )

                return NextPlanAction(
                    kind="execute",
                    step=prereq,
                    readiness=prereq_readiness,
                    reason=prereq_readiness.reason,
                    action=prereq_readiness.action,
                )

            if prereq_readiness.status in {"needs_user_choice", "not_ready"}:
                return NextPlanAction(
                    kind="ask_user",
                    step=prereq,
                    readiness=prereq_readiness,
                    reason=(
                        "A prerequisite step must be resolved before the dependent "
                        f"step `{_plan_step_title(step)}` can run. "
                        f"{prereq_readiness.reason}"
                    ),
                    prerequisite_step=prereq,
                )

            return NextPlanAction(
                kind="blocked",
                step=step,
                readiness=prereq_readiness,
                reason=(
                    "A prerequisite step blocks this step and is not currently actionable. "
                    f"Prerequisite: `{_plan_step_title(prereq)}`. "
                    f"Reason: {prereq_readiness.reason}"
                ),
                prerequisite_step=prereq,
            )

        assessment = assess_plan_step_readiness(
            step=step,
            profile=profile,
        )

        if assessment.executable:
            if assessment.status == "needs_review":
                return NextPlanAction(
                    kind="request_review",
                    step=step,
                    readiness=assessment,
                    reason=assessment.reason,
                    action=assessment.action,
                )

            return NextPlanAction(
                kind="execute",
                step=step,
                readiness=assessment,
                reason=assessment.reason,
                action=assessment.action,
            )

        if assessment.status in {"needs_user_choice", "not_ready"}:
            return NextPlanAction(
                kind="ask_user",
                step=step,
                readiness=assessment,
                reason=assessment.reason,
            )

        if first_actionable_blocker is None:
            first_actionable_blocker = NextPlanAction(
                kind="blocked",
                step=step,
                readiness=assessment,
                reason=assessment.reason,
            )

    unfinished_steps = [step for step in steps if _is_step_unfinished(step)]

    if not unfinished_steps:
        return NextPlanAction(
            kind="complete",
            reason="All plan steps have completed or been skipped.",
        )

    return first_actionable_blocker or first_terminal_blocker or NextPlanAction(
        kind="blocked",
        reason="The plan has unfinished steps, but none are currently actionable.",
    )


def find_next_executable_step(
    pending_plan: Dict[str, Any],
    profile: Any = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[PlanStepReadiness]]:
    """Return the next executable step using the legacy skip-blockers behavior.

    New controller code should use `find_next_actionable_step`. This wrapper is
    kept for older tests/callers that specifically want to skip over non-ready
    steps and find a runnable action.
    """
    steps = [step for step in (pending_plan.get("steps", []) or []) if isinstance(step, dict)]
    first_actionable_blocker: Optional[PlanStepReadiness] = None
    first_terminal_blocker: Optional[PlanStepReadiness] = None

    for step in steps:
        if step.get("execution_status") in TERMINAL_EXECUTION_STATUSES:
            if first_terminal_blocker is None:
                first_terminal_blocker = _readiness_blocked_by_execution_status(step)
            continue

        assessment = assess_plan_step_readiness(step=step, profile=profile)

        if assessment.executable:
            return step, assessment

        if first_actionable_blocker is None:
            first_actionable_blocker = assessment

    return None, first_actionable_blocker or first_terminal_blocker


def _set_step_execution_status(
    pending_plan: Dict[str, Any],
    step_id: str,
    *,
    execution_status: str,
    action_id: str | None = None,
    verification_status: str | None = None,
    last_execution_id: str | None = None,
    last_execution_message: str | None = None,
) -> Dict[str, Any]:
    plan = dict(pending_plan)
    steps = []

    for step in plan.get("steps", []) or []:
        step = dict(step)

        if step.get("step_id") == step_id:
            step["execution_status"] = execution_status

            if action_id is not None:
                step["action_id"] = action_id

            if verification_status is not None:
                step["verification_status"] = verification_status

            if last_execution_id is not None:
                step["last_execution_id"] = last_execution_id

            if last_execution_message is not None:
                step["last_execution_message"] = last_execution_message

        steps.append(step)

    plan["steps"] = steps
    return plan


def mark_plan_step_started(
    pending_plan: Dict[str, Any],
    step_id: str,
    action_id: str,
) -> Dict[str, Any]:
    plan = _set_step_execution_status(
        pending_plan,
        step_id,
        execution_status="running",
        action_id=action_id,
    )
    plan["status"] = "executing"
    return plan


def mark_plan_step_awaiting_review(
    pending_plan: Dict[str, Any],
    step_id: str,
    action_id: str,
) -> Dict[str, Any]:
    plan = _set_step_execution_status(
        pending_plan,
        step_id,
        execution_status="awaiting_review",
        action_id=action_id,
        verification_status="needs_review",
    )
    plan["status"] = "awaiting_review"
    return plan


def mark_plan_step_after_execution(
    pending_plan: Dict[str, Any],
    step_id: str,
    *,
    success: bool,
    execution_id: str | None = None,
    message: str | None = None,
) -> Dict[str, Any]:
    plan = _set_step_execution_status(
        pending_plan,
        step_id,
        execution_status="completed" if success else "failed",
        last_execution_id=execution_id,
        last_execution_message=message,
    )
    steps = plan.get("steps", []) or []

    remaining_ready = [
        step
        for step in steps
        if _is_step_ready_for_future_execution(step)
    ]

    unfinished_steps = [
        step
        for step in steps
        if _is_step_unfinished(step)
    ]

    failed_steps = [
        step
        for step in steps
        if _is_step_failed(step)
    ]

    blocked_steps = [
        step
        for step in steps
        if _is_step_blocked(step)
    ]

    awaiting_review_steps = [
        step
        for step in steps
        if step.get("execution_status") == "awaiting_review"
    ]

    if failed_steps:
        plan["status"] = "partially_failed"
    elif not unfinished_steps:
        plan["status"] = "completed"
    elif awaiting_review_steps:
        plan["status"] = "awaiting_review"
    elif remaining_ready:
        plan["status"] = "partially_executed"
    elif blocked_steps:
        plan["status"] = "blocked"
    else:
        # No executable ready steps remain, but the plan still has unfinished
        # steps. This is not completed; the runner should pause and ask for
        # missing choices / clarification.
        plan["status"] = "partially_executed"

    return plan


def make_review_state_update(
    *,
    pending_plan: Dict[str, Any],
    step: Dict[str, Any],
    action: Any,
    verification: Any,
) -> Dict[str, Any]:
    verification_payload = _make_verification_payload_for_review(
        action=action,
        verification=verification,
    )
    action_payload = action_to_state_dict(action)
    updated_plan = mark_plan_step_awaiting_review(
        pending_plan,
        step_id=step["step_id"],
        action_id=get_action_id(action),
    )

    return {
        "pending_plan": updated_plan,
        "plan_status": updated_plan.get("status"),
        "current_plan_step_id": step["step_id"],
        "plan_execution_status": "awaiting_review",
        "action_origin": "pending_plan",
        "current_action": action_payload,
        "current_execution": None,
        "current_verification": verification_payload,
        "human_review_required": True,
        "pending_action": action_payload,
    }
