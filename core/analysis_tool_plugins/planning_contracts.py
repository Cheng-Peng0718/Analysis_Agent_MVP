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

    # Generic cross-step dependency contract. If a plugin declares
    # wait_for_step_tags=["data_cleaning"], the plan scheduler may reorder and
    # pause that step until any pending step carrying planning_tags containing
    # "data_cleaning" has completed. This avoids global tool-name checks such
    # as "clean_data before regression".
    wait_for_step_tags: List[str] = field(default_factory=list)

    # None means "not specified locally"; ToolManifest normalizes it to 100.
    plan_order: Optional[int] = None