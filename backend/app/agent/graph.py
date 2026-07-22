from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes import (
    clinic_selection_node,
    planner_node,
    medical_node,
    search_node,
    booking_node,
    response_node,
)


def _route_from_planner(state: AgentState) -> str:
    planner_decision = state.get("planner_decision") or {}
    capability = planner_decision.get("capability", "")

    if capability == "medical":
        return "medical_node"
    if capability == "search":
        return "search_node"
    if capability == "booking":
        return "booking_node"
    return "response_node"


async def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("clinic_selection_node", clinic_selection_node)
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("medical_node", medical_node)
    workflow.add_node("search_node", search_node)
    workflow.add_node("booking_node", booking_node)
    workflow.add_node("response_node", response_node)

    # 1. Entry point
    workflow.add_edge(START, "clinic_selection_node")
    workflow.add_edge("clinic_selection_node", "planner_node")

    # 2. Planner conditional routing
    workflow.add_conditional_edges(
        "planner_node",
        _route_from_planner,
        {
            "medical_node": "medical_node",
            "search_node": "search_node",
            "booking_node": "booking_node",
            "response_node": "response_node",
        },
    )

    # 3. Information-gathering capabilities loop back for re-evaluation.
    workflow.add_edge("medical_node", "planner_node")
    workflow.add_edge("search_node", "planner_node")
    workflow.add_edge("booking_node", "response_node")

    # 4. Response node terminates the graph
    workflow.add_edge("response_node", END)

    return workflow.compile()
