from pydantic import BaseModel, Field
from typing import Optional, List


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


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    messages: List[Message]
    # Location data from the frontend 📍 button
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    location_denied: Optional[bool] = False
    specialty_needed: Optional[str] = None

    # Booking data from the frontend
    selected_clinic: Optional[dict] = None
    current_booking: Optional[dict] = None
    booking_confirmed: Optional[bool] = False
    booking_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    action: Optional[str] = None
    # Return booking state to frontend
    selected_clinic: Optional[dict] = None
    current_booking: Optional[dict] = None
    booking_confirmed: Optional[bool] = False
    booking_id: Optional[str] = None
    specialty_needed: Optional[str] = None
