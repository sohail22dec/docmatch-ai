# backend/app/models/database.py

from supabase import create_client, Client
from app.core.config import settings

# This creates our connection to the Supabase cloud database
supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL, supabase_key=settings.SUPABASE_SERVICE_KEY
)


def get_supabase_client() -> Client:
    """
    Returns the initialized Supabase client so we can use it
    in our booking agent and tools later.
    """
    return supabase
