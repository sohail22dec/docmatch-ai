from enum import Enum
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# SearchStatus
# ---------------------------------------------------------------------------


class SearchStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    EMPTY = "empty"
    HAS_RESULTS = "has_results"


# ---------------------------------------------------------------------------
# PlannerState
# ---------------------------------------------------------------------------


class PlannerState(BaseModel):

    specialty_known: bool = False
    location_known: bool = False
    search_status: SearchStatus = SearchStatus.NOT_ATTEMPTED
    clinic_selected: bool = False
    booking_completed: bool = False