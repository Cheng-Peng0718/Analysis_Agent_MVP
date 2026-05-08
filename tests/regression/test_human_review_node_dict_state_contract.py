from core.graph import human_review_node


def test_human_review_node_accepts_dict_action_and_dict_verification_for_needs_review():
    state = {
        "current_action": {
            "action_id": "act_1",
            "action_type": "tool_call",
            "tool_name": "clean_data",
            "arguments": {
                "action_type": "drop",
                "strategy": "rows",
                "columns": ["GPA"],
            },
            "reasoning_summary": "Drop missing GPA rows.",
        },
        "current_verification": {
            "action_id": "act_1",
            "status": "needs_review",
            "feedback": "Cleaning data requires confirmation.",
            "error_code": None,
            "details": {
                "action_hash": "hash_1",
                "canonical_arguments": {
                    "action_type": "drop",
                    "strategy": "rows",
                    "columns": ["GPA"],
                },
            },
        },
        "human_review_decision": None,
    }

    updates = human_review_node(state)

    assert updates["human_review_required"] is True
    assert isinstance(updates["pending_action"], dict)
    assert updates["pending_action"]["action_id"] == "act_1"

    obs = updates["observations"][0]
    assert obs["source_action_id"] == "act_1"
    assert obs["tool_name"] == "clean_data"
    assert obs["structured_data"]["pending_action"]["action_id"] == "act_1"
    assert obs["raw_data"]["verification"]["status"] == "needs_review"


def test_human_review_node_accepts_dict_action_and_dict_verification_for_rejection():
    state = {
        "current_action": {
            "action_id": "act_2",
            "action_type": "tool_call",
            "tool_name": "run_multiple_regression",
            "arguments": {},
            "reasoning_summary": "Run regression.",
        },
        "current_verification": {
            "action_id": "act_2",
            "status": "rejected_recoverable",
            "feedback": "Missing required arguments.",
            "error_code": "SCHEMA_VALIDATION_FAILED",
            "details": {},
        },
        "human_review_decision": None,
    }

    updates = human_review_node(state)

    obs = updates["observations"][0]
    assert obs["source_action_id"] == "act_2"
    assert obs["tool_name"] == "run_multiple_regression"
    assert obs["raw_data"]["verification"]["status"] == "rejected_recoverable"