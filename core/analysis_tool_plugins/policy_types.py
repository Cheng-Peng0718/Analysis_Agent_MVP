from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class VersioningPolicy:
    mutates_data: bool = False
    must_create_child_version: bool = False
    allowed_to_call_save_df: bool = False


@dataclass
class RepairPolicy:
    max_attempts: int = 2
    repairable_error_codes: List[str] = field(default_factory=list)
    non_repairable_error_codes: List[str] = field(default_factory=list)
    allow_argument_repair: bool = True
    allow_method_fallback: bool = True
    requires_user_for_missing_roles: bool = True


@dataclass
class PlanningPolicy:
    include_in_capability_map: bool = True
    ready_without_user_variables: bool = False
    allow_default_arguments: bool = False
    planning_description: str = ""
    requires_variable_contract: bool = True
    required_user_choices: List[str] = field(default_factory=list)
