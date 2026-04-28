# backend/app/api/routes.py

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage
from app.models.crud import create_session, get_sessions, get_messages, add_message, delete_session

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[Message]
    # Location data from the frontend 📍 button
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    location_denied: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    session_id: str
    action: Optional[str] = None


@router.get("/sessions")
def get_all_sessions():
    """Returns all chat sessions."""
    try:
        sessions = get_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """Returns all messages for a specific session."""
    try:
        messages = get_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """Deletes a session and its messages."""
    try:
        delete_session(session_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    """
    Accepts a new message + optional location data, saves to Supabase,
    runs the multi-agent LangGraph, and saves the AI response.
    """
    graph = getattr(request.app.state, "graph", None)
    if not graph:
        raise HTTPException(status_code=500, detail="LangGraph is not initialized.")

    if not chat_request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    # 1. Manage Session
    session_id = chat_request.session_id
    newest_user_message = chat_request.messages[-1]

    if not session_id:
        title = (
            newest_user_message.content[:30] + "..."
            if len(newest_user_message.content) > 30
            else newest_user_message.content
        )
        new_session = create_session(title)
        if not new_session:
            raise HTTPException(status_code=500, detail="Failed to create new session.")
        session_id = new_session["id"]

    # 2. Save user message to DB
    add_message(session_id, "user", newest_user_message.content)

    # 3. Fetch full message history from DB
    db_messages = get_messages(session_id)

    # 4. Convert to LangChain message objects
    lc_messages = []
    for msg in db_messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    # 5. Build initial state — include location data from frontend
    state = {
        "messages": lc_messages,
        "latitude": chat_request.latitude,
        "longitude": chat_request.longitude,
        "city": chat_request.city or None,
        "location_denied": chat_request.location_denied or False,
        "clinics_found": None,
        "search_attempted": False,
        "final_response": None,
        "specialty_needed": None,
        "symptoms": None,
        "next": None,
        "location_source": "gps" if chat_request.latitude else (
            "user_typed" if chat_request.city else "none"
        ),
    }

    try:
        # 6. Run the multi-agent graph
        final_state = await graph.ainvoke(state, config={"recursion_limit": 20})

        # 7. Extract the last AI message
        final_message = None
        for msg in reversed(final_state.get("messages", [])):
            if isinstance(msg, AIMessage):
                final_message = msg
                break

        if not final_message:
            raise ValueError("No AI response generated.")

        # 8. Save AI response to DB
        add_message(session_id, "assistant", final_message.content)

        return ChatResponse(
            response=final_message.content, 
            session_id=session_id,
            action=final_state.get("action_required")
        )

    except Exception as e:
        print(f"[chat_endpoint] Error during graph execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
