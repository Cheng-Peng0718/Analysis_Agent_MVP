from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from core.responses import make_response_update
from core.domain.intent import IntentDecision
from core.dataset_intelligence.schemas import DatasetProfileV2
from core.planning.schemas import PlanStep
from core.planning.verifier import verify_plan_step
from core.analysis_tool_plugins import get_plugin
from core.analysis_tool_plugins.manifest import build_tool_manifest
from core.services.llm_interaction_parser import (
    decide_llm_interaction_intent,
    route_intent_from_decision,
)


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dict(dumped)

    return {}


def _task_spec_dict(decision: IntentDecision) -> Dict[str, Any]:
    task_spec = getattr(decision, "task_spec", None)
    return _as_dict(task_spec)


def _normalize_column_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _column_lookup(profile: DatasetProfileV2) -> Dict[str, str]:
    lookup: Dict[str, str] = {}

    for column_name in profile.columns.keys():
        if not isinstance(column_name, str):
            continue

        lookup[column_name] = column_name
        lookup[column_name.casefold()] = column_name
        lookup[_normalize_column_key(column_name)] = column_name

    return lookup


def _resolve_column_name(value: Any, lookup: Dict[str, str]) -> Tuple[Any, str | None]:
    if not isinstance(value, str):
        return value, "Column reference must be a string."

    stripped = value.strip()

    if not stripped:
        return value, "Column reference is empty."

    resolved = lookup.get(stripped)
    if resolved is not None:
        return resolved, None

    resolved = lookup.get(stripped.casefold())
    if resolved is not None:
        return resolved, None

    resolved = lookup.get(_normalize_column_key(stripped))
    if resolved is not None:
        return resolved, None

    return value, f"Column '{value}' does not exist in the current dataset."


def _resolve_column_value(value: Any, *, choice_name: str, plugin: Any, profile: DatasetProfileV2) -> Tuple[Any, List[str]]:
    schema = getattr(plugin, "argument_schema", None)
    column_args = set(getattr(schema, "column_args", []) or [])
    column_list_args = set(getattr(schema, "column_list_args", []) or [])

    lookup = _column_lookup(profile)
    errors: List[str] = []

    if choice_name in column_args:
        resolved, error = _resolve_column_name(value, lookup)
        if error:
            errors.append(error)
        return resolved, errors

    if choice_name in column_list_args:
        values = value if isinstance(value, list) else [value]
        resolved_values = []

        for item in values:
            resolved, error = _resolve_column_name(item, lookup)
            if error:
                errors.append(error)
            else:
                resolved_values.append(resolved)

        return resolved_values, errors

    return value, []


def _is_missing_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _task_value_from_binding(task_spec: Dict[str, Any], binding: Dict[str, Any]) -> Any:
    task_field = binding.get("task_field")

    if not task_field:
        return None

    value = task_spec.get(task_field)
    index = binding.get("index")

    if index is not None:
        try:
            if isinstance(value, list):
                return value[int(index)]
        except Exception:
            return None

    return value


def _coerce_assignment_value(value: str) -> Any:
    cleaned = value.strip().strip(" ;\n\t")
    cleaned = cleaned.rstrip(".")

    if not cleaned:
        return ""

    parts = [
        part.strip().strip("'\"").rstrip(".")
        for part in cleaned.split(",")
        if part.strip()
    ]

    if len(parts) > 1:
        return parts

    return cleaned.strip("'\"")


def _explicit_assignment_arguments(text: Any) -> Dict[str, Any]:
    """Extract explicit key=value assignments from the user text.

    This is not intent routing and does not know any concrete tool names. It is
    a generic assignment parser used only after plugin contracts decide whether
    a key is meaningful for a pending plan step.
    """
    if not isinstance(text, str) or "=" not in text:
        return {}

    result: Dict[str, Any] = {}
    pattern = re.compile(
        r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*?)(?=,\s*[A-Za-z_][A-Za-z0-9_]*\s*=|$)",
        flags=re.DOTALL,
    )

    for match in pattern.finditer(text):
        key = match.group("key").strip()
        value = _coerce_assignment_value(match.group("value"))
        if key and not _is_missing_value(value):
            result[key] = value

    return result


