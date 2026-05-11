from __future__ import annotations

from typing import Any, List

from core.analysis_tool_plugins import get_plugin
from core.analysis_tool_plugins.applicability import ApplicabilityResult
from core.dataset_intelligence.schemas import DatasetProfileV2
from core.planning.schemas import PlanProposal, PlanStep
from core.planning.dependencies import reorder_clean_data_before_modeling

def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _column_exists(profile: DatasetProfileV2, column_name: str) -> bool:
    return column_name in profile.columns


def _column_semantic_type(profile: DatasetProfileV2, column_name: str) -> str | None:
    col = profile.columns.get(column_name)
    if col is None:
        return None
    return col.semantic_type

def _first_non_empty_mapping_value(step: PlanStep, key: str):
    arguments = step.arguments or {}
    variables = step.variables or {}

    value = arguments.get(key)

    if value is None or value == "" or value == []:
        value = variables.get(key)

    return value


def _is_missing_choice(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, list):
        return len(value) == 0

    return False

def _unique_strings(values: List[Any]) -> List[str]:
    result: List[str] = []

    for value in values or []:
        if not isinstance(value, str):
            continue

        if value and value not in result:
            result.append(value)

    return result


def _get_policy_required_choices(plugin) -> List[str]:
    planning_policy = getattr(plugin, "planning_policy", None)

    if planning_policy is None:
        return []

    return list(getattr(planning_policy, "required_user_choices", []) or [])


def _policy_allows_ready_without_variables(plugin) -> bool:
    planning_policy = getattr(plugin, "planning_policy", None)

    if planning_policy is None:
        return False

    return bool(getattr(planning_policy, "ready_without_user_variables", False))


def _normalize_contract_value_between_variables_and_arguments(
    step: PlanStep,
    key: str,
) -> Any:
    """
    Keep step.variables and step.arguments synchronized for declared contract
    fields. The LLM is allowed to put a selected variable in either place; the
    verifier owns canonical normalization before readiness/execution.
    """
    step.variables = dict(step.variables or {})
    step.arguments = dict(step.arguments or {})

    value = _first_non_empty_mapping_value(step, key)

    if not _is_missing_choice(value):
        step.variables[key] = value
        step.arguments[key] = value

    return value

def _is_contract_readiness_warning(warning: Any) -> bool:
    """Return True for stale verifier/readiness warnings from earlier passes.

    Plan steps may enter verification with warnings created by the planner or by
    an earlier verifier implementation. Verification is authoritative for
    execution readiness, so these stale readiness warnings must be recomputed
    instead of blocking otherwise-valid contract-driven plugins.
    """
    if not isinstance(warning, str):
        return False

    lowered = warning.lower()
    return (
        "variable role contract" in lowered
        or "execution-ready from planning" in lowered
    )


