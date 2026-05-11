from __future__ import annotations

from typing import Any, Iterable, List, Set

from core.analysis_tool_plugins import get_plugin
from core.dataset_intelligence.schemas import DatasetProfileV2


def _get_field(value: Any, field_name: str, default=None):
    if value is None:
        return default

    if isinstance(value, dict):
        return value.get(field_name, default)

    return getattr(value, field_name, default)


def _set_field(value: Any, field_name: str, new_value: Any) -> None:
    if isinstance(value, dict):
        value[field_name] = new_value
    else:
        setattr(value, field_name, new_value)


def _step_tool_name(step: Any) -> str | None:
    return _get_field(step, "tool_name")


def _step_execution_status(step: Any) -> str | None:
    return _get_field(step, "execution_status")


def _plugin_for_step(step: Any):
    tool_name = _step_tool_name(step)

    if not tool_name:
        return None

    return get_plugin(tool_name)


def _planning_metadata(plugin: Any):
    return getattr(plugin, "planning_metadata", None)


def _step_tags(step: Any) -> Set[str]:
    plugin = _plugin_for_step(step)
    metadata = _planning_metadata(plugin)

    if metadata is None:
        return set()

    return set(getattr(metadata, "planning_tags", []) or [])


def _wait_for_step_tags(step: Any) -> Set[str]:
    plugin = _plugin_for_step(step)
    metadata = _planning_metadata(plugin)

    if metadata is None:
        return set()

    return set(getattr(metadata, "wait_for_step_tags", []) or [])


def _is_completed(step: Any) -> bool:
    return _step_execution_status(step) == "completed"


def _step_is_prerequisite_for(
    candidate_prerequisite: Any,
    dependent_step: Any,
) -> bool:
    required_tags = _wait_for_step_tags(dependent_step)

    if not required_tags:
        return False

    return bool(_step_tags(candidate_prerequisite) & required_tags)


def _has_pending_prerequisite_step(
    *,
    step: Any,
    steps: Iterable[Any],
) -> bool:
    return any(
        _step_is_prerequisite_for(candidate, step)
        and not _is_completed(candidate)
        for candidate in steps
    )


def _first_dependent_index_for_prerequisite(
    *,
    prerequisite_step: Any,
    steps: List[Any],
) -> int | None:
    for idx, candidate in enumerate(steps):
        if candidate is prerequisite_step:
            continue

        if _step_is_prerequisite_for(prerequisite_step, candidate):
            return idx

    return None


def reorder_clean_data_before_modeling(plan: Any, profile: DatasetProfileV2) -> Any:
    """
    Backward-compatible name, contract-driven behavior.

    This no longer knows about clean_data, regression, or ANOVA tool names.
    It reorders any step whose planning_tags satisfy another step's
    wait_for_step_tags so prerequisites appear before dependent analyses.
    """
    steps = list(getattr(plan, "steps", []) or [])

    if len(steps) < 2:
        return plan

    reordered = list(steps)
    changed = True

    while changed:
        changed = False

        for idx, step in list(enumerate(reordered)):
            dependent_idx = _first_dependent_index_for_prerequisite(
                prerequisite_step=step,
                steps=reordered,
            )

            if dependent_idx is None or idx < dependent_idx:
                continue

            prereq = reordered.pop(idx)
            reordered.insert(dependent_idx, prereq)
            changed = True
            break

    _set_field(plan, "steps", reordered)
    return plan


def modeling_blocked_by_pending_cleaning(
    *,
    step: Any,
    pending_plan: dict,
    profile: DatasetProfileV2,
) -> bool:
    """
    Backward-compatible name, contract-driven behavior.

    The runtime scheduler blocks a step only when that step's plugin declares
    wait_for_step_tags and an unfinished step in the same plan carries one of
    those tags. No concrete tool names are inspected here.
    """
    steps = pending_plan.get("steps", []) or []

    return _has_pending_prerequisite_step(
        step=step,
        steps=steps,
    )
