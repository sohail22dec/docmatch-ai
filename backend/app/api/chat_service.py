from fastapi import HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from app.models.schemas import ChatRequest, ChatResponse
from app.models.crud import (
    create_session,
    get_messages,
    add_message,
    get_user_message_count,
)
from app.planner import PlannerState, CurrentLocation, LocationType, SearchStatus
from app.api.sessions import _restore_planner_state, _restore_search_results
from app.agent.nodes import _resolve_clinic_selection

ANON_MESSAGE_LIMIT = 5


def get_or_create_session(
    chat_request: ChatRequest, current_user: dict
) -> tuple[str, bool, int]:
    token_user_id = current_user.get("sub")
    user_role = current_user.get("role", "anon")
    is_anonymous = user_role == "anon"
    user_id = token_user_id or chat_request.user_id

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
            raise HTTPException(
                status_code=500, detail="Failed to create new session."
            )
        session_id = new_session["id"]

    message_count = 0
    limit_reached = False
    if is_anonymous and session_id:
        message_count = get_user_message_count(session_id, user_id)
        if message_count >= ANON_MESSAGE_LIMIT:
            limit_reached = True

    add_message(session_id, "user", newest_user_message.content)
    message_count += 1

    return session_id, limit_reached, message_count


def build_initial_graph_state(
    db_messages: list[dict], chat_request: ChatRequest
) -> dict:
    lc_messages = []
    for msg in db_messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    restored_planner_state = _restore_planner_state(db_messages)
    previous_search_results = _restore_search_results(db_messages)

    if not restored_planner_state.clinic_selected:
        latest_user_text = chat_request.messages[-1].content if chat_request.messages else ""
        selected_clinic = _resolve_clinic_selection(
            user_text=latest_user_text,
            clinics=previous_search_results or [],
            explicit_selection=chat_request.selected_clinic,
        )
        if selected_clinic:
            restored_planner_state = restored_planner_state.model_copy(
                update={"selected_clinic": selected_clinic}
            )

    return {
        "messages": lc_messages,
        "planner_state": restored_planner_state.model_dump(mode="json"),
        "planner_decision": None,
        "medical_decision": None,
        "search_results": None,
        "previous_search_results": previous_search_results,
        "selected_clinic_request": chat_request.selected_clinic,
        "final_response": None,
    }


async def invoke_graph_and_build_response(
    graph,
    session_id: str,
    initial_state: dict,
    limit_reached: bool = False,
    message_count: int = 0,
    default_fallback_text: str = "I'm here to help you find the right doctor. Could you describe your symptoms?",
) -> ChatResponse:
    final_state = await graph.ainvoke(
        initial_state, config={"recursion_limit": 10}
    )

    response_text = final_state.get("final_response") or default_fallback_text
    search_results = final_state.get("search_results")
    previous_search_results = initial_state.get("previous_search_results")
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
        action=final_state.get("action")
        or (final_state.get("booking_result") or {}).get("action"),
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


def handle_chat_event(payload: dict) -> dict:
    session_id = payload.get("session_id")
    event_type = payload.get("type")

    if not session_id or not event_type:
        raise HTTPException(
            status_code=400, detail="session_id and type are required."
        )

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
        raise HTTPException(
            status_code=400, detail=f"Unsupported event type: {event_type}"
        )

    metadata = {
        "planner_state": final_planner_state.model_dump(mode="json"),
    }
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


async def process_location_request(
    graph, session_id: str, latitude: float | None, longitude: float | None
) -> dict:
    db_messages = get_messages(session_id)
    planner_state = _restore_planner_state(db_messages)
    previous_search_results = _restore_search_results(db_messages)

    if latitude is None or longitude is None:
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
        latitude=latitude,
        longitude=longitude,
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

    chat_resp = await invoke_graph_and_build_response(
        graph=graph,
        session_id=session_id,
        initial_state=initial_state,
        default_fallback_text="I found these clinics near your location.",
    )

    return {
        "status": "success",
        "response": chat_resp.response,
        "session_id": session_id,
        "clinics": chat_resp.clinics,
        "metadata": chat_resp.metadata,
    }
