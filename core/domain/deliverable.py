from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RequiredDeliverable(BaseModel):
    deliverable_id: str = Field(..., description="Stable id for the deliverable.")
    description: str = Field(..., description="Human-readable deliverable description.")
    satisfied_by: List[str] = Field(
        default_factory=list,
        description="Tool names that can satisfy this deliverable.",
    )
    required_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence keys required to consider this deliverable complete.",
    )
    status: Literal["pending", "satisfied", "missing", "blocked"] = "pending"


class TaskConstraint(BaseModel):
    constraint_id: str
    description: str
    type: Literal["data_mutation", "method", "reporting", "safety", "other"] = "other"


class TaskContract(BaseModel):
    contract_id: str = Field(..., description="Unique contract id.")
    user_goal: str = Field(..., description="What the user wants to accomplish.")
    required_deliverables: List[RequiredDeliverable] = Field(default_factory=list)
    constraints: List[TaskConstraint] = Field(default_factory=list)
    created_by: str = "supervisor"
    status: Literal["active", "satisfied", "blocked"] = "active"


class DeliverableCheckResult(BaseModel):
    status: Literal["ok", "needs_more_work", "missing", "blocked"] = "ok"
    satisfied: List[Dict[str, Any]] = Field(default_factory=list)
    missing: List[Dict[str, Any]] = Field(default_factory=list)
    blocked: List[Dict[str, Any]] = Field(default_factory=list)
    message: Optional[str] = None
