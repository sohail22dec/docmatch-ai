import json
import logging
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request, Depends
from app.models.schemas import ChatRequest, ChatResponse
from langchain_core.messages import HumanMessage, AIMessage
from app.core.auth import get_current_user
from app.models.crud import (
    create_session,
    get_sessions,
    get_messages,
    add_message,
    delete_session,
    get_user_message_count,
    link_anonymous_sessions,
)
from app.planner import PlannerState, CurrentLocation, LocationType, SearchStatus
from app.booking import (
    BookingCreateRequest,
    BookingService,
    BookingValidationError,
    SlotConflictError,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Anonymous users are limited to this many sent messages per session
ANON_MESSAGE_LIMIT = 5


def _message_metadata(message: dict) -> dict:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _latest_metadata_value(messages: list[dict], key: str):
    for message in reversed(messages):
        metadata = _message_metadata(message)
        if key in metadata:
            return metadata[key]
    return None


def _restore_planner_state(messages: list[dict]) -> PlannerState:
    saved_state = _latest_metadata_value(messages, "planner_state")
    if not saved_state:
        return PlannerState()
    try:
        return PlannerState.model_validate(saved_state)
    except Exception:
        logger.exception("Failed to restore PlannerState from session metadata.")
        return PlannerState()


def _restore_search_results(messages: list[dict]) -> list[dict] | None:
    saved_results = _latest_metadata_value(messages, "last_search_results")
    if saved_results is not None:
        return saved_results
    return _latest_metadata_value(messages, "clinics")


@router.get("/sessions")
def get_all_sessions(user_id: str = None):
    """Returns all chat sessions."""
    try:
        sessions = get_sessions(user_id)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """Returns all messages for a specific session."""
    try:
        messages = get_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch messages: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """Deletes a session and its messages."""
    try:
        delete_session(session_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete session: {str(e)}"
        )


@router.post("/auth/link-sessions")
def link_sessions_endpoint(payload: dict):
    """
    Called by the frontend after a successful sign-up/login.
    Links all anonymous chat sessions to the new authenticated user account,
    preserving the full chat history.
    """
    anon_user_id = payload.get("anon_user_id")
    real_user_id = payload.get("real_user_id")
    if not anon_user_id or not real_user_id:
        raise HTTPException(status_code=400, detail="anon_user_id and real_user_id are required.")
    try:
        link_anonymous_sessions(anon_user_id, real_user_id)
        return {"status": "success", "message": "Sessions linked successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link sessions: {str(e)}")



@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    DocMatch endpoint — Planner + Medical Capability architecture.
    """
    try:
        graph = getattr(request.app.state, "graph", None)
        if not graph:
            raise HTTPException(status_code=500, detail="LangGraph is not initialized.")

        if not chat_request.messages:
            raise HTTPException(status_code=400, detail="No messages provided.")

        # Auth + identity
        token_user_id = current_user.get("sub")
        user_role = current_user.get("role", "anon")
        is_anonymous = user_role == "anon"
        user_id = token_user_id or chat_request.user_id

        # Session management
        session_id = chat_request.session_id
        newest_user_message = chat_request.messages[-1]

        if not session_id:
            title = (
                newest_user_message.content[:30] + "..."
                if len(newest_user_message.content) > 30
                else newest_user_message.content
            )
            new_session = create_session(title, user_id)
            if not new_session:
                raise HTTPException(status_code=500, detail="Failed to create new session.")
            session_id = new_session["id"]

        # Anonymous message limit
        message_count = 0
        limit_reached = False
        if is_anonymous and session_id:
            message_count = get_user_message_count(session_id, user_id)
            if message_count >= ANON_MESSAGE_LIMIT:
                limit_reached = True

        # Persist user message
        add_message(session_id, "user", newest_user_message.content)
        message_count += 1

        # Fetch full history and convert to LangChain messages
        db_messages = get_messages(session_id)
        lc_messages = []
        for msg in db_messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        restored_planner_state = _restore_planner_state(db_messages)
        previous_search_results = _restore_search_results(db_messages)

        # Build initial graph state.
        initial_state = {
            "messages": lc_messages,
            "planner_state": restored_planner_state.model_dump(mode="json"),
            "planner_decision": None,
            "medical_decision": None,
            "search_results": None,
            "previous_search_results": previous_search_results,
            "selected_clinic_request": chat_request.selected_clinic,
            "final_response": None,
        }
        logger.info(
            "[planner_trace] %s",
            json.dumps(
                {
                    "node": "chat_endpoint",
                    "phase": "initial_state",
                    "request_selected_clinic": chat_request.selected_clinic,
                    "request_specialty_needed": chat_request.specialty_needed,
                    "request_booking_confirmed": chat_request.booking_confirmed,
                    "previous_search_results_count": len(previous_search_results or []),
                    "planner_state": initial_state["planner_state"],
                    "planner_decision": initial_state["planner_decision"],
                },
                default=str,
            ),
        )

        # Run the graph
        final_state = await graph.ainvoke(
            initial_state, config={"recursion_limit": 10}
        )

        # Output sets final_response explicitly
        response_text = final_state.get("final_response") or (
            "I'm here to help you find the right doctor. "
            "Could you describe your symptoms?"
        )

        # Extract search results, build metadata, and persist AI response
        search_results = final_state.get("search_results")
        last_search_results = (
            search_results
            if search_results is not None
            else previous_search_results
        )
        final_planner_state = PlannerState.model_validate(final_state["planner_state"])
        metadata = {
            "planner_state": final_planner_state.model_dump(mode="json"),
            "last_search_results": last_search_results,
        }
        if search_results:
            metadata["clinics"] = search_results
        # Do not save the intermediate assistant message if it triggers the booking form modal
        booking_res = final_state.get("booking_result") or {}
        if booking_res.get("status") != "open_booking_form":
            add_message(session_id, "assistant", response_text, metadata=metadata)

        medical_decision_data = final_state.get("medical_decision") or {}
        specialty_needed = (
            medical_decision_data.get("specialty")
            if medical_decision_data.get("status") == "diagnosed"
            else None
        )

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            action=final_state.get("action") or (final_state.get("booking_result") or {}).get("action"),
            specialty_needed=specialty_needed,
            selected_clinic=(
                final_planner_state.selected_clinic.model_dump(mode="json")
                if final_planner_state.selected_clinic
                else None
            ),
            current_booking=final_state.get("booking_result"),
            limit_reached=limit_reached,
            message_count=message_count,
            clinics=search_results,
            metadata=metadata,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("[chat_endpoint] CRITICAL ERROR")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

_booking_service = BookingService()


@router.post("/bookings", status_code=201)
async def create_booking_endpoint(req: BookingCreateRequest):
    """
    Create a booking appointment.

    Validates input, checks slot availability, persists to the database,
    and sends a confirmation email.
    """
    try:
        booking = await _booking_service.create_booking(req)
        return {
            "success": True,
            "booking": booking.model_dump(),
            "message": (
                f"Your appointment has been successfully booked! "
                f"A confirmation email has been sent to {booking.patient_email}."
            ),
        }
    except BookingValidationError as ve:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "VALIDATION_ERROR", "details": ve.errors},
        )
    except SlotConflictError as sce:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "SLOT_UNAVAILABLE",
                "message": sce.message,
                "suggested_slots": sce.suggested_slots,
            },
        )


@router.post("/chat/events")
def chat_events_endpoint(payload: dict):
    session_id = payload.get("session_id")
    event_type = payload.get("type")
    
    if not session_id or not event_type:
        raise HTTPException(status_code=400, detail="session_id and type are required.")
        
    db_messages = get_messages(session_id)
    final_planner_state = _restore_planner_state(db_messages)

    if event_type == "booking_completed":
        booking = payload.get("booking") or {}
        clinic_name = booking.get("clinic_name") or "the clinic"
        appointment_date = booking.get("appointment_date")
        time_slot = booking.get("time_slot")
        
        content = (
            f"✅ Your appointment with {clinic_name} has been booked successfully for "
            f"{appointment_date} at {time_slot}. A confirmation email has been sent."
        )
        final_planner_state.booking_completed = True
        
    elif event_type == "booking_failed":
        error_msg = payload.get("error") or "Unknown error"
        content = f"❌ Booking failed: {error_msg}"
        
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported event type: {event_type}")

    metadata = {
        "planner_state": final_planner_state.model_dump(mode="json"),
    }
    # Update search results from db if they existed, to preserve clinics list
    previous_search_results = _restore_search_results(db_messages)
    if previous_search_results is not None:
        metadata["last_search_results"] = previous_search_results
        metadata["clinics"] = previous_search_results

    add_message(session_id, "assistant", content, metadata=metadata)
    
    return {
        "status": "success",
        "message": content,
        "planner_state": final_planner_state.model_dump(mode="json"),
    }


class LocationRequest(BaseModel):
    session_id: str
    latitude: float | None = None
    longitude: float | None = None


@router.post("/chat/location")
async def chat_location_endpoint(
    request: Request,
    payload: LocationRequest,
):
    session_id = payload.session_id
    db_messages = get_messages(session_id)
    planner_state = _restore_planner_state(db_messages)
    previous_search_results = _restore_search_results(db_messages)

    if payload.latitude is None or payload.longitude is None:
        planner_state.location_type = LocationType.UNKNOWN
        planner_state.current_location = None
        content = (
            "I couldn't access your current location. "
            "Please tell me your city or locality so I can search nearby clinics."
        )
        metadata = {
            "planner_state": planner_state.model_dump(mode="json"),
        }
        if previous_search_results is not None:
            metadata["last_search_results"] = previous_search_results
            metadata["clinics"] = previous_search_results

        add_message(session_id, "assistant", content, metadata=metadata)
        return {
            "status": "success",
            "response": content,
            "metadata": metadata,
        }

    planner_state.current_location = CurrentLocation(
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    planner_state.location_type = LocationType.CURRENT_LOCATION
    planner_state.search_status = SearchStatus.NOT_ATTEMPTED

    lc_messages = []
    for msg in db_messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    initial_state = {
        "messages": lc_messages,
        "planner_state": planner_state.model_dump(mode="json"),
        "planner_decision": None,
        "medical_decision": None,
        "search_results": None,
        "previous_search_results": previous_search_results,
        "selected_clinic_request": None,
        "final_response": None,
    }

    graph = getattr(request.app.state, "graph", None)
    if not graph:
        raise HTTPException(status_code=500, detail="LangGraph is not initialized.")

    final_state = await graph.ainvoke(initial_state, config={"recursion_limit": 10})

    response_text = final_state.get("final_response") or "I found these clinics near your location."
    search_results = final_state.get("search_results")
    last_search_results = (
        search_results if search_results is not None else previous_search_results
    )

    final_planner_state = PlannerState.model_validate(final_state["planner_state"])
    metadata = {
        "planner_state": final_planner_state.model_dump(mode="json"),
        "last_search_results": last_search_results,
    }
    if search_results:
        metadata["clinics"] = search_results

    add_message(session_id, "assistant", response_text, metadata=metadata)

    return {
        "status": "success",
        "response": response_text,
        "session_id": session_id,
        "clinics": search_results,
        "metadata": metadata,
    }
