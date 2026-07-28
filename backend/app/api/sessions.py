from fastapi import APIRouter, HTTPException
from app.planner import PlannerState
from app.models.crud import (
    get_sessions,
    get_messages,
    delete_session,
    link_anonymous_sessions,
)

router = APIRouter(tags=["Sessions"])


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
        raise HTTPException(
            status_code=400, detail="anon_user_id and real_user_id are required."
        )
    try:
        link_anonymous_sessions(anon_user_id, real_user_id)
        return {"status": "success", "message": "Sessions linked successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to link sessions: {str(e)}"
        )
