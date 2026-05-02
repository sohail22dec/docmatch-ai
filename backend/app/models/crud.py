from app.models.database import get_supabase_client


def create_session(title: str, user_id: str = None):
    """Creates a new chat session."""
    client = get_supabase_client()
    # Let Supabase generate the UUID, we just return the inserted row
    data = {"title": title}
    if user_id:
        data["user_id"] = user_id
    response = client.table("chat_sessions").insert(data).execute()
    if response.data:
        return response.data[0]
    return None


def get_sessions(user_id: str = None):
    """Gets all chat sessions ordered by newest first, optionally filtered by user."""
    client = get_supabase_client()
    query = client.table("chat_sessions").select("*")
    if user_id:
        query = query.eq("user_id", user_id)
        
    response = (
        query.order("created_at", desc=True)
        .execute()
    )
    return response.data


def get_messages(session_id: str, limit: int = 15):
    """
    Gets the latest messages for a specific session.
    Returns them in chronological order for the AI.
    """
    client = get_supabase_client()
    # 1. Get the LATEST messages by ordering DESC and limiting
    response = (
        client.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    
    # 2. Reverse them so they are back in CHRONOLOGICAL order for the AI
    messages = response.data
    messages.reverse()
    
    return messages


def add_message(session_id: str, role: str, content: str):
    """Adds a single message to a session."""
    client = get_supabase_client()
    data = {"session_id": session_id, "role": role, "content": content}
    response = client.table("chat_messages").insert(data).execute()
    if response.data:
        return response.data[0]
    return None

def delete_session(session_id: str):
    """Deletes a session and all its messages (via ON DELETE CASCADE)."""
    client = get_supabase_client()
    response = client.table("chat_sessions").delete().eq("id", session_id).execute()
    return response.data

def create_booking(booking_data: dict):
    """Creates a new booking in the 'bookings' table."""
    client = get_supabase_client()
    try:
        print(f"[create_booking] Inserting: {booking_data}")
        response = client.table("bookings").insert(booking_data).execute()
        print(f"[create_booking] Supabase response data: {response.data}")
        if response.data:
            return response.data[0]
        # If data is empty, the insert was blocked (e.g. by RLS or a constraint)
        print(f"[create_booking] ❌ Insert returned no data — likely blocked by Supabase RLS policy or missing column. Full response: {response}")
        return None
    except Exception as e:
        import traceback
        print(f"[create_booking] ❌ Exception during insert: {e}")
        print(traceback.format_exc())
        return None
