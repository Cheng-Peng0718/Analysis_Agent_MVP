from __future__ import annotations

from enum import Enum

from core.services.interaction_router import (
    decide_interaction_intent,
    legacy_interaction_intent_from_decision,
)


class InteractionIntent(str, Enum):
    ADVISORY = "advisory"
    PLAN_ONLY = "plan_only"
    EXECUTE_PLAN = "execute_plan"
    DIRECT_TOOL = "direct_tool"
    UNKNOWN = "unknown"


def classify_interaction_intent(user_message: str) -> InteractionIntent:
    """
    Compatibility adapter for legacy routes.

    Natural-language interpretation lives in core.services.interaction_router
    and returns IntentDecision/TaskSpec. This wrapper only preserves the old
    enum contract for code that still routes by interaction_intent.
    """
    decision = decide_interaction_intent(user_message)
    return InteractionIntent(legacy_interaction_intent_from_decision(decision))
