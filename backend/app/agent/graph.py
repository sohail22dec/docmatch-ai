from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes import (
    orchestrator_node,
    symptom_agent,
    location_agent,
    search_agent,
    formatter_agent,
    booking_agent,
    confirmation_agent,
)


def route_from_orchestrator(state: AgentState) -> str:
    """Reads the 'next' key set by the orchestrator and returns it as a routing string."""
    next_node = state.get("next")
    return next_node or END


async def build_medical_graph():
    """
    Builds and compiles the multi-agent LangGraph.
    """
    workflow = StateGraph(AgentState)

    # Register all nodes
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("symptom_agent", symptom_agent)
    workflow.add_node("location_agent", location_agent)
    workflow.add_node("search_agent", search_agent)
    workflow.add_node("formatter_agent", formatter_agent)
    workflow.add_node("booking_agent", booking_agent)
    workflow.add_node("confirmation_agent", confirmation_agent)

    # Entry point
    workflow.add_edge(START, "orchestrator")

    # Orchestrator routes conditionally based on state.next
    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "symptom_agent": "symptom_agent",
            "location_agent": "location_agent",
            "search_agent": "search_agent",
            "formatter_agent": "formatter_agent",
            "booking_agent": "booking_agent",
            "confirmation_agent": "confirmation_agent",
            END: END,
        },
    )

    # All sub-agents loop back to the orchestrator
    workflow.add_edge("symptom_agent", "orchestrator")
    workflow.add_edge("location_agent", "orchestrator")
    workflow.add_edge("search_agent", "orchestrator")
    workflow.add_edge("formatter_agent", "orchestrator")
    workflow.add_edge("booking_agent", "orchestrator")
    workflow.add_edge("confirmation_agent", "orchestrator")

    return workflow.compile()
