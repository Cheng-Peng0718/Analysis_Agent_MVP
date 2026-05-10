import json
import sys

from core.analysis_tool_plugins import PLUGIN_REGISTRY, ensure_plugins_loaded
from core.analysis_tool_plugins.manifest import (
    ToolManifest,
    build_tool_manifest,
    build_tool_manifests,
)
from core.analysis_tool_plugins.planning_metadata import TOOL_PLANNING_METADATA


def _registered_plugins():
    ensure_plugins_loaded()
    return dict(PLUGIN_REGISTRY)


def _walk_values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
        return

    if isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
        return

    yield value


def test_every_registered_plugin_can_build_tool_manifest():
    plugins = _registered_plugins()

    manifests = build_tool_manifests(plugins)

    assert manifests
    assert set(manifests) == set(plugins)

    for tool_name, manifest in manifests.items():
        assert isinstance(manifest, ToolManifest)
        assert manifest.tool_name == tool_name
        assert manifest.display_name
        assert manifest.method_family
        assert isinstance(manifest.argument_schema, dict)
        assert isinstance(manifest.variable_roles, list)
        assert isinstance(manifest.planning_policy, dict)
        assert isinstance(manifest.versioning_policy, dict)
        assert isinstance(manifest.repair_policy, dict)
        assert isinstance(manifest.requires_confirmation, bool)
        assert isinstance(manifest.mutates_data, bool)
        if tool_name in TOOL_PLANNING_METADATA:
            assert manifest.planning_tags
            assert manifest.supported_goal_types
            assert manifest.default_plan_purpose
            assert manifest.expected_deliverables
        else:
            assert tool_name.startswith("unit_test_")

        assert isinstance(manifest.plan_order, int)
        assert manifest.argument_template == {}

        json.dumps(manifest.model_dump())


def test_tool_manifest_excludes_runtime_and_reporting_fields():
    manifest_fields = set(ToolManifest.model_fields)

    assert "execute" not in manifest_fields
    assert "extractor" not in manifest_fields
    assert "display_config" not in manifest_fields
    assert "guardrail_evaluators" not in manifest_fields
    assert "report_block_builder" not in manifest_fields
    assert "result_builder" not in manifest_fields

    manifest = build_tool_manifest(_registered_plugins()["run_multiple_regression"])
    dumped = manifest.model_dump()

    assert "execute" not in dumped
    assert "extractor" not in dumped
    assert "display_config" not in dumped
    assert "guardrail_evaluators" not in dumped
    assert "report_block_builder" not in dumped
    assert "result_builder" not in dumped

    assert not any(callable(value) for value in _walk_values(dumped))


def test_clean_data_manifest_preserves_mutation_safety_metadata():
    manifest = build_tool_manifest(_registered_plugins()["clean_data"])

    assert manifest.tool_name == "clean_data"
    assert manifest.mutates_data is True
    assert manifest.requires_confirmation is True
    assert "data_cleaning" in manifest.supported_goal_types
    assert "mutation" in manifest.planning_tags
    assert manifest.versioning_policy["mutates_data"] is True
    assert manifest.versioning_policy["must_create_child_version"] is True
    assert "action_type" in manifest.argument_schema["required"]
    assert "strategy" in manifest.argument_schema["required"]
    assert manifest.planning_policy["required_user_choices"] == [
        "action_type",
        "strategy",
    ]
    assert any(
        role["role_name"] == "columns"
        for role in manifest.variable_roles
    )


def test_known_planning_metadata_is_merged_into_manifest():
    manifests = build_tool_manifests(_registered_plugins())

    overview_tools = [
        "inspect_dataset",
        "missingness_report",
        "get_summary_stats",
    ]

    for tool_name in overview_tools:
        assert "dataset_overview" in manifests[tool_name].supported_goal_types

    assert "regression_modeling" in manifests["run_multiple_regression"].supported_goal_types
    assert "data_cleaning" in manifests["clean_data"].supported_goal_types

    assert (
        manifests["run_multiple_regression"].plan_order
        < manifests["regression_diagnostics"].plan_order
        < manifests["generate_residual_histogram"].plan_order
    )

    assert (
        "dataset_overview"
        in manifests["run_multiple_regression"].not_recommended_for_goal_types
    )


def test_manifest_generation_does_not_import_ui_or_workflow_nodes():
    before = set(sys.modules)

    build_tool_manifests(_registered_plugins())

    imported = set(sys.modules) - before
    forbidden = [
        name
        for name in imported
        if name == "core.ui_adapter"
        or name.startswith("core.ui_adapter.")
        or name == "core.workflow"
        or name.startswith("core.workflow.")
    ]

    assert forbidden == []
