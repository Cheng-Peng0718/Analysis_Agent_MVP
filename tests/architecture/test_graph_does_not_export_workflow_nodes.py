import core.graph as graph


def test_core_graph_only_exports_create_graph_app_as_public_api():
    assert graph.__all__ == ["create_graph_app"]

    public_node_names = [
        "build_context_node",
        "intent_router_node",
        "advisory_answer_node",
        "plan_only_node",
        "execute_pending_plan_node",
        "supervisor_node",
        "verify_node",
        "human_review_node",
        "execute_node",
        "summarize_node",
        "deliverable_gate_node",
        "final_response_node",
    ]

    public_route_names = [
        "route_after_intent",
        "route_after_execute_pending_plan",
        "route_after_supervisor",
        "route_after_verify",
        "route_after_review",
        "route_after_summarize",
        "route_after_deliverable_gate",
    ]

    for name in public_node_names + public_route_names:
        assert not hasattr(graph, name), f"core.graph should not export {name}"