def _contract_direct_arguments(task_spec: Dict[str, Any]) -> Dict[str, Any]:
    constraints = task_spec.get("constraints") or {}

    result: Dict[str, Any] = {}

    if isinstance(constraints, dict):
        for key in [
            "role_arguments",
            "arguments",
            "variables",
            "choices",
        ]:
            value = constraints.get(key)
            if isinstance(value, dict):
                result.update(value)

        # Also accept top-level constraint keys. The LLM parser is instructed to use
        # plugin role / argument names when it can, so this remains contract-driven.
        for key, value in constraints.items():
            if isinstance(value, dict):
                continue
            result.setdefault(key, value)

    # If the user explicitly writes contract-shaped assignments like
    # "target_col = GPA" or "action_type = drop", keep those values even when
    # the LLM classified the turn as direct_analysis/modify_data instead of
    # clarification. The downstream plugin contract still decides whether each
    # key is applicable to a pending step.
    for text_field in ["source_user_request", "user_goal"]:
        explicit = _explicit_assignment_arguments(task_spec.get(text_field))
        for key, value in explicit.items():
            result.setdefault(key, value)

    return result



def _plugin_contract_argument_names(plugin: Any) -> set[str]:
    schema = getattr(plugin, "argument_schema", None)
    names: set[str] = set()

    if schema is not None:
        names.update((getattr(schema, "required", {}) or {}).keys())
        names.update((getattr(schema, "optional", {}) or {}).keys())
        names.update(getattr(schema, "column_args", []) or [])
        names.update(getattr(schema, "column_list_args", []) or [])
        names.update((getattr(schema, "allowed_values", {}) or {}).keys())

    for role in getattr(plugin, "variable_roles", []) or []:
        role_name = getattr(role, "role_name", None)
        if role_name:
            names.add(role_name)

    planning_policy = getattr(plugin, "planning_policy", None)
    if planning_policy is not None:
        names.update(getattr(planning_policy, "required_user_choices", []) or [])

    manifest = build_tool_manifest(plugin)
    for binding in manifest.task_argument_bindings or []:
        if isinstance(binding, dict) and binding.get("argument"):
            names.add(str(binding["argument"]))

    return names


def _candidate_arg_applies_to_step(
    *,
    choice_name: str,
    required_choices: List[str],
    plugin: Any,
) -> bool:
    if choice_name in required_choices:
        return True

    return choice_name in _plugin_contract_argument_names(plugin)


def _pending_plan_has_unresolved_choices(state: Dict[str, Any]) -> bool:
    pending_plan = state.get("pending_plan")
    if not isinstance(pending_plan, dict):
        return False

    for step in pending_plan.get("steps", []) or []:
        if isinstance(step, dict) and _step_needs_choices(step):
            return True

    return False


def _should_attempt_plan_clarification(
    state: Dict[str, Any],
    decision: IntentDecision,
    backend_command: Any,
) -> bool:
    if backend_command == "execute_pending_plan":
        return False

    if decision.intent in {"execute_plan", "plan_analysis", "advisory"}:
        return False

    if decision.task_spec is None:
        return False

    return _pending_plan_has_unresolved_choices(state)


def _candidate_arguments_for_step(
    *,
    step: Dict[str, Any],
    task_spec: Dict[str, Any],
    plugin: Any,
) -> Dict[str, Any]:
    manifest = build_tool_manifest(plugin)
    candidate_args = _contract_direct_arguments(task_spec)

    # Plugin-level task_argument_bindings are the preferred way to map high-level
    # TaskSpec fields such as target_variables or predictor_variables into the
    # concrete execution argument names required by each tool.
    for binding in manifest.task_argument_bindings or []:
        if not isinstance(binding, dict):
            continue

        argument_name = binding.get("argument")
        if not argument_name or not _is_missing_value(candidate_args.get(argument_name)):
            continue

        value = _task_value_from_binding(task_spec, binding)
        if not _is_missing_value(value):
            candidate_args[argument_name] = value

    step_id = step.get("step_id")
    per_step = task_spec.get("constraints", {}).get("step_arguments") if isinstance(task_spec.get("constraints"), dict) else None
    if isinstance(per_step, dict) and step_id in per_step and isinstance(per_step[step_id], dict):
        candidate_args.update(per_step[step_id])

    return candidate_args


