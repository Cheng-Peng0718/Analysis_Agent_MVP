from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from core.analysis_tool_plugins.applicability import ApplicabilityResult
from core.analysis_tool_plugins.arguments import ArgumentSchema
from core.analysis_tool_plugins.display import DisplayConfig
from core.analysis_tool_plugins.policy_types import (
    PlanningPolicy,
    RepairPolicy,
    VersioningPolicy,
)
from core.analysis_tool_plugins.roles import VariableRoleSpec
from core.analysis_tool_plugins.types import ExecuteFn, ExtractorFn, GuardrailFn


@dataclass
class AnalysisToolPlugin:
    tool_name: str
    display_name: str

    execute: Optional[ExecuteFn] = None
    extractor: Optional[ExtractorFn] = None

    requires_confirmation: bool = False
    argument_schema: ArgumentSchema = field(default_factory=ArgumentSchema)

    guardrail_evaluators: List[GuardrailFn] = field(default_factory=list)
    display_config: DisplayConfig = field(default_factory=DisplayConfig)

    method_family: str = "general"
    variable_roles: List[VariableRoleSpec] = field(default_factory=list)
    applicability_checker: Optional[Callable[..., ApplicabilityResult]] = None
    plan_step_builder: Optional[Callable[..., dict]] = None

    mutates_data: bool = False
    versioning_policy: VersioningPolicy = field(default_factory=VersioningPolicy)
    repair_policy: RepairPolicy = field(default_factory=RepairPolicy)
    planning_policy: PlanningPolicy = field(default_factory=PlanningPolicy)

    def run(self, context) -> dict:
        if self.execute is None:
            return {
                "status": "failed",
                "error_code": "MISSING_PLUGIN_EXECUTE",
                "message": f"Plugin `{self.tool_name}` does not define an execute function.",
                "recoverable": False,
                "details": {},
                "artifacts": [],
            }

        return self.execute(context)
