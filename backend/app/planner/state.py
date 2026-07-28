from enum import Enum
from typing import Optional
from pydantic import BaseModel


class LocationType(str, Enum):
    CITY = "city"
    CURRENT_LOCATION = "current_location"
    UNKNOWN = "unknown"


class SearchStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    AWAITING_LOCATION = "awaiting_location"
    EMPTY = "empty"
    HAS_RESULTS = "has_results"


class CurrentLocation(BaseModel):
    latitude: float
    longitude: float


class ClinicSelection(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    rating: Optional[float] = None


class PlannerState(BaseModel):

    specialty: Optional[str] = None
    location_type: LocationType = LocationType.UNKNOWN
    city: Optional[str] = None
    current_location: Optional[CurrentLocation] = None
    selected_clinic: Optional[ClinicSelection] = None
    search_status: SearchStatus = SearchStatus.NOT_ATTEMPTED
    booking_completed: bool = False

    @property
    def specialty_known(self) -> bool:
        return bool(self.specialty and self.specialty.strip())

    @property
    def location_known(self) -> bool:
        if self.location_type == LocationType.CITY:
            return bool(self.city and self.city.strip())
        if self.location_type == LocationType.CURRENT_LOCATION:
            return True
        return bool(self.city and self.city.strip())

    @property
    def clinic_selected(self) -> bool:
        return self.selected_clinic is not None