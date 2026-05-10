from core.analysis_tool_plugins import PLUGIN_REGISTRY, ensure_plugins_loaded
from core.analysis_tool_plugins.manifest import build_tool_manifests
from core.analysis_tool_plugins.planning_metadata import TOOL_PLANNING_METADATA


def _registered_plugins():
    ensure_plugins_loaded()
    return dict(PLUGIN_REGISTRY)


def test_planning_metadata_keys_match_registered_plugins():
    plugins = _registered_plugins()

    assert set(TOOL_PLANNING_METADATA).issubset(set(plugins))

    plugins_without_overlay = set(plugins) - set(TOOL_PLANNING_METADATA)

    assert all(
        tool_name.startswith("unit_test_")
        for tool_name in plugins_without_overlay
    )


def test_every_planning_metadata_entry_has_required_fields():
    for tool_name, metadata in TOOL_PLANNING_METADATA.items():
        assert metadata["planning_tags"], tool_name
        assert metadata["supported_goal_types"], tool_name
        assert metadata["default_plan_purpose"], tool_name
        assert metadata["expected_deliverables"], tool_name
        assert isinstance(metadata["plan_order"], int), tool_name
        assert "argument_template" not in metadata
        assert "execute" not in metadata
        assert "extractor" not in metadata
        assert "display_config" not in metadata
        assert "guardrail_evaluators" not in metadata


def test_manifest_goal_type_queries_can_identify_existing_tool_groups():
    manifests = build_tool_manifests(_registered_plugins())

    overview_tools = {
        name
        for name, manifest in manifests.items()
        if "dataset_overview" in manifest.supported_goal_types
    }
    regression_tools = sorted(
        [
            manifest
            for manifest in manifests.values()
            if "regression_modeling" in manifest.supported_goal_types
        ],
        key=lambda manifest: manifest.plan_order,
    )
    cleaning_tools = {
        name
        for name, manifest in manifests.items()
        if "data_cleaning" in manifest.supported_goal_types
    }

    assert {
        "inspect_dataset",
        "missingness_report",
        "get_summary_stats",
    }.issubset(overview_tools)

    assert [
        manifest.tool_name
        for manifest in regression_tools
    ] == [
        "run_multiple_regression",
        "regression_diagnostics",
        "generate_residual_histogram",
    ]

    assert cleaning_tools == {"clean_data"}
