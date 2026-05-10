from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlanningMetadata:
    supported_goal_types: List[str] = field(default_factory=list)
    planning_tags: List[str] = field(default_factory=list)
    default_plan_purpose: str = ""
    expected_deliverables: List[str] = field(default_factory=list)

    argument_template: Dict[str, Any] = field(default_factory=dict)
    task_argument_bindings: List[Dict[str, Any]] = field(default_factory=list)
    required_planning_choices: List[str] = field(default_factory=list)

    not_recommended_for_goal_types: List[str] = field(default_factory=list)

    # None means "not specified locally; use central fallback if available."
    plan_order: Optional[int] = None