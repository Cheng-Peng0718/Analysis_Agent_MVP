from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    goal_type: str = Field(..., description="High-level user goal, not a tool name.")
    user_goal: str = ""
    source_user_request: str = ""

    target_variables: List[str] = Field(default_factory=list)
    predictor_variables: List[str] = Field(default_factory=list)
    grouping_variables: List[str] = Field(default_factory=list)
    requested_methods: List[str] = Field(default_factory=list)

    constraints: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
