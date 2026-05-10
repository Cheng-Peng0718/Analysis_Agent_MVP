from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.domain.deliverable import TaskContract


def _as_dict(value: Any) -> dict:
    if value is None:
        return {}

    if isinstance(value, Mapping):
        return dict(value)

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    return {}


def _looks_like_canonical_task_contract(data: dict) -> bool:
    if "contract_id" in data or "user_goal" in data:
        return True

    deliverables = data.get("required_deliverables", []) or []

    return any(
        isinstance(item, Mapping) and "deliverable_id" in item
        for item in deliverables
    )


def task_contract_to_state_dict(contract: Any) -> dict:
    """
    Normalize a supervisor task_contract for graph state storage.

    Canonical TaskContract payloads are validated against the domain model
    before storage. Legacy/free-form gate contracts are preserved for backward
    compatibility during migration.
    """
    data = _as_dict(contract)

    if not data:
        return {}

    if _looks_like_canonical_task_contract(data):
        return TaskContract.model_validate(data).model_dump()

    return data
