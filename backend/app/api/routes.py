import traceback
from datetime import datetime
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

router = APIRouter()

# Anonymous users are limited to this many sent messages per session
ANON_MESSAGE_LIMIT = 5


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
    Accepts a new message + optional location data, saves to Supabase,
    runs the multi-agent LangGraph, and saves the AI response.

    - Requires a valid Supabase JWT (anonymous or authenticated).
    - Enforces a 5-message limit per session for anonymous users.
    """
    try:
        graph = getattr(request.app.state, "graph", None)
        if not graph:
            raise HTTPException(status_code=500, detail="LangGraph is not initialized.")

        if not chat_request.messages:
            raise HTTPException(status_code=400, detail="No messages provided.")

        # Extract user identity from verified JWT
        # Supabase sets role="anon" for anonymous sessions, "authenticated" for real users
        token_user_id = current_user.get("sub")
        user_role = current_user.get("role", "anon")  # "anon" or "authenticated"
        is_anonymous = user_role == "anon"

        # Use the token's user_id (more secure than trusting client-sent user_id)
        user_id = token_user_id or chat_request.user_id

        # 1. Manage Session
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

        # 2. Check anonymous message limit BEFORE saving the message
        message_count = 0
        limit_reached = False
        if is_anonymous and session_id:
            message_count = get_user_message_count(session_id, user_id)
            if message_count >= ANON_MESSAGE_LIMIT:
                limit_reached = True

        # 3. Save user message to DB
        add_message(session_id, "user", newest_user_message.content)
        message_count += 1  # Reflect the message we just added

        # 4. Fetch full message history from DB
        db_messages = get_messages(session_id)

        # 5. Convert to LangChain message objects
        lc_messages = []
        for msg in db_messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        # 6. Build initial state
        state = {
            "messages": lc_messages,
            "user_id": user_id,
            "latitude": chat_request.latitude,
            "longitude": chat_request.longitude,
            "city": chat_request.city,
            "location_denied": chat_request.location_denied,
            "clinics_found": None,
            "search_attempted": False,
            "final_response": None,
            "specialty_needed": chat_request.specialty_needed,
            "symptoms": None,
            "selected_clinic": chat_request.selected_clinic,
            "current_booking": chat_request.current_booking,
            "booking_confirmed": chat_request.booking_confirmed,
            "booking_id": chat_request.booking_id,
            "action_required": None,
            "next": None,
            "google_calendar_token": chat_request.google_calendar_token,
        }

        # 7. Run the multi-agent graph
        final_state = await graph.ainvoke(state, config={"recursion_limit": 20})

        # 8. Extract the last AI message
        final_message = None
        msgs = final_state.get("messages", [])
        for msg in reversed(msgs):
            if isinstance(msg, AIMessage) or (
                hasattr(msg, "type") and msg.type == "ai"
            ):
                final_message = msg
                break

        if not final_message:
            print(
                "[chat_endpoint] WARNING: No AI message found in state. Falling back to default."
            )
            final_message = AIMessage(
                content="I've processed your request, but I'm not sure how to respond. How else can I help you?"
            )

        # 9. Save AI response to DB
        add_message(session_id, "assistant", final_message.content)

        return ChatResponse(
            response=final_message.content,
            session_id=session_id,
            action=final_state.get("action_required"),
            selected_clinic=final_state.get("selected_clinic"),
            current_booking=final_state.get("current_booking"),
            booking_confirmed=final_state.get("booking_confirmed"),
            booking_id=final_state.get("booking_id"),
            specialty_needed=final_state.get("specialty_needed"),
            limit_reached=limit_reached,
            message_count=message_count,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(f"[chat_endpoint] CRITICAL ERROR: {error_msg}")
        with open("backend_error.log", "a") as f:
            f.write(f"\n--- {datetime.now()} ---\n{error_msg}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )
