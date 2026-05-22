"""
Calendar utility functions for DocMatch AI booking system.

Uses Supabase 'bookings' table to track slots and prevent double-booking.
"""
from datetime import datetime
from typing import Optional

from app.models.database import get_supabase_client


# ─────────────────────────────────────────────────────────────────────────────
# Business Hours Constants
# ─────────────────────────────────────────────────────────────────────────────

BUSINESS_START_HOUR = 8   # 8:00 AM
BUSINESS_END_HOUR = 17    # 5:00 PM


# ─────────────────────────────────────────────────────────────────────────────
# Business Hours Validation
# ─────────────────────────────────────────────────────────────────────────────

def is_within_business_hours(time_str: str) -> bool:
    """
    Returns True if the given time string (e.g. '10:00 AM', '2:30 PM', '14:00')
    falls within 8:00 AM – 5:00 PM (17:00).
    """
    time_str = time_str.strip().upper()
    parsed = None

    for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%H"):
        try:
            parsed = datetime.strptime(time_str, fmt)
            break
        except ValueError:
            continue

    if parsed is None:
        # Cannot parse → treat as invalid (outside hours)
        return False

    hour = parsed.hour

    # Allow 8:00 AM through 4:59 PM (last slot starts at 4:00 PM → ends 5:00 PM)
    if hour < BUSINESS_START_HOUR:
        return False
    if hour >= BUSINESS_END_HOUR:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Database — Conflict & Slot Availability
# ─────────────────────────────────────────────────────────────────────────────

def get_available_slots(date_str: str) -> list[str]:
    """
    Check the database and return a list of free 1-hour slots
    between 8:00 AM and 5:00 PM on the given date (YYYY-MM-DD).
    """
    try:
        client = get_supabase_client()
        # Query bookings table in Supabase for all active appointments on date_str
        response = client.table("bookings").select("time_slot").eq("appointment_date", date_str).eq("status", "confirmed").execute()
        
        booked_slots = set()
        if response.data:
            for b in response.data:
                ts = b.get("time_slot")
                if ts:
                    booked_slots.add(_normalize_time(ts))

        # Build list of free slots
        available = []
        for hour in range(BUSINESS_START_HOUR, BUSINESS_END_HOUR):
            dt = datetime(2000, 1, 1, hour)
            slot_name = dt.strftime("%-I:%M %p").upper()
            if slot_name not in booked_slots:
                # Keep formatting like '8:00 AM'
                available.append(dt.strftime("%-I:%M %p"))

        return available

    except Exception as e:
        print(f"[calendar] get_available_slots database fallback error: {e}")
        return _all_slots()


def check_admin_conflict(date_str: str, time_str: str) -> bool:
    """
    Returns True if the database already has an event
    at the given date+time.
    """
    try:
        client = get_supabase_client()
        
        response = client.table("bookings").select("time_slot").eq("appointment_date", date_str).eq("status", "confirmed").execute()
        if response.data:
            target = _normalize_time(time_str)
            for b in response.data:
                db_slot = b.get("time_slot")
                if db_slot and _normalize_time(db_slot) == target:
                    return True
        return False

    except Exception as e:
        print(f"[calendar] check_admin_conflict database fallback error: {e}")
        return False


def create_admin_event(booking_data: dict, clinic: dict) -> Optional[str]:
    """
    Stub returning a mock ID since database insert is handled elsewhere.
    """
    import random
    return f"DB-EVT-{random.randint(1000, 9999)}"


# ─────────────────────────────────────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_time(t: str) -> str:
    """Normalizes time string to %I:%M %p format for comparison."""
    t = t.strip().upper()
    for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%H"):
        try:
            parsed = datetime.strptime(t, fmt)
            return parsed.strftime("%I:%M %p").upper()
        except ValueError:
            continue
    return t


def _all_slots() -> list[str]:
    """Returns all 1-hour slots from 8AM to 5PM as fallback."""
    slots = []
    for hour in range(BUSINESS_START_HOUR, BUSINESS_END_HOUR):
        dt = datetime(2000, 1, 1, hour)
        slots.append(dt.strftime("%-I:%M %p"))
    return slots
