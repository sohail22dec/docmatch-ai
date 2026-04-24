# backend/app/models/schemas.py

from pydantic import BaseModel, Field
from typing import Optional

class Doctor(BaseModel):
    """Pydantic model representing a Doctor entity."""
    id: str = Field(description="Unique identifier for the doctor (e.g. from Google Maps)")
    name: str = Field(description="Name of the doctor or clinic")
    address: str = Field(description="Physical address of the clinic")
    specialty: Optional[str] = Field(None, description="Medical specialty if known")
    rating: Optional[float] = Field(None, description="Average user rating")
    
class AppointmentRequest(BaseModel):
    """Pydantic model representing a request to book an appointment."""
    doctor_id: str = Field(description="ID of the doctor to book with")
    patient_name: str = Field(description="Name of the patient")
    patient_email: str = Field(description="Email address of the patient")
    symptoms_summary: str = Field(description="Brief summary of symptoms")
    preferred_date: Optional[str] = Field(None, description="Preferred date in YYYY-MM-DD format")
