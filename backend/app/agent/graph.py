from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from app.agent.state import AgentState
from app.agent.nodes import make_triage_node
from app.core.tools import get_mcp_tools


async def build_medical_graph():
    """
    Builds and compiles the LangGraph.
    It is an async function because we need to fetch the MCP tools
    from the external servers before wiring the graph.
    """
    # 1. Fetch the tools dynamically from our MCP Server
    tools = await get_mcp_tools()

    # 2. Create the LangGraph ToolNode
    # This node automatically executes the tools if the LLM requests them.
    tool_node = ToolNode(tools)

    # 3. Initialize the Graph with our State
    workflow = StateGraph(AgentState)

    # 4. Add the nodes
    triage_node = make_triage_node(tools)
    workflow.add_node("triage", triage_node)
    workflow.add_node("tools", tool_node)

    # 5. Wire the edges
    # Start -> Triage
    workflow.add_edge(START, "triage")

    # Triage -> conditionally go to 'tools' or END
    # The `tools_condition` function automatically checks if the LLM returned a tool call.
    # If yes -> "tools". If no -> END.
    workflow.add_conditional_edges(
        "triage", tools_condition, {"tools": "tools", END: END}
    )

    # Tools -> Triage
    # After tools execute, return to triage so it can summarize the tool output
    workflow.add_edge("tools", "triage")

    # 6. Compile the graph!
    return workflow.compile()
