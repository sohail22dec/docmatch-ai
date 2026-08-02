from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request, Depends

from app.models.schemas import ChatRequest, ChatResponse
from app.core.auth import get_current_user
from app.models.crud import get_messages
from app.api.chat_service import (
    get_or_create_session,
    build_initial_graph_state,
    invoke_graph_and_build_response,
    handle_chat_event,
    process_location_request,
)

router = APIRouter(tags=["Chat"])


class LocationRequest(BaseModel):
    session_id: str
    latitude: float | None = None
    longitude: float | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        graph = getattr(request.app.state, "graph", None)
        if not graph:
            raise HTTPException(
                status_code=500, detail="LangGraph is not initialized."
            )
        if not chat_request.messages:
            raise HTTPException(status_code=400, detail="No messages provided.")

        session_id, limit_reached, message_count = get_or_create_session(
            chat_request, current_user
        )
        db_messages = get_messages(session_id)
        initial_state = build_initial_graph_state(db_messages, chat_request)

        return await invoke_graph_and_build_response(
            graph=graph,
            session_id=session_id,
            initial_state=initial_state,
            limit_reached=limit_reached,
            message_count=message_count,
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {str(e)}"
        )


@router.post("/chat/events")
def chat_events_endpoint(payload: dict):
    return handle_chat_event(payload)


@router.post("/chat/location")
async def chat_location_endpoint(
    request: Request,
    payload: LocationRequest,
):
    graph = getattr(request.app.state, "graph", None)
    if not graph:
        raise HTTPException(
            status_code=500, detail="LangGraph is not initialized."
        )

    return await process_location_request(
        graph=graph,
        session_id=payload.session_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