def _step_needs_choices(step: Dict[str, Any]) -> bool:
    execution_status = step.get("execution_status")
    if execution_status in {"running", "completed", "failed", "skipped", "blocked"}:
        return False

    return (
        step.get("status") == "needs_user_choice"
        or bool(step.get("required_user_choices"))
        or step.get("execution_ready") is not True
    )


def _recompute_plan_status(plan: Dict[str, Any]) -> str:
    steps = [step for step in plan.get("steps", []) or [] if isinstance(step, dict)]

    if not steps:
        return plan.get("status") or "draft"

    unfinished = [
        step
        for step in steps
        if step.get("execution_status") not in {"completed", "skipped"}
    ]

    if not unfinished:
        return "completed"

    if any(step.get("status") == "needs_user_choice" for step in unfinished):
        return "partially_ready"

    if any(step.get("status") in {"blocked", "not_applicable"} for step in unfinished):
        return "blocked"

    if any(step.get("execution_status") == "completed" for step in steps):
        return "partially_executed"

    if all(step.get("status") == "ready" and step.get("execution_ready") is True for step in unfinished):
        return "verified"

    return plan.get("status") or "draft"


def _format_unmatched_columns(errors: List[str], profile: DatasetProfileV2) -> str:
    columns = list(profile.columns.keys())
    preview = ", ".join(str(col) for col in columns[:12])
    if len(columns) > 12:
        preview += ", ..."

    lines = [
        "I could not apply that clarification to the pending plan because at least one column did not match the current dataset.",
        "",
        "Unmatched input:",
    ]
    for error in errors:
        lines.append(f"- {error}")

    if preview:
        lines.extend([
            "",
            f"Available columns include: {preview}",
        ])

    lines.append("")
    lines.append("Please reply with the exact column name(s) you want to use.")
    return "\n".join(lines)


def _format_unapplied_clarification(plan: Dict[str, Any] | None) -> str:
    lines = [
        "I understood this as a clarification, but I could not map it to the pending plan choices yet.",
    ]

    if isinstance(plan, dict):
        missing_blocks: List[str] = []
        for step in plan.get("steps", []) or []:
            if not isinstance(step, dict):
                continue
            choices = step.get("required_user_choices") or []
            if not choices:
                continue
            title = step.get("title") or step.get("tool_name") or step.get("step_id")
            missing_blocks.append(f"- {title}: {', '.join(str(choice) for choice in choices)}")

        if missing_blocks:
            lines.extend([
                "",
                "Pending choices:",
                *missing_blocks[:8],
            ])

    lines.extend([
        "",
        "Please reply using the missing role names or exact dataset columns, for example: `target_col = GPA, feature_cols = SATM`.",
    ])

    return "\n".join(lines)


