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
from app.planner import PlannerState

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

        # Build initial graph state.
        initial_state = {
            "messages": lc_messages,
            "planner_state": PlannerState().model_dump(),
            "planner_decision": None,
            "medical_decision": None,
            "final_response": None,
        }

        # Run the graph
        final_state = await graph.ainvoke(
            initial_state, config={"recursion_limit": 10}
        )

        # Output sets final_response explicitly
        response_text = final_state.get("final_response") or (
            "I'm here to help you find the right doctor. "
            "Could you describe your symptoms?"
        )

        # Persist AI response
        add_message(session_id, "assistant", response_text)

        # Extract search results and specialty for frontend compatibility
        search_results = final_state.get("search_results")
        medical_decision_data = final_state.get("medical_decision") or {}
        specialty_needed = (
            medical_decision_data.get("specialty")
            if medical_decision_data.get("status") == "diagnosed"
            else None
        )

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            specialty_needed=specialty_needed,
            limit_reached=limit_reached,
            message_count=message_count,
            search_results=search_results,
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
