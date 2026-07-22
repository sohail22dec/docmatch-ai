from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .nodes import planner_node, medical_node, search_node, response_node


def _route_from_planner(state: AgentState) -> str:
    planner_decision = state.get("planner_decision") or {}
    capability = planner_decision.get("capability", "")

    if capability == "medical":
        return "medical_node"
    if capability == "search":
        return "search_node"
    return "response_node"


async def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("planner_node", planner_node)
    workflow.add_node("medical_node", medical_node)
    workflow.add_node("search_node", search_node)
    workflow.add_node("response_node", response_node)

    workflow.add_edge(START, "planner_node")

    workflow.add_conditional_edges(
        "planner_node",
        _route_from_planner,
        {
            "medical_node": "medical_node",
            "search_node": "search_node",
            "response_node": "response_node",
        },
    )

    workflow.add_edge("medical_node", "planner_node")
    workflow.add_edge("search_node", "planner_node")
    workflow.add_edge("response_node", END)

    return workflow.compile()
