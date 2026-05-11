from __future__ import annotations

import uuid
import importlib
from typing import Any, Dict, List, Optional

from core.action_access import (
    get_action_field,
    get_action_reasoning_summary,
    get_action_type,
)
from core.context_builder import build_context
from core.services.task_contracts import task_contract_to_state_dict
from core.workflow.profile_access import get_context_profile, get_dataset_profile_v2
from core.action_codec import action_to_state_dict
from core.schema import ActionProposal
from core.services.llm_planner import create_llm_plan_from_state
from core.planning.execution_queue import find_next_executable_step


def call_supervisor(context_pkg):
    """
    Legacy supervisor adapter retained for compatibility and tests only.

    The active dataset-aware path in supervisor_node no longer relies on this
    LLM prompt for tool selection. It is used only when the new planner inputs
    are unavailable, so old tests and transitional non-dataset flows keep a
    deterministic fallback.
    """
    legacy_module = importlib.import_module("agents.supervisor")
    return legacy_module.call_supervisor(context_pkg)


def _make_final_action(content: str) -> ActionProposal:
    return ActionProposal(
        action_id=f"act_{uuid.uuid4().hex[:8]}",
        action_type="final_answer",
        tool_name=None,
        arguments={"content": content},
        reasoning_summary=content,
    )


def _has_new_planner_inputs(state: dict) -> bool:
    return bool(state.get("dataset_profile_v2") and state.get("capability_map"))


def _format_step_choice_block(step: Dict[str, Any]) -> str:
    title = step.get("title") or step.get("tool_name") or step.get("step_id")
    missing = step.get("required_user_choices") or []
    candidates = step.get("candidate_variables") or {}
    warnings = step.get("warnings") or []

    lines: List[str] = []
    lines.append(f"Step: {title}")

    if missing:
        lines.append("Missing choices: " + ", ".join(str(x) for x in missing))

    useful_candidates = {
        key: value
        for key, value in candidates.items()
        if isinstance(value, list) and value
    }

    if useful_candidates:
        lines.append("Candidate variables:")
        for key, value in useful_candidates.items():
            preview = ", ".join(str(v) for v in value[:8])
            if len(value) > 8:
                preview += ", ..."
            lines.append(f"- {key}: {preview}")

    if warnings:
        lines.append("Warnings:")
        for warning in warnings[:5]:
            lines.append(f"- {warning}")

    return "\n".join(lines)


def _format_no_ready_step_response(plan: Dict[str, Any]) -> str:
    steps = plan.get("steps") or []
    blocked = plan.get("blocked_or_not_recommended") or []

    lines: List[str] = []
    lines.append("I understood the request, but I cannot execute it yet because the verified plan has no execution-ready step.")
    lines.append("")

    if steps:
        lines.append("What is missing:")
        for step in steps[:5]:
            lines.append(_format_step_choice_block(step))
            lines.append("")

    if blocked:
        lines.append("Blocked or not recommended steps:")
        for step in blocked[:5]:
            title = step.get("title") or step.get("tool_name") or step.get("step_id")
            warnings = step.get("warnings") or []
            lines.append(f"- {title}: " + ("; ".join(warnings) if warnings else step.get("status", "blocked")))

    lines.append("You can reply in chat with the missing variables or choices; no UI buttons are required.")

    return "\n".join(line for line in lines if line is not None)


def _planner_direct_action_updates(state: dict) -> Dict[str, Any]:
    """
    New active supervisor path.

    For direct analysis / data modification requests, use the LLM planner and
    plugin contracts to produce a verified plan, then convert the first ready
    PlanStep into an ActionProposal. The old agents.supervisor prompt no longer
    chooses tools on this path.
    """
    intent = state.get("interaction_intent")

    if intent not in {"direct_tool", "unknown"}:
        content = (
            "I need a more specific analysis request before executing a tool. "
            "You can ask for a direct analysis, or ask me to make a plan first."
        )
        return {
            "current_action": action_to_state_dict(_make_final_action(content)),
            "current_execution": None,
            "current_verification": None,
            "action_origin": "direct_tool",
        }

    try:
        verified_plan = create_llm_plan_from_state(state)
    except Exception as exc:
        content = (
            "I could not create a verified tool action from this request.\n\n"
            f"Planner error: {type(exc).__name__}: {exc}"
        )
        return {
            "current_action": action_to_state_dict(_make_final_action(content)),
            "current_execution": None,
            "current_verification": None,
            "action_origin": "direct_tool",
        }

    plan_dict = verified_plan.model_dump()
    dataset_profile = get_dataset_profile_v2(state)
    next_step, readiness = find_next_executable_step(
        plan_dict,
        profile=dataset_profile,
    )

    if next_step is None or readiness is None or not readiness.executable:
        content = _format_no_ready_step_response(plan_dict)
        return {
            "pending_plan": plan_dict,
            "plan_status": plan_dict.get("status"),
            "plan_execution_status": "blocked_no_ready_steps",
            "current_action": action_to_state_dict(_make_final_action(content)),
            "current_execution": None,
            "current_verification": None,
            "action_origin": "direct_tool",
        }

    action = readiness.action
    tool_name = next_step.get("tool_name")

    print("\n" + "=" * 40)
    print("[DIRECT ACTION PLANNER]")
    print(f"plan_id = {plan_dict.get('plan_id')}")
    print(f"step_id = {next_step.get('step_id')}")
    print(f"tool_name = {tool_name}")
    print(f"arguments = {next_step.get('arguments')}")
    print("=" * 40 + "\n")

    return {
        "current_action": action_to_state_dict(action),
        "current_execution": None,
        "current_verification": None,
        "current_plan_step_id": None,
        "action_origin": "direct_tool",
        "plan_execution_status": None,
    }


def _legacy_supervisor_updates(state: dict) -> Dict[str, Any]:
    current_workspace = state.get("workspace_dir", "./")
    current_profile = get_context_profile(state)

    context_pkg = build_context(
        step=state.get("current_step", 1),
        max_steps=state.get("max_steps", 12),
        user_request=state.get("user_request", "Not provided"),
        profile=current_profile,
        observations=state.get("observations", []),
        workspace_dir=current_workspace,
        deliverable_check=state.get("deliverable_check"),
        data_versions=state.get("data_versions", []),
        active_data_version_id=state.get("active_data_version_id"),
        data_audit_log=state.get("data_audit_log", []),
        task_contract=state.get("task_contract"),
    )

    action = call_supervisor(context_pkg)
    updates = {"current_action": action_to_state_dict(action)}

    contract = get_action_field(action, "task_contract", None)
    contract_dict = task_contract_to_state_dict(contract)

    if contract_dict:
        print(
            f"[TASK CONTRACT DECLARED] "
            f"deliverables={len(contract_dict.get('required_deliverables', []))}"
        )

        updates["task_contract"] = contract_dict

    return updates


def supervisor_node(state: dict):
    if _has_new_planner_inputs(state):
        updates = _planner_direct_action_updates(state)
    else:
        updates = _legacy_supervisor_updates(state)

    action = updates.get("current_action")

    print("\n" + "=" * 40)
    print(f"[Supervisor decision]: action_type = {get_action_type(action)}")
    print(f"[Reasoning summary]: {get_action_reasoning_summary(action)}")
    print("=" * 40 + "\n")

    return updates
