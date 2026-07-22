import re
from datetime import date, time, datetime
from .models import BookingCreateRequest


class BookingValidator:
    """
    100% deterministic Python validation — no LLM.

    Validates:
    - Required fields are present and non-empty
    - Email format is valid
    - Phone number format is valid
    - Appointment date is not in the past
    - Appointment time is within business hours (9:00 AM – 5:00 PM)
    """

    BUSINESS_HOURS_START = time(9, 0)
    BUSINESS_HOURS_END = time(17, 0)

    # Single source of truth for 30-minute slots across the business day
    ALL_SLOTS: list[str] = [
        f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        for h in range(9, 17)
        for m in (0, 30)
    ]

    _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    _PHONE_RE = re.compile(r"^\+?[\d\s\-().]{7,20}$")

    @classmethod
    def validate(cls, req: BookingCreateRequest) -> list[dict]:
        """Return a list of field-level error dicts. Empty list = valid."""
        errors: list[dict] = []

        # 1. Required: patient_name
        if not req.patient_name or not req.patient_name.strip():
            errors.append({"field": "patient_name", "message": "Patient name is required"})

        # 2. Required: patient_email + format
        if not req.patient_email:
            errors.append({"field": "patient_email", "message": "Email address is required"})
        elif not cls._EMAIL_RE.match(req.patient_email):
            errors.append({"field": "patient_email", "message": "Invalid email address format"})

        # 3. Required: patient_phone + format
        if not req.patient_phone:
            errors.append({"field": "patient_phone", "message": "Phone number is required"})
        elif not cls._PHONE_RE.match(req.patient_phone):
            errors.append({"field": "patient_phone", "message": "Invalid phone number format"})

        # 4. Appointment date must not be in the past
        if req.appointment_date < date.today():
            errors.append({
                "field": "appointment_date",
                "message": "Appointment date cannot be in the past",
            })

        # 5. Time slot must be within business hours
        parsed = cls._parse_time_slot(req.time_slot)
        if parsed is None:
            errors.append({
                "field": "time_slot",
                "message": "Invalid time format. Use e.g. '10:00 AM'",
            })
        elif not (cls.BUSINESS_HOURS_START <= parsed <= cls.BUSINESS_HOURS_END):
            errors.append({
                "field": "time_slot",
                "message": "Appointment time must be within business hours (9:00 AM – 5:00 PM)",
            })

        return errors

    @classmethod
    def _parse_time_slot(cls, time_slot: str) -> time | None:
        """Parse '10:00 AM', '2:30 PM', '14:00', etc. Returns a time object or None on failure."""
        normalised = time_slot.strip().upper()
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                return datetime.strptime(normalised, fmt).time()
            except ValueError:
                continue
        return None
