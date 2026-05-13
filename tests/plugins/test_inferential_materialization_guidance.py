from core.analysis_tool_plugins import get_plugin


def _plugin_text(plugin_name: str) -> str:
    plugin = get_plugin(plugin_name)
    assert plugin is not None

    parts = [
        getattr(plugin, "description", "") or "",
        getattr(plugin, "usage_guidance", "") or "",
        " ".join(getattr(plugin, "use_when", []) or []),
        " ".join(getattr(plugin, "do_not_use_when", []) or []),
    ]

    return " ".join(parts).lower()


def test_statistical_group_comparison_guidance_requires_observation_level_data():
    text = _plugin_text("statistical_group_comparison")

    assert "observation-level" in text or "observational unit" in text
    assert "not one row per group" in text or "one row per group" in text
    assert "not select region" in text or "group by region" in text or "sum(revenue)" in text


def test_materialize_sql_query_guidance_preserves_observational_unit_for_inference():
    text = _plugin_text("materialize_sql_query_result")

    assert "inferential" in text or "statistical" in text
    assert "observational unit" in text or "observation-level" in text
    assert "do not pre-aggregate" in text or "one row per group" in text