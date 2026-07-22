import random
import string
from datetime import date, datetime

from app.models.database import get_supabase_client
from .models import BookingCreateRequest, BookingResponse
from .validator import BookingValidator
from .email_service import EmailService


# ---------------------------------------------------------------------------
# Exceptions — defined right here until there's a reason to share them
# ---------------------------------------------------------------------------


class BookingValidationError(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("Booking validation failed")


class SlotConflictError(Exception):
    def __init__(self, message: str, suggested_slots: list[str]):
        self.message = message
        self.suggested_slots = suggested_slots
        super().__init__(message)


def _generate_booking_id() -> str:
    suffix = "".join(random.choices(string.digits, k=5))
    return f"APT-{suffix}"


# ---------------------------------------------------------------------------
# BookingService Orchestrator
# ---------------------------------------------------------------------------


class BookingService:
    """
    Orchestrates the booking pipeline:
      validate → check slot → save → send email confirmation.
    Fails fast on database or infrastructure errors.
    """

    def __init__(self, email_service: EmailService | None = None):
        self._email = email_service or EmailService()

    async def create_booking(self, req: BookingCreateRequest) -> BookingResponse:
        """
        Executes the 4-step booking pipeline.
        Raises BookingValidationError on invalid input.
        Raises SlotConflictError if the requested slot is taken.
        Returns BookingResponse on success.
        """
        self._validate_request(req)
        self._check_slot(req)
        saved = self._save_booking(req)
        await self._send_confirmation(saved)

        return BookingResponse(
            id=saved.get("booking_id") or str(saved.get("id")),
            clinic_id=req.clinic_id,
            clinic_name=saved["clinic_name"],
            clinic_address=saved.get("clinic_address"),
            specialty=saved.get("specialty"),
            patient_name=saved["patient_name"],
            patient_email=saved.get("email_id") or req.patient_email,
            patient_phone=req.patient_phone,
            appointment_date=str(saved["appointment_date"]),
            time_slot=saved["time_slot"],
            notes=saved.get("reason"),
            status=saved.get("status", "confirmed"),
            created_at=str(saved.get("created_at", datetime.utcnow().isoformat())),
        )

    # -----------------------------------------------------------------------
    # Private Step Pipeline
    # -----------------------------------------------------------------------

    def _validate_request(self, req: BookingCreateRequest) -> None:
        errors = BookingValidator.validate(req)
        if errors:
            raise BookingValidationError(errors)

    def _check_slot(self, req: BookingCreateRequest) -> None:
        if not self._is_slot_available(req.clinic_name, req.appointment_date, req.time_slot):
            suggested = self._suggest_alternatives(req.clinic_name, req.appointment_date)
            raise SlotConflictError(
                message=(
                    f"The selected time slot ({req.time_slot} on {req.appointment_date}) "
                    f"is no longer available at {req.clinic_name}."
                ),
                suggested_slots=suggested,
            )

    def _save_booking(self, req: BookingCreateRequest) -> dict:
        booking_id_str = _generate_booking_id()
        row = {
            "booking_id": booking_id_str,
            "clinic_name": req.clinic_name,
            "clinic_address": req.clinic_address,
            "specialty": req.specialty,
            "patient_name": req.patient_name,
            "email_id": req.patient_email,
            "appointment_date": str(req.appointment_date),
            "time_slot": req.time_slot,
            "reason": req.notes,
            "status": "confirmed",
        }
        client = get_supabase_client()
        # Fail Fast: No try/except fallback. If schema or DB fails, raise exception immediately.
        response = client.table("bookings").insert(row).execute()
        if not response.data:
            raise RuntimeError("Failed to save booking to database.")

        return response.data[0]

    async def _send_confirmation(self, booking: dict) -> None:
        await self._email.send_booking_confirmation(booking)

    # -----------------------------------------------------------------------
    # Slot Helpers (merged into BookingService)
    # -----------------------------------------------------------------------

    def _is_slot_available(self, clinic_name: str, appointment_date: date, time_slot: str) -> bool:
        client = get_supabase_client()
        response = (
            client.table("bookings")
            .select("id")
            .eq("clinic_name", clinic_name)
            .eq("appointment_date", str(appointment_date))
            .eq("time_slot", time_slot)
            .execute()
        )
        return len(response.data) == 0

    def _suggest_alternatives(self, clinic_name: str, appointment_date: date) -> list[str]:
        client = get_supabase_client()
        response = (
            client.table("bookings")
            .select("time_slot")
            .eq("clinic_name", clinic_name)
            .eq("appointment_date", str(appointment_date))
            .execute()
        )
        booked = {row["time_slot"] for row in response.data}
        return [slot for slot in BookingValidator.ALL_SLOTS if slot not in booked]
