from pathlib import Path


def test_planning_contracts_do_not_reference_central_metadata_fallback():
    text = Path("core/analysis_tool_plugins/planning_contracts.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "central fallback",
        "central planning",
        "TOOL_PLANNING_METADATA",
        "planning_metadata.py",
    ]

    for phrase in forbidden:
        assert phrase not in text


def test_planning_contract_documents_manifest_default_plan_order():
    text = Path("core/analysis_tool_plugins/planning_contracts.py").read_text(
        encoding="utf-8"
    )

    assert "ToolManifest normalizes it to 100" in text