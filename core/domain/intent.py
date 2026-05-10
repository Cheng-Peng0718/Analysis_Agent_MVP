from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from core.domain.task import TaskSpec


class IntentDecision(BaseModel):
    intent: Literal[
        "advisory",
        "plan_analysis",
        "direct_analysis",
        "execute_plan",
        "modify_data",
        "clarification",
        "unknown",
    ]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    task_spec: Optional[TaskSpec] = None
    should_execute: bool = False
