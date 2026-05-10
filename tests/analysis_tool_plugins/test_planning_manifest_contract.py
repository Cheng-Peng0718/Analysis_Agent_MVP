import pandas as pd

from core.analysis_tool_plugins import PLUGIN_REGISTRY, ensure_plugins_loaded
from core.analysis_tool_plugins.manifest import build_tool_manifests
from core.data.context_refresh import refresh_dataset_context_from_df


def _manifests():
    ensure_plugins_loaded()
    return build_tool_manifests(dict(PLUGIN_REGISTRY))


def _context(df):
    refreshed = refresh_dataset_context_from_df(
        df,
        dataset_name="student_data",
        data_version_id="raw_v1",
    )
    return refreshed.dataset_profile_v2, refreshed.capability_map


def test_registered_plugin_manifests_have_expected_deliverables_metadata():
    manifests = _manifests()

    tools_expected_to_have_deliverables = [
        "inspect_dataset",
        "missingness_report",
        "get_summary_stats",
        "summarize_columns",
        "get_correlation_matrix",
        "run_multiple_regression",
        "regression_diagnostics",
        "generate_residual_histogram",
        "run_correlation_test",
        "generate_scatterplot",
        "clean_data",
        "run_anova",
        "run_chi_square",
        "run_independent_t_test",
    ]

    for tool_name in tools_expected_to_have_deliverables:
        assert manifests[tool_name].expected_deliverables, tool_name


def test_manifest_exposes_task_argument_bindings_for_planner_contract():
    manifests = _manifests()

    expected_regression_bindings = [
        {
            "task_field": "target_variables",
            "index": 0,
            "argument": "target_col",
            "required_choice": "target_col",
        },
        {
            "task_field": "predictor_variables",
            "argument": "feature_cols",
            "required_choice": "feature_cols",
        },
    ]

    assert (
        manifests["run_multiple_regression"].task_argument_bindings
        == expected_regression_bindings
    )
    assert (
        manifests["regression_diagnostics"].task_argument_bindings
        == expected_regression_bindings
    )
    assert (
        manifests["generate_residual_histogram"].task_argument_bindings
        == expected_regression_bindings
    )

    assert manifests["run_correlation_test"].task_argument_bindings == [
        {
            "task_field": "predictor_variables",
            "index": 0,
            "argument": "x_col",
            "required_choice": "x_col",
        },
        {
            "task_field": "predictor_variables",
            "index": 1,
            "argument": "y_col",
            "required_choice": "y_col",
        },
    ]

    assert manifests["generate_scatterplot"].task_argument_bindings == [
        {
            "task_field": "predictor_variables",
            "index": 0,
            "argument": "x_column",
            "required_choice": "x_column",
        },
        {
            "task_field": "predictor_variables",
            "index": 1,
            "argument": "y_column",
            "required_choice": "y_column",
        },
    ]

    assert manifests["clean_data"].task_argument_bindings == [
        {
            "task_field": "target_variables",
            "argument": "columns",
            "required_choice": "columns",
        }
    ]
    assert manifests["clean_data"].required_planning_choices == [
        "action_type",
        "strategy",
    ]


def test_manifest_safety_metadata_matches_capability_map_safety():
    manifests = _manifests()
    _, capability_map = _context(pd.DataFrame({
        "GPA": [3.0, None, 3.8, 4.0],
        "SATM": [600, 620, 650, 700],
    }))

    capability_requires_confirmation = sorted(
        capability.tool_name
        for capability in capability_map.capabilities
        if capability.requires_confirmation
    )
    manifest_requires_confirmation = sorted(
        tool_name
        for tool_name, manifest in manifests.items()
        if manifest.requires_confirmation
    )
    capability_mutates_data = sorted(
        capability.tool_name
        for capability in capability_map.capabilities
        if capability.mutates_data
    )
    manifest_mutates_data = sorted(
        tool_name
        for tool_name, manifest in manifests.items()
        if manifest.mutates_data
    )

    assert capability_requires_confirmation == ["clean_data"]
    assert manifest_requires_confirmation == ["clean_data"]
    assert capability_mutates_data == ["clean_data"]
    assert manifest_mutates_data == ["clean_data"]

    for capability in capability_map.capabilities:
        manifest = manifests[capability.tool_name]
        assert manifest.requires_confirmation == capability.requires_confirmation
        assert manifest.mutates_data == capability.mutates_data