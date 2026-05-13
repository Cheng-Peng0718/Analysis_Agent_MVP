from pathlib import Path

import pandas as pd

from core.analysis_tool_plugins import get_plugin
from core.analysis_tool_plugins.registry import get_tool_specs_for_llm


class DummyContext:
    def __init__(self, arguments, workspace_dir, data_versions, active_data_version_id):
        self.arguments = arguments
        self.args = arguments
        self.workspace_dir = str(workspace_dir)
        self.data_versions = data_versions
        self.active_data_version_id = active_data_version_id
        self.data_audit_log = []


def _make_active_dataset(tmp_path: Path):
    df = pd.DataFrame(
        {
            "customer_id": list(range(1, 13)),
            "region": ["East"] * 4 + ["West"] * 4 + ["South"] * 4,
            "segment": ["Consumer"] * 6 + ["Corporate"] * 6,
            "total_revenue": [100, 110, 120, 130, 200, 210, 220, 230, 300, 310, 320, 330],
            "number_of_orders": [1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7],
        }
    )

    path = tmp_path / "active.parquet"
    df.to_parquet(path, index=False)

    version = {
        "version_id": "data_v_test",
        "parent_version_id": None,
        "path": str(path),
        "n_rows": int(df.shape[0]),
        "n_cols": int(df.shape[1]),
        "operation": "test_dataset",
    }

    return [version], "data_v_test"


def test_statistical_group_comparison_registered():
    plugin = get_plugin("statistical_group_comparison")

    assert plugin is not None
    assert plugin.tool_name == "statistical_group_comparison"
    assert plugin.requires_data_source == "dataframe"

    specs = get_tool_specs_for_llm()

    assert "statistical_group_comparison" in specs
    assert specs["statistical_group_comparison"]["argument_schema"]["required"]["target_col"] == "str"
    assert specs["statistical_group_comparison"]["argument_schema"]["required"]["group_col"] == "str"


def test_statistical_group_comparison_runs_anova_for_three_groups(tmp_path):
    plugin = get_plugin("statistical_group_comparison")
    assert plugin is not None

    data_versions, active_id = _make_active_dataset(tmp_path)

    result = plugin.run(
        DummyContext(
            {
                "target_col": "total_revenue",
                "group_col": "region",
            },
            tmp_path,
            data_versions,
            active_id,
        )
    )

    assert result["status"] == "ok"

    details = result["details"]

    assert details["method"] == "One-way ANOVA"
    assert details["valid_group_count"] == 3
    assert details["top_group"] == "South"
    assert details["lowest_group"] == "East"
    assert details["p_value"] is not None
    assert details["eta_squared"] is not None
    assert details["effect_size_name"] == "eta squared"
    assert details["assumptions_and_limitations"]


def test_statistical_group_comparison_runs_welch_for_two_groups(tmp_path):
    plugin = get_plugin("statistical_group_comparison")
    assert plugin is not None

    data_versions, active_id = _make_active_dataset(tmp_path)

    result = plugin.run(
        DummyContext(
            {
                "target_col": "total_revenue",
                "group_col": "segment",
            },
            tmp_path,
            data_versions,
            active_id,
        )
    )

    assert result["status"] == "ok"

    details = result["details"]

    assert details["method"] == "Welch independent two-sample t-test"
    assert details["valid_group_count"] == 2
    assert details["t_statistic"] is not None
    assert details["effect_size_name"] == "Hedges g"
    assert details["effect_size"] is not None


def test_statistical_group_comparison_blocks_missing_column(tmp_path):
    plugin = get_plugin("statistical_group_comparison")
    assert plugin is not None

    data_versions, active_id = _make_active_dataset(tmp_path)

    result = plugin.run(
        DummyContext(
            {
                "target_col": "bad_revenue",
                "group_col": "region",
            },
            tmp_path,
            data_versions,
            active_id,
        )
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "COLUMN_NOT_FOUND"


def test_statistical_group_comparison_builds_analysis_run(tmp_path):
    plugin = get_plugin("statistical_group_comparison")
    assert plugin is not None

    data_versions, active_id = _make_active_dataset(tmp_path)

    arguments = {
        "target_col": "total_revenue",
        "group_col": "region",
    }

    raw = plugin.run(
        DummyContext(
            arguments,
            tmp_path,
            data_versions,
            active_id,
        )
    )

    run = plugin.build_analysis_run(
        action_id="act_test",
        arguments=arguments,
        data_version_id=active_id,
        status=raw["status"],
        success=True,
        message=raw["message"],
        payload=raw["details"],
        artifacts=raw.get("artifacts", []),
        observation_id="obs_test",
    )

    assert run["tool_name"] == "statistical_group_comparison"
    assert run["title"] == "Statistical Group Comparison: total_revenue by region"
    assert run["metrics"]["method"] == "One-way ANOVA"
    assert "group_summaries" in run["tables"]
    assert "assumptions_and_limitations" in run["tables"]
    assert run["report_blocks"]