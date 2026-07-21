
import json
import re
import warnings
from typing import Optional
from pydantic import ValidationError
from .models import MedicalDecision, MedicalStatus


# ---------------------------------------------------------------------------
# Warning Class
# ---------------------------------------------------------------------------


class MedicalParseWarning(UserWarning):
    """
    Issued when an LLM response cannot be parsed into a MedicalDecision.

    The warning message includes:
    - The failure reason (exception type and message)
    - The first 200 characters of the raw LLM response for inspection

    Exported from this module so test code can assert on it directly.
    """


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> Optional[str]:
    # Remove markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Find the outermost { ... } pair
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        return None

    return text[start : end + 1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_medical_decision(raw: str) -> MedicalDecision:
    try:
        json_str = _extract_json(raw)
        if json_str is None:
            raise ValueError("No JSON object found in LLM response")

        data = json.loads(json_str)
        
        # Normalize city field to Python None if it contains "null", "None", "", etc.
        if isinstance(data, dict) and "city" in data:
            city_val = data["city"]
            if isinstance(city_val, str):
                cleaned = city_val.strip()
                if cleaned.lower() in ("null", "none", ""):
                    data["city"] = None
                else:
                    data["city"] = cleaned
            elif city_val is not None:
                data["city"] = None

        return MedicalDecision.model_validate(data)

    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        warnings.warn(
            f"MedicalParser failed — returning fallback. "
            f"Reason: {type(exc).__name__}: {exc}. "
            f"Raw response (first 200 chars): {raw[:200]!r}",
            MedicalParseWarning,
            stacklevel=2,
        )
        return MedicalDecision(
            status=MedicalStatus.CLARIFYING,
            clarification_question="Could you tell me more about your symptoms?",
        )
