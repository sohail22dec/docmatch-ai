from enum import Enum
from pydantic import BaseModel, Field


class Capability(str, Enum):
    MEDICAL = "medical"
    SEARCH = "search"
    BOOKING = "booking"
    RESPONSE = "response"
    COMPLETE = "complete"


class MissingInfo(str, Enum):
    SPECIALTY = "specialty"
    LOCATION = "location"
    SEARCH_RESULTS = "search_results"
    CLINIC_SELECTION = "clinic_selection"


class PlannerDecision(BaseModel):
    capability: Capability
    missing_info: list[MissingInfo] = Field(default_factory=list)