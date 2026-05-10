from __future__ import annotations

import re
from typing import List

from core.domain.intent import IntentDecision
from core.domain.task import TaskSpec


def _normalize_text(user_message: str) -> str:
    return " ".join((user_message or "").strip().lower().split())


def _known_columns_from_state(state: dict | None) -> List[str]:
    state = state or {}
    profile = state.get("dataset_profile_v2") or state.get("dataset_profile") or {}
    columns = profile.get("columns") if isinstance(profile, dict) else None

    if isinstance(columns, dict):
        return [str(name) for name in columns.keys()]

    if isinstance(columns, list):
        names = []
        for item in columns:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return names

    summary = state.get("dataset_summary") or {}
    names = []
    for key in ("numeric_columns", "categorical_columns", "binary_columns", "id_like_columns"):
        values = summary.get(key) if isinstance(summary, dict) else None
        if isinstance(values, list):
            names.extend(str(value) for value in values)

    return sorted(set(names))


def _extract_columns_from_text(user_message: str, known_columns: List[str]) -> List[str]:
    found = []
    lowered = user_message.lower()

    for column in known_columns:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(column.lower())}(?![A-Za-z0-9_])"
        if re.search(pattern, lowered) and column not in found:
            found.append(column)

    return found


def _extract_regression_roles(user_message: str, known_columns: List[str]) -> tuple[List[str], List[str]]:
    selected = _extract_columns_from_text(user_message, known_columns)
    normalized = _normalize_text(user_message)

    match = re.search(
        r"\b(?:of|predict(?:ing)?|model(?:ing)?)\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"(?:on|from|using|with)\s+(?P<predictors>[A-Za-z0-9_,\s+and]+)",
        normalized,
    )

    if match:
        target_raw = match.group("target")
        predictors_raw = match.group("predictors")

        target = _match_known_column(target_raw, known_columns) or target_raw
        predictors = [
            _match_known_column(token, known_columns) or token
            for token in re.split(r",|\+|\band\b|\s+", predictors_raw)
            if token and token not in {"and", "on", "from", "using", "with"}
        ]
        predictors = [value for value in predictors if value != target]

        return [target], _dedupe(predictors)

    if len(selected) >= 2:
        return [selected[0]], selected[1:]

    return (selected[:1], selected[1:])


def _match_known_column(token: str, known_columns: List[str]) -> str | None:
    token = (token or "").strip().lower()
    for column in known_columns:
        if column.lower() == token:
            return column
    return None


def _dedupe(values: List[str]) -> List[str]:
    out = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _is_explicit_summary_statistics_request(text: str) -> bool:
    explicit_phrases = {
        "summary statistics",
        "summary stats",
        "descriptive statistics",
        "descriptive stats",
        "summarize numeric variables",
    }

    return any(phrase in text for phrase in explicit_phrases)


def _task_spec(
    *,
    goal_type: str,
    user_message: str,
    user_goal: str,
    target_variables: List[str] | None = None,
    predictor_variables: List[str] | None = None,
    requested_methods: List[str] | None = None,
    confidence: float,
) -> TaskSpec:
    return TaskSpec(
        goal_type=goal_type,
        user_goal=user_goal,
        source_user_request=user_message,
        target_variables=target_variables or [],
        predictor_variables=predictor_variables or [],
        requested_methods=requested_methods or [],
        confidence=confidence,
    )


