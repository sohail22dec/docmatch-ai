from typing import Optional
from pydantic import BaseModel, Field


class Clinic(BaseModel):
    name: str
    address: str
    rating: Optional[float] = Field(default=None, description="Google Maps user rating")
    place_id: str = Field(description="Unique Google Maps Place ID")
