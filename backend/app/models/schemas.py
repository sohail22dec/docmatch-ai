from pydantic import BaseModel, Field
from typing import Optional


class Doctor(BaseModel):
    """Pydantic model representing a Doctor entity."""

    id: str = Field(
        description="Unique identifier for the doctor (e.g. from Google Maps)"
    )
    name: str = Field(description="Name of the doctor or clinic")
    address: str = Field(description="Physical address of the clinic")
    specialty: Optional[str] = Field(None, description="Medical specialty if known")
    rating: Optional[float] = Field(None, description="Average user rating")


class AppointmentRequest(BaseModel):
    """Pydantic model representing a request to book an appointment."""

    booking_id: str = Field(description="Human-readable ID e.g. APT-12345")
    clinic_name: str = Field(description="Name of the clinic")
    clinic_address: Optional[str] = Field(None, description="Address of the clinic")
    patient_name: str = Field(description="Name of the patient")
    appointment_date: str = Field(description="Date of the appointment")
    time_slot: str = Field(description="Preferred time slot")
    specialty: Optional[str] = Field(None, description="Medical specialty")
    reason: Optional[str] = Field(None, description="Symptoms or reason for visit")
