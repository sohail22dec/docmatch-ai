import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq

from app.core.config import settings
from app.shared.conversation import ConversationTurn
from app.planner import (
    ClinicSelection,
    Planner,
    PlannerState,
    PlannerDecision,
    MissingInfo,
    SearchStatus,
    LocationType,
)
from app.medical import run as medical_run, MedicalStatus
from app.medical.models import MedicalDecision
from app.services import GoogleMapsService, Clinic
from app.booking import BookingService, BookingCreateRequest

from app.agent.state import AgentState


# ---------------------------------------------------------------------------
# Module-level singletons — constructed once, reused across requests
# ---------------------------------------------------------------------------

_llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model="llama-3.1-8b-instant",
)

_planner = Planner()
_maps_service = GoogleMapsService()
logger = logging.getLogger(__name__)


def _log_planner_snapshot(
    *,
    node: str,
    phase: str,
    planner_state: PlannerState,
    planner_decision: PlannerDecision | dict | None,
    medical_decision: dict | None = None,
) -> None:
    if isinstance(planner_decision, PlannerDecision):
        planner_decision_data = planner_decision.model_dump(mode="json")
    else:
        planner_decision_data = planner_decision

    payload = {
        "node": node,
        "phase": phase,
        "planner_state": planner_state.model_dump(mode="json"),
        "planner_decision": planner_decision_data,
        "medical_decision": medical_decision,
    }
    logger.info("[planner_trace] %s", json.dumps(payload, default=str))


def _clinic_selection_from_clinic(clinic: dict) -> ClinicSelection:
    return ClinicSelection(
        id=str(clinic.get("id") or clinic.get("place_id") or clinic.get("name")),
        name=str(clinic.get("name") or ""),
        address=clinic.get("address"),
        rating=clinic.get("rating"),
    )


