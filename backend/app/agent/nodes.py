import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from app.core.config import settings
from app.agent.state import AgentState


def _get_llm(temperature: float = 0.0):
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------

# Intent classification prompt for the orchestrator
INTENT_PROMPT = """You are an intent classifier for a medical assistant chatbot.
Look at the user's LATEST message and classify it into exactly one of these intents:

1. "clinic_search" - User is describing symptoms or asking to find a doctor/clinic/specialist
   Examples: "I have a rash", "find me a cardiologist", "my chest hurts"

2. "general_qa" - User is asking a general question, follow-up about a specific doctor, or anything else
   Examples: "what is Dr. X's phone number?", "what are symptoms of diabetes?", "tell me more about clinic 3"

Respond with ONLY one word: clinic_search OR general_qa
"""


async def orchestrator_node(state: AgentState) -> dict:
    """
    Central decision-maker. First classifies intent, then routes accordingly.
    """
    final = state.get("final_response")
    specialty = state.get("specialty_needed")
    latitude = state.get("latitude")
    city = state.get("city")
    clinics = state.get("clinics_found")
    searched = state.get("search_attempted", False)

    # If any agent has already produced a final response → done
    if final:
        return {"next": "END"}

    # Mid-pipeline routing (specialty already identified → continue the clinic flow)
    if specialty:
        if latitude is None and not city:
            return {"next": "location_agent"}
        if clinics is None and not searched:
            return {"next": "search_agent"}
        if clinics is not None or searched:
            return {"next": "formatter_agent"}

    # Fresh message — classify intent first
    messages = state.get("messages", [])
    latest_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_user_msg = msg.content
            break

    if not latest_user_msg:
        return {"next": "END"}

    llm = _get_llm()
    intent_resp = await llm.ainvoke(
        [
            SystemMessage(content=INTENT_PROMPT),
            HumanMessage(content=latest_user_msg),
        ]
    )
    intent = intent_resp.content.strip().lower()

    if "clinic_search" in intent:
        return {"next": "symptom_agent"}
    else:
        return {"next": "general_qa_agent"}


# ---------------------------------------------------------------------------
# SYMPTOM AGENT
# ---------------------------------------------------------------------------

SYMPTOM_PROMPT = """You are a medical triage specialist. 
Your job is to read the user's conversation and determine if you have enough information to assign a medical specialty.

Rules:
- Respond with ONLY a JSON object.
- If the latest message is "📍 Location shared automatically":
    - If symptoms were ALREADY discussed: Ignore the location message and continue the triage (re-ask your last question if needed).
    - If NO symptoms have been mentioned yet: Ask "I've received your location! What symptoms are you experiencing today so I can help you find the right doctor?"
- If symptoms are vague (e.g. "headache", "stomach hurts"), ask a clarifying question.
  Format: {"status": "clarifying", "message": "When did the headache start and how severe is it?"}
- If symptoms are clear, assign a specialist.
  Format: {"status": "diagnosed", "specialty": "Neurologist", "symptoms_summary": "severe headache for 3 days"}
- Choose from common specialties: Dermatologist, Cardiologist, Neurologist, Orthopedist, Pediatrician, Psychiatrist, Gastroenterologist, ENT Specialist, Ophthalmologist, General Physician, Dentist, Gynecologist, Urologist, Pulmonologist.
- Do NOT include any other text — only the JSON object.
"""


async def symptom_agent(state: AgentState) -> dict:
    """
    Reads the user's symptoms and outputs the required medical specialty.
    Can ask clarifying questions if symptoms are too vague.
    """
    messages = state.get("messages", [])

    llm = _get_llm(temperature=0.2)
    prompt_messages = [SystemMessage(content=SYMPTOM_PROMPT)]

    # Pass recent conversation context so it remembers its own clarifying questions
    recent_messages = messages[-6:] if len(messages) > 6 else messages
    prompt_messages.extend(recent_messages)

    response = await llm.ainvoke(prompt_messages)

    try:
        # Strip markdown block if llm wrapped the json
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]

        data = json.loads(content.strip())
        status = data.get("status")

        if status == "clarifying":
            return {
                "messages": [
                    AIMessage(
                        content=data.get("message", "Could you provide more details?")
                    )
                ],
                "final_response": data.get(
                    "message", "Could you provide more details?"
                ),
            }
        else:
            return {
                "specialty_needed": data.get("specialty", "General Physician"),
                "symptoms": data.get("symptoms_summary", "General symptoms"),
            }
    except Exception as e:
        print(f"[symptom_agent] JSON parsing error: {e}")
        return {
            "specialty_needed": "General Physician",
            "symptoms": "General symptoms",
        }


# ---------------------------------------------------------------------------
# LOCATION AGENT
# ---------------------------------------------------------------------------


async def location_agent(state: AgentState) -> dict:
    """
    Checks if GPS was provided. If not, generates a polite message asking
    the user for their city and ends the graph turn — the user must reply
    with their city in the next message.
    """
    specialty = state.get("specialty_needed", "a doctor")

    ask_message = (
        f"I can help you find a **{specialty}** near you! 🩺\n\n"
        f'To find the closest clinics, I need your location. Please **allow location access** when your browser asks, or simply **type your city name** (e.g., "Malda" or "Mumbai").'
    )

    return {
        "messages": [AIMessage(content=ask_message)],
        "final_response": ask_message,  # Signals orchestrator → END
        "location_source": "none",
        "action_required": "request_location",
    }


