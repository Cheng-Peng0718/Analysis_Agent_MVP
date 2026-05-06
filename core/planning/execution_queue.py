from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from core.schema import ActionProposal


def find_next_executable_step(pending_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return the next plan step that is safe to execute.

    A step is executable only if:
    - execution_ready is True
    - status is ready
    - tool_name exists
    - step is not already completed / failed / skipped
    """
    steps = pending_plan.get("steps", []) or []

    for step in steps:
        if step.get("status") != "ready":
            continue

        if step.get("execution_ready") is not True:
            continue

        if not step.get("tool_name"):
            continue

        if step.get("execution_status") in {"completed", "failed", "skipped"}:
            continue

        return step

    return None


def plan_step_to_action(step: Dict[str, Any]) -> ActionProposal:
    """
    Convert a verified PlanStep into an ActionProposal.

    This is the only allowed bridge from planning to execution.
    """
    tool_name = step["tool_name"]
    arguments = step.get("arguments") or {}

    return ActionProposal(
        action_id=f"act_{uuid.uuid4().hex[:8]}",
        action_type="tool_call",
        tool_name=tool_name,
        arguments=arguments,
        reasoning_summary=(
            f"Executing verified plan step {step.get('step_id')} "
            f"using tool {tool_name}."
        ),
    )


def mark_plan_step_started(
    pending_plan: Dict[str, Any],
    step_id: str,
    action_id: str,
) -> Dict[str, Any]:
    plan = dict(pending_plan)
    steps = []

    for step in plan.get("steps", []) or []:
        step = dict(step)

        if step.get("step_id") == step_id:
            step["execution_status"] = "running"
            step["action_id"] = action_id

        steps.append(step)

    plan["steps"] = steps
    plan["status"] = "executing"

    return plan


def mark_plan_step_after_execution(
    pending_plan: Dict[str, Any],
    step_id: str,
    *,
    success: bool,
    execution_id: str | None = None,
    message: str | None = None,
) -> Dict[str, Any]:
    plan = dict(pending_plan)
    steps = []

    for step in plan.get("steps", []) or []:
        step = dict(step)

        if step.get("step_id") == step_id:
            step["execution_status"] = "completed" if success else "failed"
            step["last_execution_id"] = execution_id
            step["last_execution_message"] = message

        steps.append(step)

    plan["steps"] = steps

    remaining_ready = [
        s for s in steps
        if s.get("status") == "ready"
        and s.get("execution_ready") is True
        and s.get("execution_status") not in {"completed", "failed", "skipped"}
    ]

    if remaining_ready:
        plan["status"] = "partially_executed"
    else:
        plan["status"] = "completed" if success else "partially_failed"

    return plan