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
    
    # User ID from auth
    user_id: Optional[str]

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

    # --- Booking Agent fields ---
    selected_clinic: Optional[dict]   # The clinic the user chose to book
    current_booking: Optional[dict]   # Stores {patient_name, appointment_date, time_slot}
    booking_confirmed: Optional[bool] # True after database save
    booking_id: Optional[str]        # Human-readable ID e.g. "APT-47291"

    # --- UI Actions ---
    action_required: Optional[str]    # Special signals sent back to the frontend (e.g. "request_location")
    
    # --- Google Calendar ---
    google_calendar_token: Optional[str]  # Patient's Google OAuth access token (if signed in with Google)

    # --- Internal Routing ---
    next: Optional[str]               # Used by orchestrator to signal next agent

