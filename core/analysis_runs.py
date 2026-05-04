import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove None values from a flat dict for cleaner UI display.
    """
    return {k: v for k, v in d.items() if v is not None}


def _safe_join_features(features: Any) -> str:
    if isinstance(features, list):
        return " + ".join(str(x) for x in features)
    if isinstance(features, str):
        return features
    return ""


def build_analysis_run_from_observation(
    *,
    tool_name: str,
    action_id: str,
    arguments: Dict[str, Any],
    data_version_id: Optional[str],
    status: str,
    success: bool,
    message: Optional[str],
    payload: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    observation_id: str,
) -> Dict[str, Any]:
    """
    Convert one tool observation into a UI-friendly AnalysisRun.

    This function keeps graph.py clean:
    - graph.py handles orchestration
    - this file handles result presentation extraction
    """

    arguments = arguments or {}
    payload = payload or {}
    artifacts = artifacts or []

    title = tool_name.replace("_", " ").title()
    summary = f"Tool `{tool_name}` finished with status `{status}`."
    if message:
        summary += f" {message}"

    metrics: Dict[str, Any] = {}
    tables: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Dataset inspection
    # ------------------------------------------------------------------
    if tool_name == "inspect_dataset":
        title = "Dataset Inspection"

        shape = payload.get("shape", {})
        metrics = _compact_dict({
            "rows": shape.get("rows") if isinstance(shape, dict) else None,
            "columns": shape.get("columns") if isinstance(shape, dict) else None,
            "total_missing": payload.get("total_missing"),
            "total_inf": payload.get("total_inf"),
        })

        columns = payload.get("columns", [])
        if columns:
            tables["columns"] = columns

        summary = "Inspected dataset shape, column types, missingness, and non-finite values."

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------
    elif tool_name == "get_summary_stats":
        title = "Summary Statistics"

        numeric_summary = payload.get("numeric_summary", {})
        categorical_summary = payload.get("categorical_summary", {})

        if numeric_summary:
            tables["numeric_summary"] = numeric_summary
        if categorical_summary:
            tables["categorical_summary"] = categorical_summary

        summary = "Computed descriptive summary statistics for the active dataset."

        # Surface GPA mean if available.
        try:
            if "GPA" in numeric_summary and "mean" in numeric_summary["GPA"]:
                metrics["GPA mean"] = numeric_summary["GPA"]["mean"]
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Column summary
    # ------------------------------------------------------------------
    elif tool_name == "summarize_columns":
        title = "Column Summary"

        col_summary = payload.get("summary", {})
        if col_summary:
            tables["summary"] = col_summary

        summary = "Summarized selected columns."

    # ------------------------------------------------------------------
    # Missingness report
    # ------------------------------------------------------------------
    elif tool_name == "missingness_report":
        title = "Missingness Report"

        shape = payload.get("shape", {})
        columns = payload.get("columns", [])

        metrics = _compact_dict({
            "rows": shape.get("rows") if isinstance(shape, dict) else None,
            "columns": shape.get("columns") if isinstance(shape, dict) else None,
        })

        if columns:
            tables["missingness_by_column"] = columns

        summary = "Computed missingness and non-finite values by column."

    # ------------------------------------------------------------------
    # Data cleaning
    # ------------------------------------------------------------------
    elif tool_name == "clean_data":
        title = "Data Cleaning"

        metrics = _compact_dict({
            "old_version_id": payload.get("old_version_id"),
            "new_version_id": payload.get("new_version_id"),
            "original_shape": payload.get("original_shape"),
            "final_shape": payload.get("final_shape"),
            "total_missing_before": payload.get("total_missing_before"),
            "total_missing_after": payload.get("total_missing_after"),
            "total_inf_before": payload.get("total_inf_before"),
            "total_inf_after": payload.get("total_inf_after"),
        })

        audit = payload.get("audit", {})
        if audit:
            tables["audit"] = audit

        action_type = payload.get("action_type")
        strategy = payload.get("strategy")
        new_version_id = payload.get("new_version_id")

        summary = "Completed data cleaning."
        if action_type or strategy:
            summary += f" Operation: {action_type}-{strategy}."
        if new_version_id:
            summary += f" Created new active data version `{new_version_id}`."

    # ------------------------------------------------------------------
    # Correlation matrix
    # ------------------------------------------------------------------
    elif tool_name == "get_correlation_matrix":
        title = "Correlation Matrix"

        metrics = _compact_dict({
            "method": payload.get("method"),
            "n_columns": len(payload.get("columns", [])) if payload.get("columns") else None,
        })

        corr = payload.get("correlation_matrix", {})
        if corr:
            tables["correlation_matrix"] = corr

        summary = "Computed Pearson correlation matrix for selected numeric variables."

    # ------------------------------------------------------------------
    # OLS regression
    # ------------------------------------------------------------------
    elif tool_name == "run_multiple_regression":
        target = arguments.get("target_col")
        features = arguments.get("feature_cols", [])
        feature_text = _safe_join_features(features)

        if target and feature_text:
            title = f"OLS Regression: {target} ~ {feature_text}"
        else:
            title = "OLS Regression"

        metrics = _compact_dict({
            "nobs": payload.get("nobs"),
            "r_squared": payload.get("r_squared"),
            "adj_r_squared": payload.get("adj_r_squared"),
            "f_statistic": payload.get("f_statistic"),
            "f_p_value": payload.get("f_p_value"),
            "aic": payload.get("aic"),
            "bic": payload.get("bic"),
            "df_model": payload.get("df_model"),
            "df_resid": payload.get("df_resid"),
            "n_eff": payload.get("n_eff"),
            "p_eff": payload.get("p_eff"),
        })

        coef_table = payload.get("coef_table", [])
        if coef_table:
            tables["coef_table"] = coef_table

        summary = "Fitted an OLS regression model."
        if target:
            summary += f" Outcome: `{target}`."
        if feature_text:
            summary += f" Predictors: `{feature_text}`."
        if payload.get("nobs") is not None:
            summary += f" n={payload.get('nobs')}."
        if payload.get("r_squared") is not None:
            summary += f" R²={payload.get('r_squared')}."

    # ------------------------------------------------------------------
    # Regression diagnostics
    # ------------------------------------------------------------------
    elif tool_name == "regression_diagnostics":
        title = "Regression Diagnostics"

        vif = payload.get("vif", [])
        bp = payload.get("breusch_pagan", {})

        vif_values = [
            row.get("vif")
            for row in vif
            if isinstance(row, dict) and row.get("vif") is not None
        ]

        metrics = _compact_dict({
            "max_vif": max(vif_values) if vif_values else None,
            "breusch_pagan_lm_statistic": bp.get("lm_statistic") if isinstance(bp, dict) else None,
            "breusch_pagan_lm_p_value": bp.get("lm_p_value") if isinstance(bp, dict) else None,
            "breusch_pagan_f_statistic": bp.get("f_statistic") if isinstance(bp, dict) else None,
            "breusch_pagan_f_p_value": bp.get("f_p_value") if isinstance(bp, dict) else None,
            "heteroscedasticity_flag_0_05": bp.get("heteroscedasticity_flag_0_05") if isinstance(bp, dict) else None,
        })

        if vif:
            tables["vif"] = vif
        if bp:
            tables["breusch_pagan"] = bp

        summary = "Computed multicollinearity and heteroscedasticity diagnostics."
        if metrics.get("max_vif") is not None:
            summary += f" Max VIF={metrics['max_vif']}."
        if metrics.get("breusch_pagan_lm_p_value") is not None:
            summary += f" Breusch-Pagan p={metrics['breusch_pagan_lm_p_value']}."

    # ------------------------------------------------------------------
    # Logistic regression
    # ------------------------------------------------------------------
    elif tool_name == "run_logistic_regression":
        target = arguments.get("target_col")
        features = arguments.get("feature_cols", [])
        feature_text = _safe_join_features(features)

        if target and feature_text:
            title = f"Logistic Regression: {target} ~ {feature_text}"
        else:
            title = "Logistic Regression"

        metrics = _compact_dict({
            "nobs": payload.get("nobs"),
            "pseudo_r_squared": payload.get("pseudo_r_squared"),
            "aic": payload.get("aic"),
            "bic": payload.get("bic"),
            "n_eff": payload.get("n_eff"),
            "p_eff": payload.get("p_eff"),
        })

        coef_table = payload.get("coef_table", [])
        if coef_table:
            tables["coef_table"] = coef_table

        summary = "Fitted a binary logistic regression model."
        if target:
            summary += f" Outcome: `{target}`."
        if feature_text:
            summary += f" Predictors: `{feature_text}`."

    # ------------------------------------------------------------------
    # Residual histogram
    # ------------------------------------------------------------------
    elif tool_name == "generate_residual_histogram":
        title = "Residual Histogram"

        diagnostic_flags = payload.get("diagnostic_flags", [])

        metrics = _compact_dict({
            "n_residuals": payload.get("n_residuals"),
            "residual_mean": payload.get("residual_mean"),
            "residual_std": payload.get("residual_std"),
            "residual_skewness": payload.get("residual_skewness"),
            "residual_kurtosis_fisher": payload.get("residual_kurtosis_fisher"),
            "outliers_abs_2sd": payload.get("outliers_abs_2sd"),
            "outliers_abs_3sd": payload.get("outliers_abs_3sd"),
            "diagnostic_flags": diagnostic_flags if diagnostic_flags else None,
        })

        summary = "Generated a residual histogram."
        if diagnostic_flags:
            summary += f" Diagnostic flags: {', '.join(str(x) for x in diagnostic_flags)}."

    # ------------------------------------------------------------------
    # Scatterplot
    # ------------------------------------------------------------------
    elif tool_name == "generate_scatterplot":
        x_col = arguments.get("x_column")
        y_col = arguments.get("y_column")

        if x_col and y_col:
            title = f"Scatterplot: {y_col} vs {x_col}"
        else:
            title = "Scatterplot"

        metrics = _compact_dict({
            "n_points": payload.get("n_points"),
        })

        summary = "Generated a scatterplot."

    # ------------------------------------------------------------------
    # Generic statistical tests
    # ------------------------------------------------------------------
    elif tool_name == "run_independent_t_test":
        title = "Independent t-test"

        metrics = _compact_dict({
            "t_statistic": payload.get("t_statistic"),
            "p_value": payload.get("p_value"),
            "group1_n": payload.get("group1_n"),
            "group1_mean": payload.get("group1_mean"),
            "group2_n": payload.get("group2_n"),
            "group2_mean": payload.get("group2_mean"),
            "significant_at_0_05": payload.get("significant_at_0_05"),
        })

        summary = "Completed Welch independent two-sample t-test."

    elif tool_name == "run_anova":
        title = "One-way ANOVA"

        metrics = _compact_dict({
            "F_statistic": payload.get("F_statistic"),
            "p_value": payload.get("p_value"),
            "valid_group_count": payload.get("valid_group_count"),
            "significant_at_0_05": payload.get("significant_at_0_05"),
        })

        summary = "Completed one-way ANOVA."

    elif tool_name == "run_chi_square":
        title = "Chi-square Test"

        metrics = _compact_dict({
            "chi2_statistic": payload.get("chi2_statistic"),
            "p_value": payload.get("p_value"),
            "degrees_of_freedom": payload.get("degrees_of_freedom"),
            "table_shape": payload.get("table_shape"),
            "significant_at_0_05": payload.get("significant_at_0_05"),
        })

        summary = "Completed chi-square test of independence."

    return {
        "run_id": f"run_{uuid.uuid4().hex[:8]}",
        "tool_name": tool_name,
        "action_id": action_id,
        "data_version_id": data_version_id,
        "status": status,
        "success": success,
        "created_at": utc_now_iso(),
        "title": title,
        "summary": summary,
        "arguments": arguments,
        "metrics": metrics,
        "tables": tables,
        "artifacts": artifacts,
        "raw_observation_id": observation_id,
    }