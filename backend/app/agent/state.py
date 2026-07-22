from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    # Full conversation history.
    # LangGraph add_messages reducer appends — never overwrites.
    messages: Annotated[list[AnyMessage], add_messages]

    # Serialised PlannerState (model_dump()).
    # Read by planner_node. Updated by each capability node that
    # produces a planning-relevant signal (e.g. specialty_known=True).
    planner_state: dict

    # Serialised PlannerDecision (model_dump()).
    # Written by planner_node. Read by the graph router and response_node.
    planner_decision: Optional[dict]

    # Serialised MedicalDecision (model_dump()).
    # Written by medical_node. Read by response_node.
    medical_decision: Optional[dict]

    # Serialised list of Clinic objects (model_dump()).
    # Written by search_node. Read by response_node.
    search_results: Optional[list[dict]]

    # Most recent clinic results restored from the session.
    # Read by clinic_selection_node; not rendered as a fresh search response.
    previous_search_results: Optional[list[dict]]

    # Clinic selected explicitly by the client, e.g. via a search result card.
    selected_clinic_request: Optional[dict]

    # Final user-facing text. Written by response_node. Read by the API.
    final_response: Optional[str]

    # Explicit workflow signal for capability chaining (e.g. 'search', 'response').
    next_capability: Optional[str]

    # Booking payload & result for graph-triggered booking capability
    booking_request: Optional[dict]
    booking_result: Optional[dict]

    # Explicit frontend client action (e.g. 'request_current_location')
    action: Optional[str]
