from pathlib import Path


def test_human_review_node_uses_action_and_verification_codecs():
    text = Path("core/graph.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )

    assert "from core.action_codec import action_to_state_dict" in text
    assert "from core.verification_codec import verification_to_state_dict" in text

    forbidden_patterns = [
        "source_action_id=action.action_id",
        "action.model_dump() if hasattr(action, \"model_dump\")",
        "vr.model_dump() if hasattr(vr, \"model_dump\")",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in text