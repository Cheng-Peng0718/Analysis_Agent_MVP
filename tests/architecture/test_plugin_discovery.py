from core.analysis_plugins import PLUGIN_REGISTRY, get_plugin


def test_core_plugins_are_auto_discovered():
    expected_plugins = {
        "get_summary_stats",
        "run_multiple_regression",
        "regression_diagnostics",
        "generate_residual_histogram",
    }

    missing = expected_plugins - set(PLUGIN_REGISTRY.keys())

    assert not missing, (
        f"Expected core plugins to be auto-discovered, but missing: {missing}"
    )


def test_unknown_tool_falls_back_to_generic_plugin():
    plugin = get_plugin("unknown_tool_demo")

    run = plugin.build_analysis_run(
        action_id="act_test",
        arguments={},
        data_version_id="raw_v1",
        status="ok",
        success=True,
        message="Fallback test.",
        payload={"hello": "world"},
        artifacts=[],
        observation_id="obs_test",
    )

    assert run["tool_name"] == "unknown_tool_demo"
    assert run["title"] == "Unknown Tool Demo"
    assert run["status"] == "ok"
    assert run["report_blocks"], "Fallback plugin should still produce report blocks."