def _verify_variable_roles(step: PlanStep, profile: DatasetProfileV2, plugin) -> PlanStep:
    """
    Generic variable-role verification.

    This does not contain method-specific rules.
    It only checks the plugin's declared VariableRoleSpec contract.
    """

    role_specs = getattr(plugin, "variable_roles", []) or []
    ready_without_user_variables = _policy_allows_ready_without_variables(plugin)
    policy_required_choices = _get_policy_required_choices(plugin)

    step.variables = dict(step.variables or {})
    step.arguments = dict(step.arguments or {})

    # Recompute verifier-owned readiness fields from the current plugin
    # contract. Do not let stale generic choices/warnings from a previous
    # planning or verification pass keep a default-ready tool blocked.
    step.required_user_choices = [
        choice
        for choice in _unique_strings(step.required_user_choices or [])
        if choice != "analysis variables"
    ]
    step.warnings = [
        warning
        for warning in list(step.warnings or [])
        if not _is_contract_readiness_warning(warning)
    ]

    unresolved_choices: List[str] = []

    for choice in policy_required_choices:
        value = _normalize_contract_value_between_variables_and_arguments(
            step,
            choice,
        )

        if _is_missing_choice(value):
            unresolved_choices.append(choice)

    if not role_specs:
        if ready_without_user_variables and not unresolved_choices:
            step.status = "ready"
            step.execution_ready = True
            step.required_user_choices = []
            step.warnings = []
            step.arguments = step.arguments or {}

            return step

        step.status = "needs_user_choice"
        step.execution_ready = False

        choices = unresolved_choices or ["analysis variables"]
        step.required_user_choices = _unique_strings(
            list(step.required_user_choices or []) + choices
        )

        if not ready_without_user_variables:
            step.warnings.append(
                "Plugin has no variable role contract and its planning_policy "
                "does not allow execution without user choices."
            )

        return step

    all_roles_ready = True

    for role in role_specs:
        raw_selected = _normalize_contract_value_between_variables_and_arguments(
            step,
            role.role_name,
        )
        selected = _as_list(raw_selected)

        if role.required and not selected:
            all_roles_ready = False

            if role.role_name not in step.required_user_choices:
                step.required_user_choices.append(role.role_name)

            continue

        if not selected:
            continue

        if role.max_variables is not None and len(selected) > role.max_variables:
            step.status = "blocked"
            step.execution_ready = False
            step.warnings.append(
                f"Role '{role.role_name}' allows at most {role.max_variables} variable(s)."
            )
            return step

        if len(selected) < role.min_variables:
            all_roles_ready = False

            if role.role_name not in step.required_user_choices:
                step.required_user_choices.append(role.role_name)

            continue

        for col_name in selected:
            if not isinstance(col_name, str):
                step.status = "blocked"
                step.execution_ready = False
                step.warnings.append(
                    f"Role '{role.role_name}' contains a non-string column reference."
                )
                return step

            if not _column_exists(profile, col_name):
                step.status = "blocked"
                step.execution_ready = False
                step.warnings.append(
                    f"Column '{col_name}' does not exist in the current dataset."
                )
                return step

            semantic_type = _column_semantic_type(profile, col_name)

            if role.allowed_semantic_types and semantic_type not in role.allowed_semantic_types:
                step.status = "not_applicable"
                step.execution_ready = False
                step.warnings.append(
                    f"Column '{col_name}' has semantic_type='{semantic_type}', "
                    f"but role '{role.role_name}' requires one of {role.allowed_semantic_types}."
                )
                return step

    if all_roles_ready:
        remaining_choices = [
            choice
            for choice in unresolved_choices
            if _is_missing_choice(
                _first_non_empty_mapping_value(step, choice)
            )
        ]

        if remaining_choices:
            step.status = "needs_user_choice"
            step.execution_ready = False
            step.required_user_choices = _unique_strings(
                list(step.required_user_choices or []) + remaining_choices
            )
            return step

        step.status = "ready"
        step.execution_ready = True
        step.required_user_choices = []

    else:
        if step.status not in {"blocked", "not_applicable"}:
            step.status = "needs_user_choice"
        step.execution_ready = False

    return step


def verify_plan_step(step: PlanStep, profile: DatasetProfileV2) -> PlanStep:
    """
    Verify a PlanStep against the unified AnalysisToolPlugin contract.

    This function is generic and method-agnostic.
    """
    if not step.tool_name:
        step.status = "blocked"
        step.execution_ready = False
        step.warnings.append("Plan step has no tool_name.")
        return step

    plugin = get_plugin(step.tool_name)

    if plugin is None:
        step.status = "blocked"
        step.execution_ready = False
        step.warnings.append(f"Unknown tool '{step.tool_name}'.")
        return step

    if getattr(plugin, "execute", None) is None:
        step.status = "blocked"
        step.execution_ready = False
        step.warnings.append(f"Tool '{step.tool_name}' is not executable.")
        return step

    checker = getattr(plugin, "applicability_checker", None)

    if checker is not None:
        try:
            result: ApplicabilityResult = checker(
                profile=profile,
                variables=step.variables,
                mode="plan_verification",
            )

            step.status = result.status
            step.execution_ready = result.status == "ready" and not result.required_user_choices
            step.required_user_choices = result.required_user_choices
            step.candidate_variables = {
                **step.candidate_variables,
                **result.candidate_variables,
            }
            step.warnings.extend(result.warnings)
            step.suggested_alternatives = result.suggested_alternatives
            step.applicability_check = result.to_dict()

            return step

        except Exception as e:
            step.status = "blocked"
            step.execution_ready = False
            step.warnings.append(
                f"Applicability checker failed: {type(e).__name__}: {e}"
            )
            return step

    return _verify_variable_roles(step, profile, plugin)


def verify_plan(plan: PlanProposal, profile: DatasetProfileV2) -> PlanProposal:
    plan = reorder_clean_data_before_modeling(plan, profile)
    verified_steps = []
    blocked_steps = list(plan.blocked_or_not_recommended)

    for step in plan.steps:
        verified = verify_plan_step(step, profile)

        if verified.status in {"blocked", "not_applicable"}:
            blocked_steps.append(verified)
        else:
            verified_steps.append(verified)

    plan.steps = verified_steps
    plan.blocked_or_not_recommended = blocked_steps

    if any(step.status == "needs_user_choice" for step in plan.steps):
        plan.status = "partially_ready"
    elif all(step.execution_ready for step in plan.steps) and plan.steps:
        plan.status = "verified"
    else:
        plan.status = "draft"

    return plan