def _normalize_clinic_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.lower()
    normalized = re.sub(r"\bdoctor\b", "dr", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _latest_user_text(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _resolve_clinic_selection(
    *,
    user_text: str,
    clinics: list[dict],
    explicit_selection: dict | None = None,
) -> ClinicSelection | None:
    if not clinics:
        return None

    if explicit_selection:
        selected_id = str(
            explicit_selection.get("id")
            or explicit_selection.get("place_id")
            or ""
        )
        selected_name = _normalize_clinic_text(explicit_selection.get("name"))
        for clinic in clinics:
            clinic_id = str(clinic.get("id") or clinic.get("place_id") or "")
            clinic_name = _normalize_clinic_text(clinic.get("name"))
            if selected_id and selected_id == clinic_id:
                return _clinic_selection_from_clinic(clinic)
            if selected_name and selected_name == clinic_name:
                return _clinic_selection_from_clinic(clinic)

    normalized_user_text = _normalize_clinic_text(user_text)
    if not normalized_user_text:
        return None

    matches = []
    for clinic in clinics:
        clinic_name = _normalize_clinic_text(clinic.get("name"))
        if clinic_name and (
            clinic_name in normalized_user_text
            or normalized_user_text in clinic_name
        ):
            matches.append(clinic)

    if len(matches) == 1:
        return _clinic_selection_from_clinic(matches[0])
    return None


# ---------------------------------------------------------------------------
# clinic_selection_node
# ---------------------------------------------------------------------------


async def clinic_selection_node(state: AgentState) -> dict:
    current_ps = PlannerState.model_validate(state["planner_state"])
    _log_planner_snapshot(
        node="clinic_selection_node",
        phase="before",
        planner_state=current_ps,
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )

    if current_ps.clinic_selected:
        updated_ps = current_ps
    else:
        clinics = state.get("previous_search_results") or state.get("search_results") or []
        selected_clinic = _resolve_clinic_selection(
            user_text=_latest_user_text(state),
            clinics=clinics,
            explicit_selection=state.get("selected_clinic_request"),
        )
        updated_ps = (
            current_ps.model_copy(update={"selected_clinic": selected_clinic})
            if selected_clinic
            else current_ps
        )

    _log_planner_snapshot(
        node="clinic_selection_node",
        phase="after",
        planner_state=updated_ps,
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )
    return {"planner_state": updated_ps.model_dump()}


# ---------------------------------------------------------------------------
# planner_node
# ---------------------------------------------------------------------------


async def planner_node(state: AgentState) -> dict:
    planner_state = PlannerState.model_validate(state["planner_state"])
    medical_decision = state.get("medical_decision")
    _log_planner_snapshot(
        node="planner_node",
        phase="before_decide",
        planner_state=planner_state,
        planner_decision=state.get("planner_decision"),
        medical_decision=medical_decision,
    )
    decision = _planner.decide(planner_state, medical_decision=medical_decision)
    _log_planner_snapshot(
        node="planner_node",
        phase="after_decide",
        planner_state=planner_state,
        planner_decision=decision,
        medical_decision=medical_decision,
    )
    return {"planner_decision": decision.model_dump()}


# ---------------------------------------------------------------------------
# medical_node
# ---------------------------------------------------------------------------


async def medical_node(state: AgentState) -> dict:
    _log_planner_snapshot(
        node="medical_node",
        phase="before",
        planner_state=PlannerState.model_validate(state["planner_state"]),
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )

    conversation = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            conversation.append(ConversationTurn(role="user", content=msg.content))
        elif isinstance(msg, AIMessage):
            conversation.append(ConversationTurn(role="assistant", content=msg.content))
        elif isinstance(msg, dict):
            conversation.append(ConversationTurn(role=msg.get("role", "user"), content=msg.get("content", "")))

    # Run the Medical Capability
    decision = await medical_run(conversation=conversation, llm=_llm)

    # Update PlannerState facts
    current_ps = PlannerState.model_validate(state["planner_state"])
    if decision.status == MedicalStatus.DIAGNOSED:
        updates = {}
        if decision.specialty:
            updates["specialty"] = decision.specialty
        if decision.location_type:
            if decision.location_type == "city":
                updates["location_type"] = LocationType.CITY
            elif decision.location_type == "current_location":
                updates["location_type"] = LocationType.CURRENT_LOCATION
            elif decision.location_type == "unknown":
                updates["location_type"] = LocationType.UNKNOWN
        if decision.city:
            updates["city"] = decision.city
            updates["location_type"] = LocationType.CITY
        updated_ps = current_ps.model_copy(update=updates)
    else:
        updated_ps = current_ps

    _log_planner_snapshot(
        node="medical_node",
        phase="after",
        planner_state=updated_ps,
        planner_decision=state.get("planner_decision"),
        medical_decision=decision.model_dump(mode="json"),
    )

    return {
        "medical_decision": decision.model_dump(),
        "planner_state": updated_ps.model_dump(),
    }


# ---------------------------------------------------------------------------
# search_node
# ---------------------------------------------------------------------------


async def search_node(state: AgentState) -> dict:
    current_ps = PlannerState.model_validate(state["planner_state"])
    _log_planner_snapshot(
        node="search_node",
        phase="before",
        planner_state=current_ps,
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )

    specialty = current_ps.specialty or ""
    action = None
    clinics = []

    if current_ps.location_type == LocationType.CITY and current_ps.city:
        clinics = await _maps_service.search_clinics(specialty=specialty, city=current_ps.city)
        new_status = SearchStatus.HAS_RESULTS if clinics else SearchStatus.EMPTY
        updated_ps = current_ps.model_copy(update={"search_status": new_status})

    elif current_ps.location_type == LocationType.CURRENT_LOCATION:
        if current_ps.current_location:
            clinics = await _maps_service.search_clinics(
                specialty=specialty,
                latitude=current_ps.current_location.latitude,
                longitude=current_ps.current_location.longitude,
            )
            new_status = SearchStatus.HAS_RESULTS if clinics else SearchStatus.EMPTY
            updated_ps = current_ps.model_copy(update={"search_status": new_status})
        else:
            updated_ps = current_ps.model_copy(update={"search_status": SearchStatus.AWAITING_LOCATION})
            action = "request_current_location"
    else:
        city_str = current_ps.city or ""
        clinics = await _maps_service.search_clinics(specialty=specialty, city=city_str)
        new_status = SearchStatus.HAS_RESULTS if clinics else SearchStatus.EMPTY
        updated_ps = current_ps.model_copy(update={"search_status": new_status})

    _log_planner_snapshot(
        node="search_node",
        phase="after",
        planner_state=updated_ps,
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )

    return {
        "search_results": [c.model_dump() for c in clinics],
        "planner_state": updated_ps.model_dump(),
        "action": action,
    }


# ---------------------------------------------------------------------------
# booking_node
# ---------------------------------------------------------------------------


async def booking_node(state: AgentState) -> dict:
    """
    Starts the booking capability once the planner has a concrete clinic selection.
    Actual appointment creation still requires patient/date/time details.
    """
    planner_state = PlannerState.model_validate(state["planner_state"])
    _log_planner_snapshot(
        node="booking_node",
        phase="before",
        planner_state=planner_state,
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )
    _log_planner_snapshot(
        node="booking_node",
        phase="after",
        planner_state=planner_state,
        planner_decision=state.get("planner_decision"),
        medical_decision=state.get("medical_decision"),
    )
    selected_clinic = (
        planner_state.selected_clinic.model_dump(mode="json")
        if planner_state.selected_clinic
        else None
    )
    return {
        "booking_result": {
            "status": "open_booking_form",
            "action": "open_booking_form",
            "selected_clinic": selected_clinic,
        },
    }


# ---------------------------------------------------------------------------
# response_node
# ---------------------------------------------------------------------------


async def response_node(state: AgentState) -> dict:
    medical_decision_data = state.get("medical_decision")
    planner_decision_data = state.get("planner_decision")
    raw_search_results = state.get("search_results")
    booking_result = state.get("booking_result")
    action = state.get("action")

    current_ps = PlannerState.model_validate(state["planner_state"])
    if current_ps.search_status == SearchStatus.AWAITING_LOCATION:
        action = "request_current_location"
        response_text = ""
    elif booking_result:
        if booking_result.get("status") == "open_booking_form":
            selected_clinic = booking_result.get("selected_clinic") or {}
            clinic_name = selected_clinic.get("name") or "that clinic"
            response_text = (
                f"Great! I'll help you book an appointment at **{clinic_name}**. "
                "Please complete the booking form."
            )
        elif "id" in booking_result:
            response_text = (
                f"Your appointment at **{booking_result.get('clinic_name')}** has been successfully confirmed!\n\n"
                f"**Appointment ID**: `{booking_result.get('id')}`\n"
                f"**Patient**: {booking_result.get('patient_name')}\n"
                f"**Date**: {booking_result.get('appointment_date')}\n"
                f"**Time**: {booking_result.get('time_slot')}"
            )
        else:
            response_text = f"Booking Error: {booking_result.get('error', 'Unable to complete booking.')}"
    elif raw_search_results is not None:
        clinics = [Clinic.model_validate(c) for c in raw_search_results]
        med_dec = MedicalDecision.model_validate(medical_decision_data) if medical_decision_data else None
        response_text = _build_search_response(
            clinics=clinics,
            specialty=(med_dec.specialty if med_dec else "doctor"),
            city=(med_dec.city if med_dec else "your area"),
        )
    else:
        # Clean debug logging of internal symptoms summary — never shown to users
        if medical_decision_data:
            summary = medical_decision_data.get("symptoms_summary")
            if summary:
                print(f"[DEBUG] Medical Symptoms Summary: {summary}")

        response_text = _build_response(medical_decision_data, planner_decision_data)

    messages = [AIMessage(content=response_text)] if response_text else []
    return {
        "messages": messages,
        "final_response": response_text,
        "search_results": raw_search_results,
        "action": action,
    }


def _build_search_response(clinics: list[Clinic], specialty: str, city: str) -> str:
    if not clinics:
        return f"I couldn't find any **{specialty}** clinics in **{city}**. Would you like to try a different location?"

    return f"I found these **{specialty}** clinics in **{city}**. Would you like to book an appointment at one of these clinics?"


def _build_response(
    medical_decision_data: dict | None,
    planner_decision_data: dict | None = None,
) -> str:
    med_dec = (
        MedicalDecision.model_validate(medical_decision_data)
        if medical_decision_data
        else None
    )
    planner_dec = (
        PlannerDecision.model_validate(planner_decision_data)
        if planner_decision_data
        else None
    )

    missing = planner_dec.missing_info if planner_dec else []

    # Rule 1: If missing_info contains LOCATION: Ask the user for their city
    if MissingInfo.LOCATION in missing:
        if med_dec and med_dec.specialty:
            return f"I understand you're looking for a **{med_dec.specialty}**. Could you please share your city or location so I can find clinics near you?"
        return "Could you please share your city or location so I can find clinics near you?"

    # Rule 2: If missing_info contains SPECIALTY: Ask the user to clarify the specialty / symptoms
    if MissingInfo.SPECIALTY in missing:
        if med_dec and med_dec.clarification_question:
            return med_dec.clarification_question
        return "Could you tell me more about your symptoms or what kind of specialist you need?"

    # Rule 3: Generate confirmation text only when no required info is missing
    if med_dec:
        if med_dec.status == MedicalStatus.CLARIFYING:
            return med_dec.clarification_question or (
                "Could you tell me more about your symptoms?"
            )

        if med_dec.status == MedicalStatus.DIAGNOSED:
            if med_dec.city:
                return f"I understand you're looking for a **{med_dec.specialty}** in **{med_dec.city}**."
            return f"I understand you're looking for a **{med_dec.specialty}**."

    # Fallback
    return (
        "I'm here to help you find the right doctor. "
        "Could you describe what you're experiencing?"
    )
