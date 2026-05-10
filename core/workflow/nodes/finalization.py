from __future__ import annotations

from core.deliverables.gate import evaluate_deliverable_gate_state
from core.deliverables.evidence import extract_final_answer_content_from_state
from core.responses import make_response_update


def _deliverable_metadata(state: dict, extra: dict | None = None) -> dict:
    deliverable_check = state.get("deliverable_check") or {}

    metadata = {
        "deliverable_check": deliverable_check,
        "deliverable_status": deliverable_check.get("status"),
        "satisfied_deliverables": deliverable_check.get("satisfied", []),
        "missing_deliverables": deliverable_check.get("missing", []),
        "blocked_deliverables": deliverable_check.get("blocked", []),
    }

    if extra:
        metadata.update(extra)

    return metadata


def final_response_node(state: dict):
    """
    Convert a deliverable-gate-approved final answer into assistant_response.

    DeliverableGate remains the quality gate.
    This node is only the output-envelope adapter.
    """
    content = extract_final_answer_content_from_state(state)

    if not content:
        content = (
            "The final answer passed the deliverable gate, but no final-answer "
            "content could be extracted from the current graph state."
        )

        updates = make_response_update(
            response_type="error",
            content=content,
            source_node="final_response",
            data_version_id=state.get("active_data_version_id"),
            metadata=_deliverable_metadata(
                state,
                extra={"reason": "missing_final_answer_content"},
            ),
        )

        updates.update({
            "current_action": None,
            "current_execution": None,
            "current_verification": None,
        })

        return updates

    updates = make_response_update(
        response_type="final_answer",
        content=content,
        source_node="final_response",
        data_version_id=state.get("active_data_version_id"),
        metadata=_deliverable_metadata(state),
    )

    updates.update({
        "current_action": None,
        "current_execution": None,
        "current_verification": None,
    })

    return updates


def deliverable_gate_node(state: dict):
    result = evaluate_deliverable_gate_state(state)

    deliverable_check = result.model_dump()

    print("\n" + "=" * 40)
    print("[DELIVERABLE GATE]")
    print(deliverable_check)
    print("=" * 40 + "\n")

    return {
        "deliverable_check": deliverable_check,
    }
