from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ApplicabilityResult:
    status: str
    reason: str

    required_user_choices: List[str] = field(default_factory=list)
    candidate_variables: Dict[str, List[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    suggested_alternatives: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "required_user_choices": self.required_user_choices,
            "candidate_variables": self.candidate_variables,
            "warnings": self.warnings,
            "suggested_alternatives": self.suggested_alternatives,
        }
