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
    messages: List[Message] # We only really need the *newest* message from the frontend, but we accept the list for compatibility

class ChatResponse(BaseModel):
    response: str
    session_id: str

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
    Accepts a new message, saves it to Supabase, runs LangGraph on the full history, and saves the AI response.
    """
    graph = getattr(request.app.state, "graph", None)
    if not graph:
        raise HTTPException(status_code=500, detail="LangGraph is not initialized.")
    
    if not chat_request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    # 1. Manage Session
    session_id = chat_request.session_id
    newest_user_message = chat_request.messages[-1] # Assume the last message is the new one from the user

    if not session_id:
        # Create a new session with a title derived from the first message
        title = newest_user_message.content[:30] + "..." if len(newest_user_message.content) > 30 else newest_user_message.content
        new_session = create_session(title)
        if not new_session:
            raise HTTPException(status_code=500, detail="Failed to create new session in database.")
        session_id = new_session['id']

    # 2. Save the user's new message to the database
    add_message(session_id, "user", newest_user_message.content)

    # 3. Fetch the FULL message history for this session from the database
    # This ensures LangGraph has the full context, even if the frontend only sent the latest message
    db_messages = get_messages(session_id)
    
    # 4. Convert DB messages to LangChain message objects
    lc_messages = []
    for msg in db_messages:
        if msg['role'] == "user":
            lc_messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == "assistant":
            lc_messages.append(AIMessage(content=msg['content']))
            
    # 5. Initialize the state for the graph
    state = {"messages": lc_messages}
    
    try:
        # 6. Invoke the LangGraph agent
        final_state = await graph.ainvoke(state, config={"recursion_limit": 10})
        
        # 7. Extract the final response
        final_message = final_state["messages"][-1]
        
        # 8. Save the AI's response back to the database
        add_message(session_id, "assistant", final_message.content)
        
        return ChatResponse(response=final_message.content, session_id=session_id)
        
    except Exception as e:
        print(f"Error during graph execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
