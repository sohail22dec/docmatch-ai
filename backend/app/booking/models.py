from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class BookingCreateRequest(BaseModel):
    """Structured payload submitted from the frontend Booking Form."""

    session_id: Optional[str] = None

    # Clinic info (sourced from the ClinicCard that was clicked)
    clinic_id: str = Field(description="Stable Google Place ID for the clinic")
    clinic_name: str = Field(description="Display name of the clinic")
    clinic_address: Optional[str] = Field(None, description="Physical address of the clinic")
    specialty: Optional[str] = Field(None, description="Medical specialty")

    # Patient info
    patient_name: str = Field(description="Full name of the patient")
    patient_email: str = Field(description="Email address for confirmation")
    patient_phone: str = Field(description="Contact phone number")

    # Appointment
    appointment_date: date = Field(description="Preferred date (YYYY-MM-DD)")
    time_slot: str = Field(description="Preferred time slot, e.g. '10:00 AM'")
    notes: Optional[str] = Field(None, description="Optional reason or notes for the visit")


class BookingResponse(BaseModel):
    """Returned to the frontend after a successful booking."""

    id: str
    clinic_id: str
    clinic_name: str
    clinic_address: Optional[str]
    specialty: Optional[str]
    patient_name: str
    patient_email: str
    patient_phone: str
    appointment_date: str
    time_slot: str
    notes: Optional[str]
    status: str
    created_at: str


class SlotConflictResponse(BaseModel):
    """Returned when the requested slot is already taken."""

    error_code: str = "SLOT_UNAVAILABLE"
    message: str
    suggested_slots: list[str] = Field(default_factory=list)
