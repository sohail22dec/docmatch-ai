from langchain_groq import ChatGroq
from app.core.config import settings
from app.agent.state import AgentState


# System prompt for the triage agent
SYSTEM_PROMPT = """You are a highly capable Medical Triage Assistant. 
Your job is to:
1. Listen to the patient's symptoms.
2. Ask clarifying questions if the symptoms are too vague.
3. Use the `search_medical_web` tool to find relevant medical information or potential causes for symptoms.

Always be empathetic, professional, and clear. 
IMPORTANT: You are an AI, not a human doctor. Always advise the patient to seek professional medical help for emergencies.

CRITICAL INSTRUCTION FOR TOOLS: 
If a tool returns an error (e.g., "REQUEST_DENIED", "API Key invalid", or any HTTP error), DO NOT attempt to call the exact same tool again. Simply inform the user that you are currently unable to access that specific service and try to help them using your other available tools or general knowledge.
"""


def make_triage_node(tools):
    """
    Returns the triage node function, with the MCP tools pre-loaded.
    """

    async def triage_node(state: AgentState):
        """
        The main reasoning node. It uses Groq to process the conversation history
        and decide what to do next (chat, search web, or find maps).
        """
        messages = state.get("messages", [])

        # Initialize the LLM (Groq is very fast)
        llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model="llama-3.3-70b-versatile",  # or another groq model you prefer
            temperature=0.0,
        )

        # Bind the pre-loaded tools to the LLM
        llm_with_tools = llm.bind_tools(tools)

        # Ensure the system prompt is always present
        from langchain_core.messages import SystemMessage

        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        # Invoke the LLM
        response = await llm_with_tools.ainvoke(messages)

        # Return the new state (the response will be appended to the messages list)
        return {"messages": [response]}

    return triage_node
