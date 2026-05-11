from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.schema import ActionProposal
from core.services.task_contracts import task_contract_to_state_dict


def normalize_action_payload(action: Any) -> dict | None:
    """
    Normalize any supported action representation into a plain dict payload.

    This is for state/checkpoint/UI-safe storage. It does not return a
    Pydantic object.
    """
    if action is None:
        return None

    if isinstance(action, ActionProposal):
        payload = action.model_dump()
    elif isinstance(action, Mapping):
        payload = dict(action)
    else:
        payload = {
            "action_id": getattr(action, "action_id", None),
            "action_type": getattr(action, "action_type", None),
            "tool_name": getattr(action, "tool_name", None),
            "arguments": getattr(action, "arguments", None),
            "reasoning_summary": getattr(action, "reasoning_summary", None),
            "task_contract": getattr(action, "task_contract", None),
            "contract_update": getattr(action, "contract_update", None),
        }

    if not payload.get("reasoning_summary"):
        payload["reasoning_summary"] = (
            payload.get("summary")
            or payload.get("message")
            or "No reasoning summary provided."
        )

    if not payload.get("arguments"):
        payload["arguments"] = {}

    if payload.get("task_contract"):
        payload["task_contract"] = task_contract_to_state_dict(
            payload.get("task_contract"),
        )

    return payload


def action_to_state_dict(action: Any) -> dict | None:
    """
    Convert an action to a JSON-safe dict for state storage.

    task_contract is intentionally not stored inside current_action.
    It should be extracted by supervisor_node and stored separately as
    state["task_contract"].
    """
    payload = normalize_action_payload(action)

    if payload is None:
        return None

    payload = dict(payload)
    payload.pop("task_contract", None)

    cleaned = ActionProposal.model_validate(payload).model_dump()

    cleaned.pop("task_contract", None)

    return cleaned


def action_from_state(action: Any) -> ActionProposal | None:
    """
    Rehydrate a state/checkpoint action payload into ActionProposal for runtime.

    Runtime graph nodes may still expect a formal action contract while the
    state remains JSON-safe.
    """
    payload = normalize_action_payload(action)

    if payload is None:
        return None

    return ActionProposal.model_validate(payload)