def apply_pending_plan_clarification(state: Dict[str, Any], decision: IntentDecision) -> Dict[str, Any]:
    """
    Apply a chat-only clarification to an existing pending plan.

    This function is intentionally contract-driven:
    - it reads each step's plugin argument schema / variable roles;
    - it reads plugin planning_metadata.task_argument_bindings;
    - it reuses verify_plan_step as the authority for readiness.

    It does not route by hard-coded user phrases or specific tool names.
    """
    pending_plan = state.get("pending_plan")
    profile_dict = state.get("dataset_profile_v2")
    task_spec = _task_spec_dict(decision)

    if not isinstance(pending_plan, dict) or not profile_dict or not task_spec:
        return {
            "applied": False,
            "reason": "missing_pending_plan_profile_or_task_spec",
        }

    try:
        profile = DatasetProfileV2.model_validate(profile_dict)
    except Exception as exc:
        return {
            "applied": False,
            "reason": f"invalid_dataset_profile: {type(exc).__name__}: {exc}",
        }

    plan = dict(pending_plan)
    updated_steps: List[Dict[str, Any]] = []
    updated_step_ids: List[str] = []
    unmatched_errors: List[str] = []

    for raw_step in plan.get("steps", []) or []:
        if not isinstance(raw_step, dict):
            updated_steps.append(raw_step)
            continue

        step = dict(raw_step)

        if not _step_needs_choices(step):
            updated_steps.append(step)
            continue

        tool_name = step.get("tool_name")
        plugin = get_plugin(tool_name) if tool_name else None

        if plugin is None:
            updated_steps.append(step)
            continue

        candidate_args = _candidate_arguments_for_step(
            step=step,
            task_spec=task_spec,
            plugin=plugin,
        )

        required_choices = list(step.get("required_user_choices") or [])
        if not required_choices:
            required_choices = list(candidate_args.keys())

        if not candidate_args:
            updated_steps.append(step)
            continue

        step_arguments = dict(step.get("arguments") or {})
        step_variables = dict(step.get("variables") or {})
        changed = False

        for choice_name, raw_value in candidate_args.items():
            if not _candidate_arg_applies_to_step(
                choice_name=choice_name,
                required_choices=required_choices,
                plugin=plugin,
            ):
                # Do not inject unrelated values into this step. This keeps
                # clarification scoped to the plugin contract rather than to
                # concrete tool-name checks.
                continue

            if _is_missing_value(raw_value):
                continue

            resolved_value, errors = _resolve_column_value(
                raw_value,
                choice_name=choice_name,
                plugin=plugin,
                profile=profile,
            )

            if errors:
                unmatched_errors.extend(errors)
                continue

            if _is_missing_value(resolved_value):
                continue

            step_arguments[choice_name] = resolved_value
            step_variables[choice_name] = resolved_value
            changed = True

        if changed:
            step["arguments"] = step_arguments
            step["variables"] = step_variables

            verified = verify_plan_step(
                PlanStep.model_validate(step),
                profile,
            )
            step = verified.model_dump()

            ############## DEBUG ###############
            print("\n" + "=" * 40)
            print("[CLARIFICATION VERIFY RESULT]")
            print(f"step_id = {step.get('step_id')}")
            print(f"tool_name = {step.get('tool_name')}")
            print(f"status = {step.get('status')}")
            print(f"execution_ready = {step.get('execution_ready')}")
            print(f"arguments = {step.get('arguments')}")
            print(f"required_user_choices = {step.get('required_user_choices')}")
            print(f"warnings = {step.get('warnings')}")
            print("=" * 40 + "\n")
            ####################################

            updated_step_ids.append(step.get("step_id") or "")

        updated_steps.append(step)

    if unmatched_errors:
        return {
            "applied": False,
            "reason": "unmatched_columns",
            "unmatched_errors": unmatched_errors,
            "assistant_response_content": _format_unmatched_columns(unmatched_errors, profile),
        }

    updated_step_ids = [step_id for step_id in updated_step_ids if step_id]

    if not updated_step_ids:
        return {
            "applied": False,
            "reason": "no_matching_pending_plan_choice",
        }

    plan["steps"] = updated_steps
    plan["status"] = _recompute_plan_status(plan)

    return {
        "applied": True,
        "pending_plan": plan,
        "plan_status": plan.get("status"),
        "updated_step_ids": updated_step_ids,
    }


def intent_router_node(state: dict):
    user_request = state.get("user_request", "")
    backend_command = state.get("backend_command")

    clarification_update: Dict[str, Any] | None = None

    if backend_command == "execute_pending_plan":
        decision = IntentDecision(
            intent="execute_plan",
            confidence=1.0,
            reason="Backend command requested pending-plan execution.",
            task_spec=None,
            should_execute=True,
        )
    else:
        decision = decide_llm_interaction_intent(user_request, state=state)

    route_intent = route_intent_from_decision(decision)

    if _should_attempt_plan_clarification(state, decision, backend_command):
        clarification_update = apply_pending_plan_clarification(state, decision)

        if clarification_update.get("applied"):
            route_intent = "execute_plan"
        elif decision.intent == "clarification" or clarification_update.get("reason") == "unmatched_columns":
            route_intent = "end"

    print("\n" + "=" * 40)
    print("[INTENT ROUTER]")
    print(f"user_request = {user_request}")
    print(f"intent = {decision.intent}")
    print(f"route_intent = {route_intent}")
    if clarification_update:
        print(f"clarification_update = {clarification_update.get('reason') or 'applied'}")
    print("=" * 40 + "\n")

    updates = {
        "interaction_intent": route_intent,
        "intent_decision": {
            **decision.model_dump(),
            "route_intent": route_intent,
            "backend_command": backend_command,
            "pending_plan_clarification": clarification_update,
        },
        "backend_command": None,
    }

    if decision.task_spec is not None:
        updates["task_spec"] = decision.task_spec.model_dump()

    if clarification_update:
        updates["pending_plan_clarification"] = clarification_update

        if clarification_update.get("applied"):
            updates["pending_plan"] = clarification_update.get("pending_plan")
            updates["plan_status"] = clarification_update.get("plan_status")
            updates["plan_execution_status"] = "clarification_applied"

        else:
            reason = clarification_update.get("reason")
            content = clarification_update.get("assistant_response_content")
            if not content:
                content = _format_unapplied_clarification(state.get("pending_plan"))

            updates.update(make_response_update(
                response_type="clarification",
                content=content,
                source_node="intent_router",
                data_version_id=state.get("active_data_version_id"),
                plan_id=(state.get("pending_plan") or {}).get("plan_id") if isinstance(state.get("pending_plan"), dict) else None,
                plan_status=state.get("plan_status"),
                metadata={
                    "reason": reason,
                    "unmatched_errors": clarification_update.get("unmatched_errors", []),
                },
            ))

    return updates


