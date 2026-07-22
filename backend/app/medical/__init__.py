"""
medical — The DocMatch Medical Capability.

Single responsibility: understand the user's medical need.

Determines:
    • The required medical specialty
    • Whether clarification is needed (and what to ask)
    • A concise summary of symptoms
    • An optional city if explicitly mentioned by the user

Does NOT:
    • Search for clinics
    • Book appointments
    • Update PlannerState
    • Make planning decisions

Public API
----------
::

    from app.medical import run, MedicalDecision, MedicalStatus, ChatModel, MedicalParseWarning
    from app.shared.conversation import ConversationTurn

Usage example::

    conversation = [
        ConversationTurn(role="user", content="I have chest pain and shortness of breath"),
    ]
    decision = await run(conversation, llm=my_llm)

    if decision.status == MedicalStatus.DIAGNOSED:
        # Update PlannerState in the application layer
        print(f"Specialty: {decision.specialty}")
        print(f"Symptoms:  {decision.symptoms_summary}")
    else:
        # Return the clarification question to the user
        print(f"Ask: {decision.clarification_question}")

Note: ConversationTurn is imported from app.shared.conversation, not from
this package. This prevents capabilities from depending on each other.
"""

from .agent import run, ChatModel
from .models import MedicalStatus, MedicalDecision
from .parser import MedicalParseWarning
from .prompt import AVAILABLE_SPECIALTIES

__all__ = [
    "run",
    "ChatModel",
    "MedicalStatus",
    "MedicalDecision",
    "MedicalParseWarning",
    "AVAILABLE_SPECIALTIES",
]
