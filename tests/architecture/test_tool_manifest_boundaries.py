from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_tool_manifest_does_not_import_ui_workflow_or_runtime_builders():
    text = _read("core/analysis_tool_plugins/manifest.py")

    forbidden_terms = [
        "core.ui_adapter",
        "core.workflow",
        "core.analysis_tool_plugins.execution",
        "core.analysis_tool_plugins.reporting",
        "core.analysis_tool_plugins.result_builder",
        "core.analysis_tool_plugins.display",
        "execute_analysis_tool",
        "build_analysis_run_for_plugin",
        "build_generic_report_blocks",
        "DisplayConfig",
    ]

    violations = [term for term in forbidden_terms if term in text]

    assert violations == []


def test_tool_planning_metadata_does_not_import_runtime_or_plugins():
    text = _read("core/analysis_tool_plugins/planning_metadata.py")

    forbidden_terms = [
        "AnalysisToolPlugin",
        "PLUGIN_REGISTRY",
        "register_plugin",
        "core.services.intelligent_planner",
        "core.workflow",
        "core.ui_adapter",
        "execute",
        "extractor",
        "display_config",
        "guardrail_evaluators",
        "result_builder",
        "reporting",
    ]

    violations = [term for term in forbidden_terms if term in text]

    assert violations == []


def test_tool_manifest_contract_excludes_runtime_and_reporting_fields():
    from core.analysis_tool_plugins.manifest import ToolManifest

    manifest_fields = set(ToolManifest.model_fields)

    forbidden_fields = {
        "execute",
        "extractor",
        "display_config",
        "guardrail_evaluators",
        "report_block_builder",
        "result_builder",
    }

    assert manifest_fields.isdisjoint(forbidden_fields)


def test_analysis_plugin_base_does_not_absorb_manifest_or_builder_logic():
    text = _read("core/analysis_tool_plugins/base.py")

    forbidden_terms = [
        "ToolManifest",
        "build_tool_manifest",
        "build_tool_manifests",
        "core.analysis_tool_plugins.manifest",
        "core.analysis_tool_plugins.result_builder",
        "core.analysis_tool_plugins.reporting",
        "build_analysis_run_for_plugin",
        "build_generic_report_blocks",
        "default_extractor",
    ]

    violations = [term for term in forbidden_terms if term in text]

    assert violations == []


def test_planner_reads_manifest_view_but_not_planning_metadata_or_runtime():
    text = _read("core/services/intelligent_planner.py")

    assert "build_tool_manifest" in text

    forbidden_terms = [
        "TOOL_PLANNING_METADATA",
        "core.analysis_tool_plugins.planning_metadata",
        "core.ui_adapter",
        "core.workflow",
        "execute_analysis_tool",
        "execute_node",
        "core.analysis_tool_plugins.execution",
    ]

    violations = [term for term in forbidden_terms if term in text]

    assert violations == []
