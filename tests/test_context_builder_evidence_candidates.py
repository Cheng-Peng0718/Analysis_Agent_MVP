from core.context_builder import build_context


def test_context_builder_lists_candidate_tools_for_missing_evidence():
    context = build_context(
        step=1,
        max_steps=10,
        user_request="Analyze data end to end.",
        profile={},
        observations=[],
        workspace_dir="./",
        deliverable_check={
            "gate_type": "answer_quality_gate",
            "status": "ok",
            "quality_status": "needs_attention",
            "message": "Missing required evidence.",
            "continuation_recommended": True,
            "available_evidence_categories": ["data_quality"],
            "covered_evidence_categories": [],
            "missing_evidence_categories": ["data_quality"],
            "missing_evidence_requirements": [
                {
                    "evidence_category": "data_quality",
                    "required_count": 1,
                    "covered_count": 0,
                    "missing_count": 1,
                }
            ],
            "warnings": [],
        },
        data_versions=[],
        active_data_version_id=None,
        data_audit_log=[],
        analysis_coverage_brief={
            "analysis_goal": "test",
            "required_evidence_categories": ["data_quality"],
            "required_evidence_counts": {"data_quality": 1},
            "optional_evidence_categories": [],
            "autonomy_level": "continue_until_covered",
            "reasoning_summary": "Need data quality evidence.",
        },
        analysis_runs=[],
    )

    text = context.context_text

    assert "CONTINUE_ANALYSIS_RECOMMENDED: true" in text
    assert "candidate_tools_for_missing_evidence" in text
    assert "data_quality" in text
    assert "missingness_report" in text