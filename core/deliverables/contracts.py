from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DeliverableGateContract(BaseModel):
    """
    Normalized backend contract for final-answer deliverable gating.

    This is not a UI schema.
    It tells DeliverableGate what evidence must exist before a final answer
    is allowed.
    """
    required_tools: List[str] = Field(default_factory=list)
    required_artifacts: List[str] = Field(default_factory=list)
    required_deliverables: List[str] = Field(default_factory=list)

    success_criteria: List[str] = Field(default_factory=list)
    deliverable_requirements: Dict[str, Dict[str, List[str]]] = Field(
        default_factory=dict,
    )

    allow_partial: bool = False

    metadata: Dict[str, Any] = Field(default_factory=dict)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [v for v in value if v is not None]

    if isinstance(value, tuple):
        return [v for v in value if v is not None]

    return []


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    return {}


def _as_string_list(value: Any) -> List[str]:
    return [str(item) for item in _as_list(value) if item is not None]


def _normalize_required_deliverables(value: Any) -> List[str]:
    deliverables = []

    for item in _as_list(value):
        if isinstance(item, str):
            deliverables.append(item)
            continue

        item_dict = _as_dict(item)
        deliverable_id = item_dict.get("deliverable_id")

        if deliverable_id:
            deliverables.append(str(deliverable_id))

    return deliverables


def _requirements_from_required_deliverables(
    value: Any,
) -> Dict[str, Dict[str, List[str]]]:
    requirements = {}

    for item in _as_list(value):
        item_dict = _as_dict(item)
        deliverable_id = item_dict.get("deliverable_id")

        if not deliverable_id:
            continue

        requirements[str(deliverable_id)] = {
            "required_tools": _as_string_list(item_dict.get("satisfied_by")),
            "required_evidence": _as_string_list(item_dict.get("required_evidence")),
        }

    return requirements


def _tools_from_required_deliverables(value: Any) -> List[str]:
    tools = []

    for item in _as_list(value):
        item_dict = _as_dict(item)

        for tool_name in _as_string_list(item_dict.get("satisfied_by")):
            if tool_name not in tools:
                tools.append(tool_name)

    return tools


def _evidence_from_required_deliverables(value: Any) -> List[str]:
    evidence = []

    for item in _as_list(value):
        item_dict = _as_dict(item)

        for evidence_key in _as_string_list(item_dict.get("required_evidence")):
            if evidence_key not in evidence:
                evidence.append(evidence_key)

    return evidence


def normalize_task_contract(value: Any) -> DeliverableGateContract:
    """
    Convert legacy/free-form task_contract values into a normalized gate contract.

    Supported legacy keys:
    - required_tools
    - required_artifacts
    - required_deliverables
    - success_criteria
    - allow_partial
    """
    data = _as_dict(value)

    if not data:
        return DeliverableGateContract()

    raw_required_deliverables = data.get("required_deliverables")
    required_deliverables = _normalize_required_deliverables(raw_required_deliverables)

    required_tools = _as_string_list(data.get("required_tools"))
    for tool_name in _tools_from_required_deliverables(raw_required_deliverables):
        if tool_name not in required_tools:
            required_tools.append(tool_name)

    success_criteria = _as_string_list(data.get("success_criteria"))
    for evidence_key in _evidence_from_required_deliverables(raw_required_deliverables):
        criterion = f"evidence:{evidence_key}"
        if criterion not in success_criteria:
            success_criteria.append(criterion)

    return DeliverableGateContract(
        required_tools=required_tools,
        required_artifacts=_as_string_list(data.get("required_artifacts")),
        required_deliverables=required_deliverables,
        success_criteria=success_criteria,
        deliverable_requirements=_requirements_from_required_deliverables(
            raw_required_deliverables,
        ),
        allow_partial=bool(data.get("allow_partial", False)),
        metadata={
            k: v
            for k, v in data.items()
            if k not in {
                "required_tools",
                "required_artifacts",
                "required_deliverables",
                "success_criteria",
                "allow_partial",
            }
        },
    )
