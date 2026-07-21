from typing import Any, Protocol
from app.shared.conversation import ConversationTurn
from .models import MedicalDecision
from .parser import parse_medical_decision
from .prompt import MEDICAL_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# LLM Interface
# ---------------------------------------------------------------------------


class ChatModel(Protocol):

    async def ainvoke(self, messages: list) -> Any:
        ...


# ---------------------------------------------------------------------------
# Capability Entry Point
# ---------------------------------------------------------------------------


async def run(
    conversation: list[ConversationTurn],
    llm: ChatModel,
) -> MedicalDecision:
    messages = [
        {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
        *[{"role": turn.role, "content": turn.content} for turn in conversation],
    ]
    response = await llm.ainvoke(messages)
    return parse_medical_decision(response.content)
