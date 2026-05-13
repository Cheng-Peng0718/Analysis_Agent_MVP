import pandas as pd

from core.analysis_tool_plugins import get_plugin


class DummyContext:
    def __init__(self, df, args=None, analysis_runs=None):
        self.df = df
        self.args = args or {}
        self.arguments = self.args
        self.analysis_runs = analysis_runs or []
        self.active_data_version_id = "data_v_test"

    def load_df(self):
        return self.df

    def get_arg(self, key, default=None):
        return self.args.get(key, default)


def test_regression_diagnostics_unified_execute_and_analysis_run():
    plugin = get_plugin("regression_diagnostics")

    assert plugin is not None
    assert plugin.execute is not None

    df = pd.DataFrame({
        "y": [1, 2, 3, 4, 5, 6, 7, 8],
        "x": [2, 4, 6, 8, 10, 12, 14, 16],
    })

    raw = plugin.run(DummyContext(
        df,
        {
            "target_col": "y",
            "feature_cols": ["x"],
            "min_n_per_parameter": 1,
        },
    ))

    assert raw["status"] in {"ok", "warning"}
    assert "vif" in raw["details"]
    assert "breusch_pagan" in raw["details"]
    assert raw["details"]["p_eff"] == 1

    run = plugin.build_analysis_run(
        action_id="act_test",
        arguments={
            "target_col": "y",
            "feature_cols": ["x"],
            "min_n_per_parameter": 1,
        },
        data_version_id="raw_v1",
        status=raw["status"],
        success=True,
        message=raw["message"],
        payload=raw["details"],
        artifacts=raw.get("artifacts", []),
        observation_id="obs_test",
    )

    assert run["tool_name"] == "regression_diagnostics"
    assert run["title"] == "Model Diagnostics"

    assert "max_vif" in run["metrics"]
    assert "breusch_pagan_lm_p_value" in run["metrics"]
    assert "heteroscedasticity_flag_0_05" in run["metrics"]

    assert "vif" in run["tables"]

    # Raw BP dict should be metadata, not a report table.
    assert "breusch_pagan" not in run["tables"]
    assert "breusch_pagan" in run["metadata"]

    metric_block = next(
        block for block in run["report_blocks"]
        if block["type"] == "metric_table"
    )

    labels = [row["label"] for row in metric_block["rows"]]

    assert "Maximum VIF" in labels
    assert "Breusch-Pagan LM p-value" in labels
    assert "Heteroscedasticity flag" in labels

    table_block = next(
        block for block in run["report_blocks"]
        if block["type"] == "table"
    )

    table_labels = [col["label"] for col in table_block["columns"]]

    assert "Term" in table_labels
    assert "VIF" in table_labels
    assert "High VIF flag" in table_labels


def test_regression_diagnostics_blocks_missing_feature_column():
    plugin = get_plugin("regression_diagnostics")

    df = pd.DataFrame({
        "y": [1, 2, 3],
        "x": [1, 2, 3],
    })

    raw = plugin.run(DummyContext(
        df,
        {
            "target_col": "y",
            "feature_cols": ["z"],
        },
    ))

    assert raw["status"] == "blocked"
    assert raw["error_code"] == "COLUMNS_NOT_FOUND"

def test_regression_diagnostics_uses_latest_regression_model_spec_for_encoded_terms():
    linear_plugin = get_plugin("run_multiple_regression")
    diagnostics_plugin = get_plugin("regression_diagnostics")

    assert linear_plugin is not None
    assert diagnostics_plugin is not None

    df = pd.DataFrame({
        "total_revenue": [
            100, 120, 130, 150,
            180, 200, 210, 220,
            90, 95, 105, 110,
            160, 170, 175, 185,
        ],
        "number_of_orders": [
            1, 2, 2, 3,
            3, 4, 4, 5,
            1, 1, 2, 2,
            2, 3, 3, 4,
        ],
        "region": [
            "East", "East", "East", "East",
            "North", "North", "North", "North",
            "South", "South", "South", "South",
            "West", "West", "West", "West",
        ],
        "segment": [
            "Consumer", "Consumer", "Consumer", "Consumer",
            "Corporate", "Corporate", "Corporate", "Corporate",
            "Consumer", "Consumer", "Consumer", "Consumer",
            "Small Business", "Small Business", "Small Business", "Small Business",
        ],
    })

    linear_args = {
        "target_col": "total_revenue",
        "feature_cols": ["number_of_orders", "region", "segment"],
        "min_n_per_parameter": 1,
    }

    linear_raw = linear_plugin.run(
        DummyContext(df, linear_args)
    )

    assert linear_raw["status"] in {"ok", "warning"}
    assert "model_spec" in linear_raw["details"]

    linear_run = linear_plugin.build_analysis_run(
        action_id="act_regression",
        arguments=linear_args,
        data_version_id="data_v_test",
        status=linear_raw["status"],
        success=True,
        message=linear_raw["message"],
        payload=linear_raw["details"],
        artifacts=linear_raw.get("artifacts", []),
        observation_id="obs_regression",
    )

    assert "model_spec" in linear_run["metadata"]
    assert linear_run["metadata"]["model_spec"]["original_feature_cols"] == [
        "number_of_orders",
        "region",
        "segment",
    ]

    diagnostics_raw = diagnostics_plugin.run(
        DummyContext(
            df,
            {
                "target_col": "total_revenue",
                "feature_cols": [
                    "number_of_orders",
                    "region_North",
                    "region_South",
                    "region_West",
                    "segment_Corporate",
                    "segment_Small Business",
                ],
                "min_n_per_parameter": 1,
            },
            analysis_runs=[linear_run],
        )
    )

    assert diagnostics_raw["status"] in {"ok", "warning"}
    assert diagnostics_raw["details"]["resolved_from_model_spec"] is True
    assert diagnostics_raw["details"]["explicit_feature_cols"] == [
        "number_of_orders",
        "region_North",
        "region_South",
        "region_West",
        "segment_Corporate",
        "segment_Small Business",
    ]
    assert diagnostics_raw["details"]["raw_feature_count"] == 3
    assert diagnostics_raw["details"]["target"] == "total_revenue"
    assert "vif" in diagnostics_raw["details"]