from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from app.models.schemas import Doctor


class AgentState(TypedDict):
    """
    The state of our multi-agent system. This is the memory passed between nodes.
    """

    # The list of messages in the conversation. `add_messages` ensures new messages are appended, not overwritten.
    messages: Annotated[list[AnyMessage], add_messages]

    # Internal scratchpad for the triage agent to store notes on symptoms
    triage_notes: Optional[str]

    # List of doctors found during the current session
    found_doctors: Optional[List[Doctor]]

    # The final response to return to the user
    final_response: Optional[str]
