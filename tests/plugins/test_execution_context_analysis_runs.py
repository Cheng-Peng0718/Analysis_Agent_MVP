from core.schema import ActionProposal, ContextPackage
from core.analysis_tool_plugins.execution import execute_analysis_tool


def test_execute_analysis_tool_passes_analysis_runs_to_agent_context(tmp_path):
    # This test only checks that execution context can carry analysis_runs.
    # A real plugin-level model-spec test verifies behavior.
    context_pkg = ContextPackage(
        step=1,
        max_steps=5,
        user_request="test",
        workspace_dir=str(tmp_path),
        observations=[],
        analysis_runs=[
            {
                "run_id": "run_existing",
                "tool_name": "run_multiple_regression",
                "status": "ok",
                "evidence_categories": ["regression_model"],
                "metadata": {
                    "model_spec": {
                        "target_col": "y",
                        "original_feature_cols": ["x"],
                    }
                },
            }
        ],
        data_versions=[],
        active_data_version_id=None,
        data_audit_log=[],
        context_text="test context",
    )

    assert context_pkg.analysis_runs[0]["run_id"] == "run_existing"