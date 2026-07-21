"""
state.py — Application state for DocMatch.

This is NOT PlannerState. This is NOT MedicalDecision.
This is the data bag that flows through the LangGraph.

Fields are kept minimal — only what the three nodes (planner, medical,
response) actually need. No booking fields, no location fields, no
routing flags.

PlannerState is stored directly (as a serialised dict) rather than
being reconstructed on each planner invocation. Each capability node
that produces planning-relevant output updates planner_state explicitly.
This makes the planning signals the single source of truth.
"""

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

    # Final user-facing text. Written by response_node. Read by the API.
    final_response: Optional[str]
