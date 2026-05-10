from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from core.domain.task import TaskSpec


PlanStepStatus = Literal[
    "needs_user_choice",
    "ready",
    "blocked",
    "not_applicable",
    "not_recommended",
    "completed",
    "failed",
]

PlanStatus = Literal[
    "draft",
    "ready",
    "verified",
    "partially_ready",
    "needs_clarification",
    "blocked",
    "executing",
    "partially_executed",
    "completed",
    "partially_failed",
    "cancelled",
]


class PlanStep(BaseModel):
    step_id: str
    title: str

    purpose: str = ""
    goal: str = ""
    rationale: str = ""

    tool_name: Optional[str] = None
    method_family: str = "general"

    status: PlanStepStatus = "needs_user_choice"
    execution_ready: bool = False

    variables: Dict[str, Any] = Field(default_factory=dict)
    arguments: Dict[str, Any] = Field(default_factory=dict)

    candidate_variables: Dict[str, List[str]] = Field(default_factory=dict)
    required_user_choices: List[str] = Field(default_factory=list)

    applicability_check: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    suggested_alternatives: List[str] = Field(default_factory=list)

    expected_deliverables: List[str] = Field(default_factory=list)

    requires_confirmation: bool = False
    mutates_data: bool = False


class PlanProposal(BaseModel):
    plan_id: str

    user_goal: str = ""
    user_request: str = ""
    task_spec: Optional[TaskSpec] = None
    data_version_id: str = ""

    mode: str = "plan_only"
    status: PlanStatus = "draft"

    summary: str = ""
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    steps: List[PlanStep] = Field(default_factory=list)
    blocked_or_not_recommended: List[PlanStep] = Field(default_factory=list)

    requires_user_confirmation_before_execution: bool = True
