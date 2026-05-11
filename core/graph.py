from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from core.state import GraphState

from core.workflow.routes import (
    route_after_intent as _route_after_intent,
    route_after_execute_pending_plan as _route_after_execute_pending_plan,
    route_after_supervisor as _route_after_supervisor,
    route_after_verify as _route_after_verify,
    route_after_review as _route_after_review,
    route_after_summarize as _route_after_summarize,
    route_after_deliverable_gate as _route_after_deliverable_gate,
)

from core.workflow.nodes.context import build_context_node as _build_context_node
from core.workflow.nodes.interaction import (
    intent_router_node as _intent_router_node,
    advisory_answer_node as _advisory_answer_node,
)
from core.workflow.nodes.planning import plan_only_node as _plan_only_node
from core.workflow.nodes.plan_execution import (
    execute_pending_plan_node as _execute_pending_plan_node,
)
from core.workflow.nodes.supervisor import supervisor_node as _supervisor_node
from core.workflow.nodes.finalization import (
    deliverable_gate_node as _deliverable_gate_node,
    final_response_node as _final_response_node,
)
from core.workflow.nodes.execution import execute_node as _execute_node
from core.workflow.nodes.summarization import summarize_node as _summarize_node
from core.workflow.nodes.human_review import human_review_node as _human_review_node
from core.workflow.nodes.verification import verify_node as _verify_node

__all__ = ["create_graph_app"]

_CHECKPOINTER = MemorySaver()
# --- Compile graph ---
workflow = StateGraph(GraphState)

workflow.add_node("build_context", _build_context_node)
workflow.add_node("intent_router", _intent_router_node)
workflow.add_node("advisory_answer", _advisory_answer_node)
workflow.add_node("plan_only", _plan_only_node)
workflow.add_node("execute_pending_plan", _execute_pending_plan_node)

workflow.add_node("supervisor", _supervisor_node)
workflow.add_node("verify", _verify_node)
workflow.add_node("human_review", _human_review_node)
workflow.add_node("execute", _execute_node)
workflow.add_node("summarize", _summarize_node)
workflow.add_node("deliverable_gate", _deliverable_gate_node)
workflow.add_node("final_response", _final_response_node)

workflow.set_entry_point("build_context")

# Step 1: build context, dataset profile, dataset summary, capability map.
workflow.add_edge("build_context", "intent_router")

# Step 2: route by interaction intent.
workflow.add_conditional_edges(
    "intent_router",
    _route_after_intent,
    {
        "advisory_answer": "advisory_answer",
        "plan_only": "plan_only",
        "execute_pending_plan": "execute_pending_plan",
        "supervisor": "supervisor",
        "end": END,
    },
)

# These modes must never execute tools.
workflow.add_edge("advisory_answer", END)
workflow.add_edge("plan_only", END)

workflow.add_conditional_edges(
    "execute_pending_plan",
    _route_after_execute_pending_plan,
    {
        "verify": "verify",
        "human_review": "human_review",
        "end": END,
    },
)

workflow.add_conditional_edges(
    "supervisor",
    _route_after_supervisor,
    {
        "verify": "verify",
        "deliverable_gate": "deliverable_gate",
        "end": END,
    }
)

workflow.add_conditional_edges(
    "deliverable_gate",
    _route_after_deliverable_gate,
    {
        "final_response": "final_response",
        "build_context": "build_context",
        "end": END,
    },
)

workflow.add_edge("final_response", END)

workflow.add_conditional_edges(
    "verify",
    _route_after_verify,
    {
        "execute": "execute",
        "human_review": "human_review",
        "build_context": "build_context",
        "end": END,
    },
)

workflow.add_conditional_edges(
    "human_review",
    _route_after_review,
    {
        "execute": "execute",
        "end": END,
    },
)

workflow.add_edge("execute", "summarize")

workflow.add_conditional_edges(
    "summarize",
    _route_after_summarize,
    {
        "build_context": "build_context",
        "end": END,
    },
)



def create_graph_app():
    """
    Build the compiled LangGraph app explicitly.

    Importing core.graph should expose workflow wiring, but should not compile
    a global runnable app as an import-time side effect.
    """
    return workflow.compile(
        checkpointer=_CHECKPOINTER,
        interrupt_before=["human_review"],
    )