def decide_interaction_intent(
    user_message: str,
    *,
    state: dict | None = None,
) -> IntentDecision:
    text = _normalize_text(user_message)
    known_columns = _known_columns_from_state(state)

    if not text:
        return IntentDecision(
            intent="unknown",
            confidence=0.0,
            reason="Empty user message.",
            should_execute=False,
        )

    plan_terms = {"plan", "proposal", "propose", "draft"}
    execute_terms = {"run", "execute", "start", "continue"}
    dataset_terms = {"data", "dataset", "columns", "variables", "overview", "summary", "summarize", "describe"}
    suggestion_terms = {"suggest", "recommend", "options", "ideas"}
    regression_terms = {"regression", "linear model", "model"}
    cleaning_terms = {"clean", "drop", "impute", "remove missing", "fill missing"}
    plot_terms = {"plot", "histogram", "scatterplot", "chart", "figure"}
    correlation_terms = {"correlation", "correlate"}

    tokens = set(re.findall(r"[a-z0-9_]+", text))

    if "plan" in tokens and tokens.intersection(execute_terms):
        return IntentDecision(
            intent="execute_plan",
            confidence=0.9,
            reason="User explicitly asked to run or continue a plan.",
            should_execute=True,
        )

    if tokens.intersection(plan_terms):
        return IntentDecision(
            intent="plan_analysis",
            confidence=0.82,
            reason="User asked for an analysis plan rather than immediate execution.",
            task_spec=_task_spec(
                goal_type="analysis_planning",
                user_message=user_message,
                user_goal="Create a data-aware analysis plan.",
                confidence=0.82,
            ),
            should_execute=False,
        )

    if tokens.intersection(suggestion_terms):
        return IntentDecision(
            intent="plan_analysis",
            confidence=0.76,
            reason="User asked for suggestions or options.",
            task_spec=_task_spec(
                goal_type="analysis_recommendation",
                user_message=user_message,
                user_goal="Recommend useful analyses for the current dataset.",
                confidence=0.76,
            ),
            should_execute=False,
        )

    if any(term in text for term in cleaning_terms):
        selected = _extract_columns_from_text(user_message, known_columns)
        return IntentDecision(
            intent="modify_data",
            confidence=0.78,
            reason="User requested a data-cleaning or data-modification task.",
            task_spec=_task_spec(
                goal_type="data_cleaning",
                user_message=user_message,
                user_goal="Modify or clean the dataset.",
                target_variables=selected,
                requested_methods=["data_cleaning"],
                confidence=0.78,
            ),
            should_execute=True,
        )

    if any(term in text for term in regression_terms):
        target_variables, predictor_variables = _extract_regression_roles(
            user_message,
            known_columns,
        )
        return IntentDecision(
            intent="direct_analysis",
            confidence=0.8,
            reason="User requested regression/modeling at the task level.",
            task_spec=_task_spec(
                goal_type="regression_modeling",
                user_message=user_message,
                user_goal="Fit and interpret a regression model.",
                target_variables=target_variables,
                predictor_variables=predictor_variables,
                requested_methods=["linear_regression"] if "linear" in tokens else ["regression"],
                confidence=0.8,
            ),
            should_execute=True,
        )

    if _is_explicit_summary_statistics_request(text):
        return IntentDecision(
            intent="direct_analysis",
            confidence=0.74,
            reason="User explicitly requested summary statistics.",
            task_spec=_task_spec(
                goal_type="dataset_overview",
                user_message=user_message,
                user_goal="Compute summary statistics for the current dataset.",
                requested_methods=["summary_statistics"],
                confidence=0.74,
            ),
            should_execute=True,
        )

    if any(term in text for term in correlation_terms):
        selected = _extract_columns_from_text(user_message, known_columns)
        return IntentDecision(
            intent="direct_analysis",
            confidence=0.76,
            reason="User requested an association or correlation analysis.",
            task_spec=_task_spec(
                goal_type="association_analysis",
                user_message=user_message,
                user_goal="Analyze association between variables.",
                predictor_variables=selected,
                requested_methods=["correlation"],
                confidence=0.76,
            ),
            should_execute=True,
        )

    if tokens.intersection(plot_terms):
        selected = _extract_columns_from_text(user_message, known_columns)
        return IntentDecision(
            intent="direct_analysis",
            confidence=0.7,
            reason="User requested a plot or visual analysis.",
            task_spec=_task_spec(
                goal_type="visualization",
                user_message=user_message,
                user_goal="Create a data visualization.",
                predictor_variables=selected,
                requested_methods=["plot"],
                confidence=0.7,
            ),
            should_execute=True,
        )

    if tokens.intersection(dataset_terms):
        return IntentDecision(
            intent="advisory",
            confidence=0.72,
            reason="User asked for dataset understanding or available analysis context.",
            task_spec=_task_spec(
                goal_type="dataset_overview",
                user_message=user_message,
                user_goal="Understand the dataset structure and available analyses.",
                requested_methods=["dataset_overview"],
                confidence=0.72,
            ),
            should_execute=False,
        )

    return IntentDecision(
        intent="unknown",
        confidence=0.2,
        reason="No structured analysis intent could be determined conservatively.",
        should_execute=False,
    )


def legacy_interaction_intent_from_decision(decision: IntentDecision) -> str:
    if decision.intent == "advisory":
        return "advisory"

    if decision.intent == "plan_analysis":
        return "plan_only"

    if decision.intent == "execute_plan":
        return "execute_plan"

    if decision.intent in {"direct_analysis", "modify_data"}:
        return "direct_tool"

    return "unknown"
