from enum import Enum
from typing import Optional
from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# MedicalStatus
# ---------------------------------------------------------------------------


class MedicalStatus(str, Enum):
    DIAGNOSED = "diagnosed"
    CLARIFYING = "clarifying"

# ---------------------------------------------------------------------------
# MedicalDecision
# ---------------------------------------------------------------------------


class MedicalDecision(BaseModel):
    status: MedicalStatus
    specialty: Optional[str] = None
    symptoms_summary: Optional[str] = None
    location_type: Optional[str] = None
    city: Optional[str] = None
    is_direct_request: bool = False
    clarification_question: Optional[str] = None

    @model_validator(mode="after")
    def _enforce_invariants(self) -> "MedicalDecision":
        if self.status == MedicalStatus.DIAGNOSED and not self.specialty:
            raise ValueError(
                "A DIAGNOSED MedicalDecision must include a specialty. "
                "Set specialty to a non-empty string."
            )
        if self.status == MedicalStatus.CLARIFYING and not self.clarification_question:
            raise ValueError(
                "A CLARIFYING MedicalDecision must include a clarification_question. "
                "Set clarification_question to a non-empty string."
            )
        return self