# ---------------------------------------------------------------------------
# SEARCH AGENT
# ---------------------------------------------------------------------------


async def search_agent(state: AgentState) -> dict:
    """
    Searches for clinics using a 3-step fallback chain:
    1. Google Maps Places API (lat/lng or city)
    2. Tavily web search (fallback)
    """
    specialty = state.get("specialty_needed", "doctor")
    latitude = state.get("latitude")
    longitude = state.get("longitude")
    city = state.get("city")

    clinics = []

    # ---- Step 1: Google Maps Places API ----
    try:
        import httpx

        if latitude and longitude:
            # Nearby search by GPS coordinates
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{latitude},{longitude}",
                "radius": 10000,  # 10 km
                "keyword": specialty,
                "key": settings.GOOGLE_MAPS_API_KEY,
            }
        else:
            # Text search by city name
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                "query": f"{specialty} in {city}",
                "key": settings.GOOGLE_MAPS_API_KEY,
            }

        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") == "OK":
            for place in data.get("results", [])[:8]:
                clinics.append(
                    {
                        "name": place.get("name"),
                        "address": place.get("formatted_address")
                        or place.get("vicinity"),
                        "rating": place.get("rating"),
                        "open_now": place.get("opening_hours", {}).get("open_now"),
                        "source": "Google Maps",
                    }
                )
        else:
            print(f"[search_agent] Google Maps status: {data.get('status')}")

    except Exception as e:
        print(f"[search_agent] Google Maps error: {e}")

    # ---- Step 2: Tavily fallback ----
    if not clinics:
        try:
            from tavily import TavilyClient

            location_str = city or f"near coordinates {latitude},{longitude}"
            query = (
                f"{specialty} clinics in {location_str} with address and phone number"
            )
            tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
            results = tavily.search(query=query, search_depth="advanced").get(
                "results", []
            )
            for r in results[:5]:
                clinics.append(
                    {
                        "name": r.get("title"),
                        "address": r.get("url"),
                        "rating": None,
                        "open_now": None,
                        "source": "Tavily",
                    }
                )
        except Exception as e:
            print(f"[search_agent] Tavily error: {e}")

    return {
        "clinics_found": clinics,
        "search_attempted": True,
    }


# ---------------------------------------------------------------------------
# FORMATTER AGENT
# ---------------------------------------------------------------------------

FORMATTER_PROMPT = """You are a helpful medical assistant presenting clinic search results to a user.
Format the provided clinic data into a clean, friendly response.

Rules:
- Start with "I found X {specialty} near you:"
- List each clinic with: name, address, rating (if available), open now status (if available)
- Use emojis sparingly (📍 for address, ⭐ for rating, ✅/❌ for open status)
- If the list is empty, say "I couldn't find any {specialty} near {location}. Would you like me to search in a nearby larger city?"
- Keep it concise and easy to read
- End with a reminder to call ahead to confirm availability
"""


async def formatter_agent(state: AgentState) -> dict:
    """
    Takes clinics_found from state and produces a clean user-facing response.
    """
    clinics = state.get("clinics_found", [])
    specialty = state.get("specialty_needed", "doctor")
    city = state.get("city") or "your location"

    context = json.dumps(
        {
            "specialty": specialty,
            "location": city,
            "clinics": clinics,
        },
        indent=2,
    )

    llm = _get_llm(temperature=0.3)
    response = await llm.ainvoke(
        [
            SystemMessage(content=FORMATTER_PROMPT),
            HumanMessage(content=context),
        ]
    )

    return {
        "messages": [AIMessage(content=response.content)],
        "final_response": response.content,
    }


# ---------------------------------------------------------------------------
# GENERAL QA AGENT
# ---------------------------------------------------------------------------

GENERAL_QA_PROMPT = """You are a helpful medical assistant. Answer the user's question accurately and helpfully.

You have access to web search results (provided below) to help answer the question.
If the search results contain the answer, use them. If not, use your general medical knowledge.

Be conversational, empathetic, and concise. If the user is asking about a specific doctor's 
contact details and you have them from the search results, provide them clearly.
Always remind the user to verify contact details directly as they can change.
"""


async def general_qa_agent(state: AgentState) -> dict:
    """
    Handles general questions, follow-up questions about specific doctors,
    and any query that is NOT a clinic search request.
    Uses Tavily for live web search when needed.
    """
    messages = state.get("messages", [])
    latest_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_user_msg = msg.content
            break

    # Try Tavily search for specific factual questions (doctor contact, medical info)
    search_context = ""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        results = client.search(
            query=latest_user_msg,
            search_depth="basic",
        ).get("results", [])
        if results:
            snippets = [f"- {r.get('title')}: {r.get('content')}" for r in results[:3]]
            search_context = "Web search results:\n" + "\n".join(snippets)
    except Exception as e:
        print(f"[general_qa_agent] Tavily search error: {e}")

    llm = _get_llm(temperature=0.3)
    prompt_messages = [SystemMessage(content=GENERAL_QA_PROMPT)]

    # Include recent conversation context (last 6 messages) for follow-ups
    recent_messages = messages[-6:] if len(messages) > 6 else messages
    prompt_messages.extend(recent_messages)

    if search_context:
        prompt_messages.append(
            HumanMessage(
                content=f"{search_context}\n\nUser question: {latest_user_msg}"
            )
        )
    else:
        prompt_messages.append(HumanMessage(content=latest_user_msg))

    response = await llm.ainvoke(prompt_messages)

    return {
        "messages": [AIMessage(content=response.content)],
        "final_response": response.content,
    }
