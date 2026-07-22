from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq

from app.core.config import settings
from app.shared.conversation import ConversationTurn
from app.planner import (
    Planner,
    PlannerState,
    SearchStatus,
)
from app.medical import run as medical_run, MedicalStatus
from app.medical.models import MedicalDecision
from app.services import GoogleMapsService, Clinic

from .state import AgentState


# ---------------------------------------------------------------------------
# Module-level singletons — constructed once, reused across requests
# ---------------------------------------------------------------------------

_llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
)

_planner = Planner()
_maps_service = GoogleMapsService()


# ---------------------------------------------------------------------------
# planner_node
# ---------------------------------------------------------------------------


async def planner_node(state: AgentState) -> dict:
    planner_state = PlannerState.model_validate(state["planner_state"])
    decision = _planner.decide(planner_state)
    return {"planner_decision": decision.model_dump()}


# ---------------------------------------------------------------------------
# medical_node
# ---------------------------------------------------------------------------


async def medical_node(state: AgentState) -> dict:
    # Convert LangGraph messages to ConversationTurns
    conversation = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            conversation.append(ConversationTurn(role="user", content=msg.content))
        elif isinstance(msg, AIMessage):
            conversation.append(ConversationTurn(role="assistant", content=msg.content))

    # Run the Medical Capability
    decision = await medical_run(conversation=conversation, llm=_llm)

    # Update PlannerState if the specialty/location is now known
    current_ps = PlannerState.model_validate(state["planner_state"])
    if decision.status == MedicalStatus.DIAGNOSED:
        updates = {"specialty_known": True}
        if decision.city:
            updates["location_known"] = True
        updated_ps = current_ps.model_copy(update=updates)
    else:
        updated_ps = current_ps

    return {
        "medical_decision": decision.model_dump(),
        "planner_state": updated_ps.model_dump(),
    }


# ---------------------------------------------------------------------------
# search_node
# ---------------------------------------------------------------------------


async def search_node(state: AgentState) -> dict:
    medical_decision_data = state.get("medical_decision") or {}
    specialty = medical_decision_data.get("specialty", "")
    city = medical_decision_data.get("city", "")

    clinics = await _maps_service.search_clinics(specialty=specialty, city=city)

    current_ps = PlannerState.model_validate(state["planner_state"])
    new_status = SearchStatus.HAS_RESULTS if clinics else SearchStatus.EMPTY
    updated_ps = current_ps.model_copy(update={"search_status": new_status})

    return {
        "search_results": [c.model_dump() for c in clinics],
        "planner_state": updated_ps.model_dump(),
    }


# ---------------------------------------------------------------------------
# response_node
# ---------------------------------------------------------------------------


async def response_node(state: AgentState) -> dict:
    medical_decision_data = state.get("medical_decision")
    raw_search_results = state.get("search_results")

    if raw_search_results is not None:
        clinics = [Clinic.model_validate(c) for c in raw_search_results]
        med_dec = MedicalDecision.model_validate(medical_decision_data or {})
        response_text = _build_search_response(
            clinics=clinics,
            specialty=med_dec.specialty or "doctor",
            city=med_dec.city or "your area",
        )
    else:
        # Clean debug logging of internal symptoms summary — never shown to users
        if medical_decision_data:
            summary = medical_decision_data.get("symptoms_summary")
            if summary:
                print(f"[DEBUG] Medical Symptoms Summary: {summary}")

        response_text = _build_response(medical_decision_data)

    return {
        "messages": [AIMessage(content=response_text)],
        "final_response": response_text,
        "search_results": raw_search_results,
    }


def _build_search_response(clinics: list[Clinic], specialty: str, city: str) -> str:
    if not clinics:
        return f"I couldn't find any **{specialty}** clinics in **{city}**. Would you like to try a different location?"

    return f"I found these **{specialty}** clinics in **{city}**. Would you like to book an appointment at one of these clinics?"


def _build_response(medical_decision_data: dict | None) -> str:
    if medical_decision_data:
        decision = MedicalDecision.model_validate(medical_decision_data)

        if decision.status == MedicalStatus.DIAGNOSED:
            if decision.is_direct_request:
                if decision.city:
                    return f"I understand you're looking for a **{decision.specialty}** in **{decision.city}**."
                return f"I understand you're looking for a **{decision.specialty}**."
            else:
                if decision.city:
                    return f"Based on your symptoms, you should consult a **{decision.specialty}** in **{decision.city}**."
                return f"Based on your symptoms, you should consult a **{decision.specialty}**."

        if decision.status == MedicalStatus.CLARIFYING:
            return decision.clarification_question or (
                "Could you tell me more about your symptoms?"
            )

    # Fallback
    return (
        "I'm here to help you find the right doctor. "
        "Could you describe what you're experiencing?"
    )
