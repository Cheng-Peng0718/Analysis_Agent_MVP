from typing import Any, Dict, Tuple
import math
import warnings

import statsmodels.api as sm
import statsmodels.stats.api as sms
from statsmodels.stats.outliers_influence import variance_inflation_factor

from core.analysis_tool_plugins.base import (
    AnalysisToolPlugin,
    ArgumentSchema,
    DisplayConfig,
    MetricDisplayConfig,
    TableDisplayConfig,
    compact_dict,
    format_bool_yes_no,
    format_number,
    format_p_value,
)
from core.analysis_tool_plugins.registry import register_plugin
from core.analysis_tool_plugins.shared.regression_utils import prepare_regression_data
from core.guardrails import evaluate_diagnostics_guardrails


def _ok(message: str, details: Dict[str, Any], artifacts=None):
    return {
        "status": "ok",
        "message": message,
        "recoverable": False,
        "details": details or {},
        "artifacts": artifacts or [],
    }


def _warning(message: str, details: Dict[str, Any], artifacts=None):
    return {
        "status": "warning",
        "message": message,
        "recoverable": False,
        "details": details or {},
        "artifacts": artifacts or [],
    }


def _failed(error_code: str, message: str, exc: Exception):
    return {
        "status": "failed",
        "error_code": error_code,
        "message": message,
        "recoverable": True,
        "details": {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
        "artifacts": [],
    }


def _round_or_none(x: Any, digits: int = 6):
    try:
        v = float(x)
        if not math.isfinite(v):
            return None
        return round(v, digits)
    except Exception:
        return None


def _get_arg(context, name: str, default: Any = None) -> Any:
    try:
        return context.get_arg(name, default)
    except TypeError:
        try:
            value = context.get_arg(name)
            return default if value is None else value
        except Exception:
            return default
    except Exception:
        return default

def _get_analysis_runs(context) -> list[dict[str, Any]]:
    runs = getattr(context, "analysis_runs", None)

    if runs is None:
        return []

    if isinstance(runs, list):
        return runs

    return []


def _run_id(run: dict[str, Any]) -> str | None:
    return run.get("run_id") or run.get("analysis_run_id")


def _extract_model_spec_from_run(run: dict[str, Any]) -> dict[str, Any] | None:
    metadata = run.get("metadata", {}) or {}

    model_spec = metadata.get("model_spec")

    if isinstance(model_spec, dict):
        return model_spec

    return None


def _find_regression_run_by_id(
    analysis_runs: list[dict[str, Any]],
    source_analysis_run_id: str | None,
) -> dict[str, Any] | None:
    if not source_analysis_run_id:
        return None

    for run in analysis_runs or []:
        if _run_id(run) == source_analysis_run_id:
            return run

    return None


def _find_latest_regression_run(
    analysis_runs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for run in reversed(analysis_runs or []):
        if run.get("status") not in {"ok", "warning"}:
            continue

        categories = run.get("evidence_categories", []) or []

        if "regression_model" not in categories:
            continue

        if _extract_model_spec_from_run(run):
            return run

    return None


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    if isinstance(value, tuple):
        return [str(item) for item in value]

    if isinstance(value, str):
        return [value]

    return [str(value)]


def _has_missing_dataset_columns(
    df,
    target_col: Any,
    feature_cols: list[str],
) -> bool:
    if not target_col or target_col not in df.columns:
        return True

    return any(col not in df.columns for col in feature_cols)


def _resolve_diagnostic_model_inputs(
    context,
    df,
) -> tuple[str | None, list[str], dict[str, Any]]:
    """
    Resolve diagnostics target/features.

    Priority:
    1. Explicit source_analysis_run_id if provided.
    2. Latest successful regression_model run if explicit args are missing
       or explicit feature columns are not active dataset columns.
    3. Explicit target_col / feature_cols fallback.

    This aligns diagnostics with the regression model contract and prevents
    dummy coefficient terms such as region_North from being treated as raw
    dataset columns.
    """
    explicit_target = _get_arg(context, "target_col")
    explicit_features = _as_string_list(_get_arg(context, "feature_cols", []))
    source_analysis_run_id = _get_arg(context, "source_analysis_run_id")

    analysis_runs = _get_analysis_runs(context)

    selected_run = _find_regression_run_by_id(
        analysis_runs,
        source_analysis_run_id,
    )

    if selected_run is None:
        selected_run = _find_latest_regression_run(analysis_runs)

    explicit_args_missing_or_invalid = (
        not explicit_target
        or not explicit_features
        or _has_missing_dataset_columns(df, explicit_target, explicit_features)
    )

    if selected_run is not None and (
        source_analysis_run_id or explicit_args_missing_or_invalid
    ):
        model_spec = _extract_model_spec_from_run(selected_run) or {}

        target_col = model_spec.get("target_col")
        feature_cols = _as_string_list(
            model_spec.get("original_feature_cols")
        )

        if target_col and feature_cols:
            return target_col, feature_cols, {
                "resolved_from_model_spec": True,
                "source_analysis_run_id": _run_id(selected_run),
                "source_analysis_title": selected_run.get("title"),
                "source_model_spec": model_spec,
                "explicit_target_col": explicit_target,
                "explicit_feature_cols": explicit_features,
            }

    return explicit_target, explicit_features, {
        "resolved_from_model_spec": False,
        "source_analysis_run_id": source_analysis_run_id,
        "explicit_target_col": explicit_target,
        "explicit_feature_cols": explicit_features,
    }


def execute_regression_diagnostics(context) -> Dict[str, Any]:
    """
    Run VIF and Breusch-Pagan diagnostics using the same prepared design matrix as OLS.

    Args:
        target_col: numeric outcome column
        feature_cols: list of predictor columns
        max_missing_rate: optional, default 0.40
        max_categorical_levels: optional, default 10
        numeric_parse_threshold: optional, default 0.85
        min_n_per_parameter: optional, default 3
    """
    try:
        df = context.load_df()

        target_col, feature_cols, resolution_details = _resolve_diagnostic_model_inputs(
            context,
            df,
        )

        prep = prepare_regression_data(
            df,
            target_col,
            feature_cols,
            max_missing_rate=float(_get_arg(context, "max_missing_rate", 0.40)),
            max_categorical_levels=int(_get_arg(context, "max_categorical_levels", 10)),
            numeric_parse_threshold=float(_get_arg(context, "numeric_parse_threshold", 0.85)),
            min_n_per_parameter=int(_get_arg(context, "min_n_per_parameter", 3)),
        )

        if prep.get("status") != "ok":
            return prep

        y = prep["y"]
        X = prep["X"]
        X_const = sm.add_constant(X, has_constant="add")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = sm.OLS(y, X_const).fit()

        vif_rows = []

        for i, col in enumerate(X_const.columns):
            if col == "const":
                continue

            try:
                value = variance_inflation_factor(X_const.values, i)
                vif_value = _round_or_none(value)
            except Exception:
                vif_value = None

            vif_rows.append({
                "term": str(col),
                "vif": vif_value,
                "flag": bool(vif_value is not None and vif_value > 10),
            })

        bp_stat, bp_pvalue, bp_fstat, bp_fpvalue = sms.het_breuschpagan(
            model.resid,
            model.model.exog,
        )

        breusch_pagan = {
            "lm_statistic": _round_or_none(bp_stat),
            "lm_p_value": _round_or_none(bp_pvalue),
            "f_statistic": _round_or_none(bp_fstat),
            "f_p_value": _round_or_none(bp_fpvalue),
            "heteroscedasticity_flag_0_05": (
                bool(bp_pvalue < 0.05)
                if math.isfinite(float(bp_pvalue))
                else None
            ),
        }

        details = {
            **prep["details"],
            **resolution_details,
            "vif": vif_rows,
            "breusch_pagan": breusch_pagan,
        }

        has_vif_warning = any(row.get("flag") for row in vif_rows)
        has_bp_warning = breusch_pagan.get("heteroscedasticity_flag_0_05") is True

        if has_vif_warning or has_bp_warning:
            return _warning(
                "Regression diagnostics completed with statistical warnings.",
                details,
            )

        return _ok(
            "Regression diagnostics completed successfully.",
            details,
        )

    except Exception as e:
        return _failed(
            "REGRESSION_DIAGNOSTICS_EXCEPTION",
            "Regression diagnostics failed.",
            e,
        )


def extract_regression_diagnostics(
    *,
    payload: Dict[str, Any],
    arguments: Dict[str, Any],
    default_title: str,
    default_summary: str,
) -> Tuple[str, str, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    title = "Model Diagnostics"

    vif = payload.get("vif", []) or []
    bp = payload.get("breusch_pagan", {}) or {}

    vif_values = [
        row.get("vif")
        for row in vif
        if isinstance(row, dict) and row.get("vif") is not None
    ]

    metrics = compact_dict({
        "max_vif": max(vif_values) if vif_values else None,
        "breusch_pagan_lm_statistic": bp.get("lm_statistic") if isinstance(bp, dict) else None,
        "breusch_pagan_lm_p_value": bp.get("lm_p_value") if isinstance(bp, dict) else None,
        "breusch_pagan_f_statistic": bp.get("f_statistic") if isinstance(bp, dict) else None,
        "breusch_pagan_f_p_value": bp.get("f_p_value") if isinstance(bp, dict) else None,
        "heteroscedasticity_flag_0_05": (
            bp.get("heteroscedasticity_flag_0_05")
            if isinstance(bp, dict)
            else None
        ),
    })

    tables: Dict[str, Any] = {}

    if vif:
        tables["vif"] = vif

    # Do not put raw breusch_pagan JSON into report tables.
    # The user-facing BP results are already in metrics.

    metadata = compact_dict({
        "breusch_pagan": bp,
        "resolved_from_model_spec": payload.get("resolved_from_model_spec"),
        "source_analysis_run_id": payload.get("source_analysis_run_id"),
        "source_analysis_title": payload.get("source_analysis_title"),
        "source_model_spec": payload.get("source_model_spec"),
        "explicit_target_col": payload.get("explicit_target_col"),
        "explicit_feature_cols": payload.get("explicit_feature_cols"),
        "n_eff": payload.get("n_eff"),
        "p_eff": payload.get("p_eff"),
        "target": payload.get("target"),
        "encoded_columns": payload.get("encoded_columns"),
        "used_features": payload.get("used_features"),
        "excluded_features": payload.get("excluded_features"),
        "raw_feature_count": payload.get("raw_feature_count"),
        "encoded_column_count": payload.get("encoded_column_count"),
        "min_required": payload.get("min_required"),
    })

    summary = "Computed multicollinearity and heteroscedasticity diagnostics."

    if metrics.get("max_vif") is not None:
        summary += f" Max VIF={metrics.get('max_vif')}."

    if metrics.get("breusch_pagan_lm_p_value") is not None:
        summary += f" Breusch-Pagan p={metrics.get('breusch_pagan_lm_p_value')}."

    return title, summary, metrics, tables, metadata


MODEL_DIAGNOSTICS_DISPLAY = DisplayConfig(
    metrics=MetricDisplayConfig(
        labels={
            "max_vif": "Maximum VIF",
            "breusch_pagan_lm_statistic": "Breusch-Pagan LM statistic",
            "breusch_pagan_lm_p_value": "Breusch-Pagan LM p-value",
            "breusch_pagan_f_statistic": "Breusch-Pagan F statistic",
            "breusch_pagan_f_p_value": "Breusch-Pagan F-test p-value",
            "heteroscedasticity_flag_0_05": "Heteroscedasticity flag",
        },
        formatters={
            "max_vif": lambda x: format_number(x, digits=4),
            "breusch_pagan_lm_statistic": lambda x: format_number(x, digits=4),
            "breusch_pagan_lm_p_value": format_p_value,
            "breusch_pagan_f_statistic": lambda x: format_number(x, digits=4),
            "breusch_pagan_f_p_value": format_p_value,
            "heteroscedasticity_flag_0_05": format_bool_yes_no,
        },
        order=[
            "max_vif",
            "breusch_pagan_lm_statistic",
            "breusch_pagan_lm_p_value",
            "breusch_pagan_f_statistic",
            "breusch_pagan_f_p_value",
            "heteroscedasticity_flag_0_05",
        ],
    ),
    tables={
        "vif": TableDisplayConfig(
            column_labels={
                "term": "Term",
                "vif": "VIF",
                "flag": "High VIF flag",
            },
            column_formatters={
                "vif": lambda x: format_number(x, digits=4),
                "flag": format_bool_yes_no,
            },
            column_order=[
                "term",
                "vif",
                "flag",
            ],
        ),
    },
)


PLUGIN = register_plugin(AnalysisToolPlugin(
    tool_name="regression_diagnostics",
    display_name="Model Diagnostics",
    description=(
        "Run regression diagnostics such as VIF and Breusch-Pagan tests. "
        "When a previous regression model exists, this tool can diagnose that model "
        "using its stored model_spec instead of requiring manually supplied columns."
    ),
    usage_guidance=(
        "Prefer diagnosing the most recent regression_model analysis run. "
        "After run_multiple_regression has been executed, this tool may be called "
        "with source_analysis_run_id or with no target_col/feature_cols; it will "
        "resolve the latest regression model spec. If target_col/feature_cols are supplied "
        "but contain encoded coefficient terms such as region_North or segment_Corporate, "
        "the tool should fall back to the stored model_spec and use the original active-dataset "
        "features such as region and segment."
    ),
    evidence_categories=["regression_diagnostics", "model_diagnostics"],
    requires_confirmation=False,
    argument_schema=ArgumentSchema(
        required={},
        optional={
            "source_analysis_run_id": str,
            "target_col": str,
            "feature_cols": list,
            "max_missing_rate": float,
            "max_categorical_levels": int,
            "numeric_parse_threshold": float,
            "min_n_per_parameter": int,
        },
        column_args=[
            "target_col",
        ],
        column_list_args=[
            "feature_cols",
        ],
        allow_all_columns=False,
    ),
    execute=execute_regression_diagnostics,
    extractor=extract_regression_diagnostics,
    guardrail_evaluators=[
        evaluate_diagnostics_guardrails,
    ],
    display_config=MODEL_DIAGNOSTICS_DISPLAY,
))