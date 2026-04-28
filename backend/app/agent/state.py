from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    """
    The shared memory passed between all agents in the multi-agent system.
    Every field is Optional so nodes can safely check for missing data.
    """

    # Full conversation history — add_messages appends, never overwrites
    messages: Annotated[list[AnyMessage], add_messages]

    # --- Symptom Agent outputs ---
    symptoms: Optional[str]           # Raw symptom text extracted from user message
    specialty_needed: Optional[str]   # e.g. "Dermatologist", "Cardiologist"

    # --- Location Agent inputs/outputs ---
    latitude: Optional[float]         # From frontend GPS (None if denied)
    longitude: Optional[float]        # From frontend GPS (None if denied)
    city: Optional[str]               # Typed by user if GPS denied
    location_source: Optional[str]    # "gps" | "user_typed" | "none"
    location_denied: Optional[bool]   # True if user denied browser permission

    # --- Search Agent outputs ---
    clinics_found: Optional[list]     # Raw results list; None = not searched yet, [] = searched + empty
    search_attempted: Optional[bool]  # Prevents infinite retry loops

    # --- Formatter Agent outputs ---
    final_response: Optional[str]     # Formatted message ready to return to the user

    # --- Orchestrator routing ---
    next: Optional[str]               # Routing key set by orchestrator: "symptom_agent" | "location_agent" | etc.

    # --- UI Actions ---
    action_required: Optional[str]    # Special signals sent back to the frontend (e.g. "request_location")