def advisory_answer_node(state: dict):
    summary = state.get("dataset_summary") or {}
    capability_map = state.get("capability_map") or {}

    n_rows = summary.get("n_rows", "unknown")
    n_cols = summary.get("n_cols", "unknown")

    numeric_cols = summary.get("numeric_columns", []) or []
    categorical_cols = summary.get("categorical_columns", []) or []
    binary_cols = summary.get("binary_columns", []) or []
    id_like_cols = summary.get("id_like_columns", []) or []
    missingness = summary.get("missingness_summary", {}) or {}

    capabilities = capability_map.get("capabilities", []) or []

    ready = [c for c in capabilities if c.get("status") == "ready"]
    needs_choice = [c for c in capabilities if c.get("status") == "needs_user_choice"]
    not_applicable = [
        c for c in capabilities
        if c.get("status") in {"not_applicable", "blocked"}
    ]

    lines = []

    lines.append("I have profiled the current dataset. Here is what you can do next.")
    lines.append("")
    lines.append("Dataset overview:")
    lines.append(f"- Rows: {n_rows}")
    lines.append(f"- Columns: {n_cols}")
    lines.append(f"- Numeric columns: {len(numeric_cols)}")
    lines.append(f"- Categorical columns: {len(categorical_cols)}")
    lines.append(f"- Binary columns: {len(binary_cols)}")
    lines.append(f"- ID-like columns: {len(id_like_cols)}")
    lines.append(
        f"- Columns with missing values: "
        f"{missingness.get('n_columns_with_missing', 0)}"
    )
    lines.append("")

    if ready:
        lines.append("Analyses that appear ready:")
        for cap in ready[:8]:
            lines.append(
                f"- {cap.get('display_name', cap.get('tool_name'))}: "
                f"{cap.get('reason')}"
            )
        lines.append("")

    if needs_choice:
        lines.append("Analyses that may be useful but need your choices first:")
        for cap in needs_choice[:8]:
            choices = ", ".join(cap.get("required_user_choices", []) or [])
            lines.append(
                f"- {cap.get('display_name', cap.get('tool_name'))}: "
                f"needs {choices or 'additional choices'}"
            )
        lines.append("")

    if not_applicable:
        lines.append("Currently blocked or not recommended:")
        for cap in not_applicable[:5]:
            lines.append(
                f"- {cap.get('display_name', cap.get('tool_name'))}: "
                f"{cap.get('reason')}"
            )
        lines.append("")

    lines.append("I have not run any analysis tools yet.")
    lines.append(
        "If you want, say `make a plan` and I will draft a data-aware plan without executing it."
    )

    answer = "\n".join(lines)

    updates = make_response_update(
        response_type="advisory",
        content=answer,
        source_node="advisory_answer",
        data_version_id=state.get("active_data_version_id"),
        metadata={
            "interaction_intent": state.get("interaction_intent"),
        },
    )

    updates.update({
        "current_action": None,
        "current_execution": None,
        "current_verification": None,
    })

    return updates
