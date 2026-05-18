"""
Google Calendar utility functions for DocMatch AI booking system.

Admin/Clinic Calendar — server-side (token.json). Tracks all bookings.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ─────────────────────────────────────────────────────────────────────────────
# Business Hours Constants
# ─────────────────────────────────────────────────────────────────────────────

BUSINESS_START_HOUR = 8   # 8:00 AM
BUSINESS_END_HOUR = 17    # 5:00 PM


# ─────────────────────────────────────────────────────────────────────────────
# Credential Loaders
# ─────────────────────────────────────────────────────────────────────────────

def _get_admin_calendar_service():
    """
    Load server-side credentials from token.json (or env vars for Render).
    Returns a Google Calendar API service object, or None on failure.
    """
    try:
        token_json_str = os.environ.get("GOOGLE_TOKEN_JSON")
        creds_json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")

        if token_json_str:
            token_data = json.loads(token_json_str)
        elif os.path.exists("token.json"):
            with open("token.json") as f:
                token_data = json.load(f)
        else:
            return None

        if creds_json_str:
            creds_info = json.loads(creds_json_str)
        elif os.path.exists("credentials.json"):
            with open("credentials.json") as f:
                creds_info = json.load(f)
        else:
            return None

        client_info = creds_info.get("installed") or creds_info.get("web") or {}
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=client_info.get("client_id") or token_data.get("client_id"),
            client_secret=client_info.get("client_secret") or token_data.get("client_secret"),
            scopes=token_data.get("scopes", [
                "https://mail.google.com/",
                "https://www.googleapis.com/auth/calendar",
            ]),
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"[calendar] Failed to load admin calendar service: {e}")
        return None


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
# Admin Calendar — Conflict & Slot Availability
# ─────────────────────────────────────────────────────────────────────────────

def get_available_slots(date_str: str) -> list[str]:
    """
    Check the admin calendar and return a list of free 1-hour slots
    between 8:00 AM and 5:00 PM on the given date (YYYY-MM-DD).
    """
    service = _get_admin_calendar_service()
    if not service:
        # Fall back to all slots if calendar unavailable
        return _all_slots()

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        day_start = date.replace(hour=BUSINESS_START_HOUR, minute=0, second=0).isoformat() + "Z"
        day_end = date.replace(hour=BUSINESS_END_HOUR, minute=0, second=0).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=day_start,
            timeMax=day_end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        booked_times = set()
        for event in events_result.get("items", []):
            start = event.get("start", {}).get("dateTime", "")
            if start:
                try:
                    event_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    booked_times.add(event_time.hour)
                except Exception:
                    pass

        # Build list of free slots
        available = []
        for hour in range(BUSINESS_START_HOUR, BUSINESS_END_HOUR):
            if hour not in booked_times:
                slot_time = datetime(date.year, date.month, date.day, hour)
                available.append(slot_time.strftime("%-I:%M %p"))

        return available

    except Exception as e:
        print(f"[calendar] get_available_slots error: {e}")
        return _all_slots()


def check_admin_conflict(date_str: str, time_str: str) -> bool:
    """
    Returns True if the admin calendar already has an event
    at the given date+time (within a 1-hour window).
    """
    service = _get_admin_calendar_service()
    if not service:
        return False  # If calendar unavailable, don't block booking

    try:
        slot_start = _parse_slot_datetime(date_str, time_str)
        if not slot_start:
            return False

        slot_end = slot_start + timedelta(hours=1)
        time_min = slot_start.isoformat() + "Z"
        time_max = slot_end.isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
        ).execute()

        return len(events_result.get("items", [])) > 0

    except Exception as e:
        print(f"[calendar] check_admin_conflict error: {e}")
        return False


def create_admin_event(booking_data: dict, clinic: dict) -> Optional[str]:
    """
    Creates a Google Calendar event on the admin calendar for the booking.
    Returns the event ID on success, or None on failure.
    """
    service = _get_admin_calendar_service()
    if not service:
        return None

    try:
        slot_start = _parse_slot_datetime(
            booking_data.get("appointment_date", ""),
            booking_data.get("time_slot", ""),
        )
        if not slot_start:
            return None

        slot_end = slot_start + timedelta(hours=1)
        patient = booking_data.get("patient_name", "Patient")
        doctor = clinic.get("name", "Clinic")
        address = clinic.get("address", "")
        specialty = booking_data.get("specialty", "")
        bid = booking_data.get("booking_id", "")

        event = {
            "summary": f"Appointment — {patient} with {doctor}",
            "location": address,
            "description": (
                f"Booking ID: {bid}\n"
                f"Patient: {patient}\n"
                f"Specialty: {specialty}\n"
                f"Email: {booking_data.get('email_id', '')}\n"
                f"Clinic: {doctor}\n"
                f"Address: {address}"
            ),
            "start": {"dateTime": slot_start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": slot_end.isoformat(), "timeZone": "UTC"},
        }

        created = service.events().insert(calendarId="primary", body=event).execute()
        return created.get("id")

    except Exception as e:
        print(f"[calendar] create_admin_event error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_slot_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Parses 'YYYY-MM-DD' + '10:00 AM' into a datetime object."""
    time_str = time_str.strip().upper()
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            t = datetime.strptime(time_str, fmt)
            d = datetime.strptime(date_str, "%Y-%m-%d")
            return d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        except ValueError:
            continue
    return None


def _all_slots() -> list[str]:
    """Returns all 1-hour slots from 8AM to 5PM as fallback."""
    slots = []
    for hour in range(BUSINESS_START_HOUR, BUSINESS_END_HOUR):
        dt = datetime(2000, 1, 1, hour)
        slots.append(dt.strftime("%-I:%M %p"))
    return slots
