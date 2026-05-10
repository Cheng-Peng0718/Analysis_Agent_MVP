from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VariableRoleSpec:
    role_name: str
    required: bool = True
    user_must_select: bool = True
    allowed_semantic_types: List[str] = field(default_factory=list)
    min_variables: int = 1
    max_variables: Optional[int] = 1
    allow_auto_select: bool = False
    description: str = ""
