import json
from datetime import datetime, timedelta
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langgraph.graph import END
from app.core.config import settings
from app.agent.state import AgentState
from app.models.crud import (
    create_booking,
)  # Imported at top level — avoids silent import failures
from app.agent.calendar_tools import (
    is_within_business_hours,
    check_admin_conflict,
    get_available_slots,
)


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

1. "clinic_search" - User is describing symptoms, asking to find a doctor/clinic/specialist, or specifically looking for medical help near their current location.
   Examples: "I have a rash", "find me a cardiologist", "my chest hurts", "find a doctor near me", "is there any clinic closer to me?", "I am in Mumbai, find a dentist"

2. "booking_request" - User wants to book an appointment, is providing booking details, OR is confirming/cancelling a booking.
   Examples: "I want to book with Dr. Akash", "book a visit", "I pick the first one", "My name is John",
   "Tomorrow at 10am", "john@example.com", "yes", "yes confirm", "ok", "sure", "sounds good",
   "correct", "that's right", "go ahead", "no", "cancel", "stop"

3. "general_qa" - User is asking a question or seeking information about a doctor, a disease, or a clinic already discussed.
   Examples: "where is his clinic?", "what is Dr. X's phone number?", "what are the symptoms of diabetes?", "tell me more about this doctor"

Respond with ONLY one word: clinic_search, booking_request, OR general_qa
"""


# ---------------------------------------------------------------------------
# CONTEXT CLINIC EXTRACTOR
# ---------------------------------------------------------------------------

EXTRACT_CLINIC_PROMPT = """You are a medical assistant. Read the conversation below and extract the name and address of the doctor or clinic that was most recently discussed.

Output ONLY a JSON object with this format:
{"name": "Doctor or Clinic Name", "address": "Address if known, otherwise null"}

If no specific doctor or clinic was discussed, output: {"name": null, "address": null}
Do NOT include any other text.
"""


async def _extract_clinic_from_context(messages: list) -> dict | None:
    """
    Reads the conversation history and extracts the doctor/clinic that was
    most recently discussed, so it can be used as selected_clinic for booking.
    """
    recent = messages[-8:] if len(messages) > 8 else messages
    llm = _get_llm(temperature=0)
    try:
        resp = await llm.ainvoke(
            [SystemMessage(content=EXTRACT_CLINIC_PROMPT)] + recent
        )
        content = resp.content.strip()
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]
        data = json.loads(content)
        if data.get("name"):
            return {
                "name": data["name"],
                "address": data.get("address") or "Address not available",
            }
    except Exception:
        pass
    return None


async def orchestrator_node(state: AgentState) -> dict:
    """
    Central decision-maker. Always re-classifies intent on every new user message
    FIRST, before falling back to state-machine routing. This ensures follow-up
    questions like 'tell me more about Dr. X' are never confused with a new search.
    """

    specialty = state.get("specialty_needed")
    latitude = state.get("latitude")
    city = state.get("city")
    clinics = state.get("clinics_found")
    searched = state.get("search_attempted", False)
    selected_clinic = state.get("selected_clinic")
    booking_confirmed = state.get("booking_confirmed", False)
    final_response = state.get("final_response")

    # CRITICAL: If an agent already produced a response for the user, STOP.
    if final_response:
        return {"next": END}

    # CRITICAL: If booking is already confirmed, route to confirmation_agent immediately.
    # This MUST be before intent classification to prevent 'yes' from being re-routed to booking_agent.
    if booking_confirmed:
        return {"next": "confirmation_agent"}

    # --- ALWAYS re-classify intent on every new user message ---
    messages = state.get("messages", [])
    latest_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            latest_user_msg = msg.content
            break

    intent = "none"
    if latest_user_msg:
        llm = _get_llm()
        intent_resp = await llm.ainvoke(
            [
                SystemMessage(content=INTENT_PROMPT),
                HumanMessage(content=latest_user_msg),
            ]
        )
        intent = intent_resp.content.strip().lower()

        # Detect if the user is genuinely asking a question
        question_words = [
            "what",
            "where",
            "when",
            "how",
            "why",
            "who",
            "which",
            "can you",
            "could you",
            "is there",
            "do you",
            "does",
            "?",
        ]
        is_a_question = any(w in latest_user_msg.lower() for w in question_words)

        # Fast-path: simple confirmation/cancellation words always go to booking_agent during active booking
        confirmation_words = [
            "yes",
            "no",
            "ok",
            "okay",
            "sure",
            "confirm",
            "correct",
            "right",
            "go ahead",
            "sounds good",
            "perfect",
            "cancel",
            "stop",
        ]
        is_simple_answer = latest_user_msg.strip().lower() in confirmation_words

        if selected_clinic and not booking_confirmed and is_simple_answer:
            return {"next": "booking_agent"}

        # 1. General QA: only interrupt an active booking if the message is actually a question
        if "general_qa" in intent:
            if selected_clinic and not booking_confirmed and not is_a_question:
                return {"next": "booking_agent"}
            return {"next": "general_qa_agent"}

        # 2. Explicit booking request or info provision
        if "booking_request" in intent:
            # Fix for booking-after-info bug
            if not selected_clinic and not clinics:
                extracted = await _extract_clinic_from_context(messages)
                if extracted:
                    return {"next": "booking_agent", "selected_clinic": extracted}
                else:
                    msg = "I'd love to help you book an appointment! Which doctor or clinic would you like to book with?"
                    return {
                        "next": END,
                        "messages": [AIMessage(content=msg)],
                        "final_response": msg,
                    }
            return {"next": "booking_agent"}

    # 3. PRIORITIZE BOOKING FLOW (Sticky Lock)
    # If a clinic is selected and no intent matched above, stay in booking mode.
    if selected_clinic and not booking_confirmed:
        return {"next": "booking_agent"}

    # 4. Routing based on intent for other flows
    if "clinic_search" in intent:
        # clinic_search intent with no specialty yet → triage symptoms first
        if specialty is None:
            return {"next": "symptom_agent"}

    # specialty is known and intent is clinic_search (or no explicit intent) → run state machine

    # location_agent: latitude and city are both missing
    if latitude is None and not city:
        return {"next": "location_agent"}

    # search_agent: haven't searched yet
    if clinics is None and not searched:
        return {"next": "search_agent"}

    # formatter_agent: clinics found but not yet presented
    if clinics is not None and selected_clinic is None:
        return {"next": "formatter_agent"}

    # confirmation_agent: booking is confirmed
    if booking_confirmed:
        return {"next": "confirmation_agent"}

    return {"next": END}


# ---------------------------------------------------------------------------
# SYMPTOM AGENT
# ---------------------------------------------------------------------------

SYMPTOM_PROMPT = """You are a concise medical triage specialist working for DocMatch AI, an app that helps users find and book specialist doctors.

Your ONLY goal is to determine the correct medical specialty so you can then help the user find a doctor.

CRITICAL RULES:
- NEVER correct the user's grammar or spelling. Ignore language errors completely.
- NEVER give medical advice, diagnoses, or treatment suggestions.
- NEVER give long explanations. Be short and direct.
- NEVER ask a question if you already have enough information to identify the specialty.
- If you must ask, ask only ONE focused question per turn. Never ask multiple questions at once.
- Never ask more than 2-3 questions total across the whole conversation. If you still aren't sure after 2 questions, pick the most likely specialty.
- Respond with ONLY a JSON object.

RULES FOR IDENTIFYING SPECIALTY:
- If the user explicitly requests a specific doctor or specialty (e.g. "find a gynecologist", "I need a dentist", "where is a cardiologist"), immediately output the diagnosed status.
- If the user's symptoms clearly point to a specialty, immediately diagnose without asking.
- Only ask a clarifying question if the symptoms are too vague AND you genuinely cannot determine the right specialist without more info.
- If the latest message is "📍 Here is my current location.":
    - If symptoms were ALREADY discussed: re-ask your last clarifying question if still needed, or diagnose.
    - If NO symptoms yet: Ask "Got your location! What symptoms are you experiencing so I can find the right doctor for you?"

OUTPUT FORMATS (JSON only, no other text):
- When asking a question: {"status": "clarifying", "message": "Your single focused question here"}
- When specialty is identified: {"status": "diagnosed", "specialty": "Neurologist", "city": "Mumbai", "symptoms_summary": "severe headache for 3 days"}
- If no city is mentioned, leave "city" as null.

Available specialties: Dermatologist, Cardiologist, Neurologist, Orthopedist, Pediatrician, Psychiatrist, Gastroenterologist, ENT Specialist, Ophthalmologist, General Physician, Dentist, Gynecologist, Urologist, Pulmonologist.
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
        content = response.content.strip()
        # More robust JSON extraction to handle leading/trailing text and markdown
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]

        data = json.loads(content)
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
            specialty = data.get("specialty", "General Physician")
            city = data.get("city")
            symptoms_summary = data.get("symptoms_summary", "General symptoms")

            if "directly requested" in symptoms_summary.lower():
                diag_msg = f"Got it! Based on your request, you should visit a **{specialty}**. Would you like me to help you find one nearby? 🩺"
            else:
                diag_msg = f"Based on your symptoms, you should visit a **{specialty}**. Would you like me to help you find one nearby? 🩺"

            if city:
                diag_msg += f" I'll search for clinics in **{city}** right away."

            return {
                "specialty_needed": specialty,
                "city": city,
                "symptoms": data.get("symptoms_summary", "General symptoms"),
                "messages": [AIMessage(content=diag_msg)],
                # Note: No final_response here so orchestrator continues to search/location
            }
    except Exception as e:
        print(f"[symptom_agent] JSON parsing error: {e} - Content: {response.content}")
        return {
            "specialty_needed": "General Physician",
            "symptoms": "General symptoms",
            "messages": [
                AIMessage(
                    content="I'm analyzing your symptoms. Let me find the right specialist for you."
                )
            ],
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
    messages = state.get("messages", [])

    prefix = ""
    if messages and (
        isinstance(messages[-1], AIMessage) or getattr(messages[-1], "type", "") == "ai"
    ):
        prefix = messages[-1].content + "\n\n"

    # Don't say "I can help you find a X" twice if the prefix already implies it
    if "I can help you find" in prefix:
        ask_message = f"{prefix}To find the closest clinics, I am requesting your location now. Please click **Allow** on the popup that just appeared. (If you prefer not to share your GPS, you can deny the request and simply type your city name instead)."
    else:
        ask_message = (
            f"{prefix}I can help you find a **{specialty}** near you! 🩺\n\n"
            "To find the closest clinics, I am requesting your location now. Please click **Allow** on the popup that just appeared. (If you prefer not to share your GPS, you can deny the request and simply type your city name instead)."
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


def _reverse_geocode(latitude: float, longitude: float) -> str | None:
    """
    Use OpenStreetMap Nominatim to convert GPS coordinates to a city name.
    Free, no API key required. Returns the most specific city/town/village name.
    """
    try:
        import httpx

        resp = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "zoom": 10,
                "accept-language": "en",
            },
            headers={"User-Agent": "DocMatchAI/1.0"},
            timeout=5,
        )
        data = resp.json()
        addr = data.get("address", {})
        return (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("county")
            or addr.get("state")
        )
    except Exception:
        return None


async def search_agent(state: AgentState) -> dict:
    """
    Searches for clinics using a 2-step fallback chain:
    1. Google Maps Places API (lat/lng or city) — best results, requires billing
    2. Tavily web search — uses actual city name reverse-geocoded from GPS coordinates
    """
    specialty = state.get("specialty_needed", "doctor")
    latitude = state.get("latitude")
    longitude = state.get("longitude")
    city = state.get("city")

    clinics = []
    geocoded_city = city  # Will be updated if we reverse geocode

    # ── Step 1: Resolve city from GPS if not already known ────────────────────
    if latitude and longitude and not city:
        geocoded_city = _reverse_geocode(latitude, longitude)
        if geocoded_city:
            print(
                f"[search_agent] Reverse geocoded: ({latitude},{longitude}) → {geocoded_city}"
            )

    # ── Step 2: Google Maps Places API ───────────────────────────────────────
    try:
        import httpx

        if latitude and longitude:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{latitude},{longitude}",
                "radius": 10000,
                "keyword": specialty,
                "key": settings.GOOGLE_MAPS_API_KEY,
            }
        else:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                "query": f"{specialty} in {geocoded_city or city}",
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
            print(
                f"[search_agent] Google Maps: {data.get('status')} — {data.get('error_message', '')}"
            )

    except Exception as e:
        print(f"[search_agent] Google Maps exception: {e}")

    # ── Step 3: Tavily web search (uses real city name from reverse geocoding) ─
    if not clinics:
        try:
            from tavily import TavilyClient

            location_str = (
                geocoded_city
                or city
                or (f"near {latitude},{longitude}" if latitude else "nearby")
            )
            query = f"best {specialty} clinics doctors in {location_str} address phone number"
            print(f"[search_agent] Tavily query: {query}")
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
        # Also update city if we reverse-geocoded it
        **({"city": city} if city and not state.get("city") else {}),
    }


# ---------------------------------------------------------------------------
# FORMATTER AGENT
# ---------------------------------------------------------------------------

FORMATTER_PROMPT = """You are a professional medical assistant. Your goal is to present clinic search results in a clean, structured format.

Instructions:
1. Start with a friendly intro: "I found [count] [specialty] near you in [location]:"
2. For each clinic, output it EXACTLY like this:
   ---CLINIC---
   NAME: [Clinic Name]
   RATING: [Rating]
   ADDRESS: [Full Address]
   ---END---
   
3. End with a helpful tip: "I recommend calling ahead to confirm their current availability."
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
# BOOKING AGENT
# ---------------------------------------------------------------------------

BOOKING_EXTRACT_PROMPT = """You are a medical booking assistant. Extract booking information from the user's message.

Today's Date: {today}
14-Day Window Ends: {fourteen_days_later}
Last Question Asked: {last_question}
User Message: {user_msg}
Current Booking Data: {current_data}

Rules:
1. Extract "patient_name", "appointment_date", "time_slot", and "email_id" ONLY if the user is clearly providing them in response to a question.
2. If the user mentions a name in passing earlier in the chat, do NOT extract it as "patient_name" yet. Wait until you have asked "What is your name?".
3. Use the "Last Question Asked" as context. If you asked for a name and they said "Sohail", that is the "patient_name".
4. For "appointment_date", you MUST output the date in YYYY-MM-DD format. Use "Today's Date" {today} as reference.
5. If the user specifies a date, ensure it is strictly between Today and the 14-Day Window. If invalid, output "INVALID_DATE".
6. Respond with ONLY a JSON object. No conversational text.
7. If no new info is found, return {{}}.
"""


async def booking_agent(state: AgentState) -> dict:
    """
    Handles the booking conversation. Inspects current_booking to find missing fields.
    Supports cancellation.
    """
    messages = state.get("messages", [])
    latest_msg = messages[-1].content.lower() if messages else ""

    # Check for cancellation
    if any(
        word in latest_msg for word in ["cancel", "stop", "never mind", "dont want"]
    ):
        return {
            "selected_clinic": None,
            "current_booking": None,
            "messages": [
                AIMessage(
                    content="No problem, I've canceled the booking request. How else can I help you?"
                )
            ],
            "final_response": "Booking canceled.",
        }

    current_booking = state.get("current_booking") or {}
    clinic = state.get("selected_clinic")
    clinics_found = state.get("clinics_found", [])

    # 1. If clinic is NOT set, try to find which one user mentioned
    if not clinic and clinics_found:
        latest_msg = messages[-1].content.lower()
        for c in clinics_found:
            name = c.get("name", "").lower()
            if name in latest_msg or (
                len(name.split()) > 1 and name.split()[0] in latest_msg
            ):
                clinic = c
                break

        if not clinic:
            # Could not identify which clinic. Ask user which doctor they want to book.
            msg = "Which doctor or clinic would you like to book an appointment with? Please let me know their name."
            return {"messages": [AIMessage(content=msg)], "final_response": msg}

    # 2. Extract info from latest message
    llm = _get_llm(temperature=0)
    user_input = messages[-1].content if messages else ""
    user_input_lower = user_input.lower().strip()

    # --- SMART KEYWORD FALLBACK ---
    # For one-word answers, don't even wait for the LLM
    if len(user_input.split()) <= 2:
        if any(w in user_input_lower for w in ["morning", "afternoon", "evening"]):
            current_booking["time_slot"] = user_input.capitalize()
        now = datetime.now()
        if "today" in user_input_lower:
            current_booking["appointment_date"] = now.strftime("%Y-%m-%d")
        elif "tomorrow" in user_input_lower:
            current_booking["appointment_date"] = (now + timedelta(days=1)).strftime(
                "%Y-%m-%d"
            )

    # Get last AI message for context
    last_ai_msg = ""
    for msg in reversed(messages[:-1]):
        if hasattr(msg, "type") and msg.type == "ai":
            last_ai_msg = msg.content
            break

    # Get current date context
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d, %A")
    fourteen_days_later_str = (now + timedelta(days=14)).strftime("%Y-%m-%d, %A")

    extract_resp = await llm.ainvoke(
        [
            SystemMessage(
                content=BOOKING_EXTRACT_PROMPT.format(
                    today=today_str,
                    fourteen_days_later=fourteen_days_later_str,
                    current_data=json.dumps(current_booking),
                    user_msg=user_input,
                    last_question=last_ai_msg,
                )
            )
        ]
    )

    try:
        content = extract_resp.content.strip()
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]

        new_data = json.loads(content)
        current_booking.update(new_data)
    except Exception:
        pass

    # 3. Find first missing field
    if not clinic:
        msg = "I'm ready to help you book an appointment! Which doctor or clinic would you like to visit?"
        return {"messages": [AIMessage(content=msg)], "final_response": msg}

    # Converational Step-by-Step flow
    patient_name = current_booking.get("patient_name")
    if not patient_name or len(str(patient_name).strip()) < 2:
        clinic_name = clinic.get("name", "the clinic")
        msg = f"I'd be happy to help you schedule an appointment with **{clinic_name}**. \n\nFirst, could you please tell me your **full name**?"
        return {
            "selected_clinic": clinic,
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    appointment_date = current_booking.get("appointment_date")
    if not appointment_date or appointment_date == "INVALID_DATE":
        if appointment_date == "INVALID_DATE":
            current_booking.pop("appointment_date", None)
            msg = f"I'm sorry, {patient_name.split()[0]}, but we can only schedule appointments up to 14 days in advance. What **valid date** would you like to book?"
        else:
            msg = f"Nice to meet you, {patient_name.split()[0]}! \nWhat **date** would you like to book your appointment for? (e.g., **Tomorrow**, **Next Monday**)."

        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    time_slot = current_booking.get("time_slot")
    if not time_slot:
        msg = f"Great. And what **time** works best for you on {appointment_date}? Our booking hours are **8:00 AM to 5:00 PM** (e.g., **10:00 AM**, **2:30 PM**)."
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    # ── Business Hours Validation ─────────────────────────────────────────────
    if not is_within_business_hours(time_slot):
        current_booking.pop("time_slot", None)
        msg = (
            f"Sorry, **{time_slot}** is outside our working hours. "
            "We accept appointments between **8:00 AM and 5:00 PM** only. "
            "What time within those hours works best for you?"
        )
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    # ── Admin Calendar Conflict Check ─────────────────────────────────────────
    admin_conflict_checked = current_booking.get("admin_conflict_checked")
    if not admin_conflict_checked:
        current_booking["admin_conflict_checked"] = True
        if check_admin_conflict(appointment_date, time_slot):
            available = get_available_slots(appointment_date)
            current_booking.pop("time_slot", None)
            current_booking.pop("admin_conflict_checked", None)
            if available:
                slots_str = ", ".join(f"**{s}**" for s in available)
                msg = (
                    f"Sorry, **{time_slot}** on {appointment_date} is already booked. "
                    f"Here are the available time slots for that day: {slots_str}. "
                    "Which one works best for you?"
                )
            else:
                msg = (
                    f"Sorry, **{time_slot}** on {appointment_date} is already booked, "
                    "and unfortunately there are no other slots available that day. "
                    "Would you like to try a different date?"
                )
            return {
                "current_booking": current_booking,
                "messages": [AIMessage(content=msg)],
                "final_response": msg,
            }

    # ── Final Confirmation ────────────────────────────────────────────────────
    email_id = current_booking.get("email_id")
    if not email_id:
        msg = "Almost done! Lastly, please provide your **email address** so I can send you the confirmation details."
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    confirmed = current_booking.get("confirmed")
    if not confirmed:
        # Check if the user just said "yes" in the latest message
        if user_input_lower in [
            "yes",
            "confirm",
            "ok",
            "sure",
            "sounds good",
            "perfect",
        ]:
            current_booking["confirmed"] = True
        else:
            specialty = state.get("specialty_needed", "N/A")
            reason = state.get("symptoms", "Not specified")
            msg = f"""Please confirm your booking details:
- **Patient Name**: {patient_name}
- **Specialty**: {specialty}
- **Reason**: {reason}
- **Doctor**: {clinic.get("name")}
- **Date**: {appointment_date}
- **Time**: {time_slot}
- **Email**: {email_id}

If everything looks correct, please reply **"Yes"** to confirm."""
            return {
                "current_booking": current_booking,
                "messages": [AIMessage(content=msg)],
                "final_response": msg,
            }

    # All fields present and confirmed -> Complete Booking
    import random

    booking_id = f"APT-{random.randint(10000, 99999)}"

    return {
        "current_booking": current_booking,
        "booking_id": booking_id,
        "booking_confirmed": True,
    }


# ---------------------------------------------------------------------------
# CONFIRMATION AGENT
# ---------------------------------------------------------------------------


async def confirmation_agent(state: AgentState) -> dict:
    """
    Saves booking to Supabase, attempts to send email via MCP, and returns confirmation.
    """
    clinic = state.get("selected_clinic") or {}
    booking = state.get("current_booking") or {}
    bid = state.get("booking_id") or "APT-PENDING"

    # 1. Save to Supabase
    specialty = state.get("specialty_needed", "N/A")
    reason = state.get("symptoms", "Not specified")

    booking_data = {
        "booking_id": bid,
        "user_id": state.get("user_id"),
        "clinic_name": clinic.get("name"),
        "clinic_address": clinic.get("address"),
        "patient_name": booking.get("patient_name"),
        "appointment_date": booking.get("appointment_date"),
        "email_id": booking.get("email_id"),
        "time_slot": booking.get("time_slot"),
        "specialty": specialty,
        "reason": reason,
        "status": "confirmed",
    }

    db_result = create_booking(booking_data)
    if db_result:
        db_status = "✅ Appointment saved to database."
    else:
        db_status = "⚠️ Note: There was an issue saving to the database. Please contact support with your booking ID."

    email_status = "Confirmation email will be sent shortly."
    try:
        import os
        import base64
        from email.mime.text import MIMEText
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        # Load credentials — prefer env vars (for Render), fallback to local files
        token_json_str = os.environ.get("GOOGLE_TOKEN_JSON")
        creds_json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")

        if token_json_str:
            token_data = json.loads(token_json_str)
        elif os.path.exists("token.json"):
            with open("token.json") as f:
                token_data = json.load(f)
        else:
            token_data = None

        if creds_json_str:
            creds_info = json.loads(creds_json_str)
        elif os.path.exists("credentials.json"):
            with open("credentials.json") as f:
                creds_info = json.load(f)
        else:
            creds_info = None

        if token_data and creds_info:
            client_info = creds_info.get("installed") or creds_info.get("web") or {}
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
                client_id=client_info.get("client_id") or token_data.get("client_id"),
                client_secret=client_info.get("client_secret")
                or token_data.get("client_secret"),
                scopes=token_data.get("scopes", ["https://mail.google.com/"]),
            )

            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

            service = build("gmail", "v1", credentials=creds)

            # Build the email
            recipient = booking.get("email_id")
            patient = booking.get("patient_name")
            doctor = clinic.get("name")
            address = clinic.get("address", "")
            appt_date = booking.get("appointment_date")
            appt_time = booking.get("time_slot")

            plain_body = f"""Dear {patient},

This is a confirmation of your appointment with {doctor} at the clinic. The appointment details are as follows:

Date: {appt_date}
Time: {appt_time}
Location: {address}

Please arrive 15 minutes prior to your scheduled time and bring any necessary documents or information. If you need to reschedule or have any questions, please do not hesitate to contact us.

We look forward to seeing you at the clinic.

Best regards,
{doctor} Clinic"""

            msg = MIMEText(plain_body, "plain")
            msg["Subject"] = f"Appointment Confirmed – {doctor}"
            msg["From"] = "me"
            msg["To"] = recipient

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            email_status = f"📧 Confirmation email sent to {recipient}!"
        else:
            pass
    except Exception:
        pass

    # ── Database Confirmation ────────────────────────────────────────────────
    calendar_status = "📅 Appointment secured in our system.\n"

    confirmation_msg = f"""
---BOOKING_CONFIRMED---
ID: {bid}
CLINIC: {clinic.get("name")}
ADDRESS: {clinic.get("address")}
PATIENT: {booking.get("patient_name")}
SPECIALTY: {specialty}
REASON: {reason}
DATE: {booking.get("appointment_date")}
TIME: {booking.get("time_slot")}
---END---

🎉 Your appointment has been successfully scheduled!
{db_status}
{email_status}
{calendar_status}"""
    return {
        "messages": [AIMessage(content=confirmation_msg)],
        "final_response": confirmation_msg,
    }


# ---------------------------------------------------------------------------
# GENERAL QA AGENT
# ---------------------------------------------------------------------------

GENERAL_QA_PROMPT = """You are a concise, helpful medical assistant for DocMatch AI.
Answer the user's question clearly and directly using the search results provided.

CRITICAL RULES:
- NEVER guess or say "likely" if you have search results. Use the facts.
- If the user is asking "where" or for "address", provide the specific location from the search results.
- LOCATION AWARENESS: If the user's current city is provided in the context, and the doctor/clinic you found is in a DIFFERENT city, you MUST inform the user and offer to help them find a different specialist closer to them.
- Example: "Dr. Smith is in Kolkata. Since you are in Balurghat, would you like me to find a cardiologist closer to you?"
- NEVER correct the user's grammar.
- Be short and to the point.

CONTEXT:
- User Current City: {city}
- Needed Specialty: {specialty}
"""


async def general_qa_agent(state: AgentState) -> dict:
    """
    Handles general questions using Tavily for live web search.
    Generates a optimized search query based on conversation history.
    """
    messages = state.get("messages", [])
    city = state.get("city") or "Unknown"
    specialty = state.get("specialty_needed") or "General Physician"

    # 1. Generate an optimized search query using LLM
    llm = _get_llm(temperature=0)
    query_gen_prompt = "Based on the following conversation, generate a short, effective Google search query to answer the user's latest question. Respond with ONLY the query text."

    recent_messages = messages[-4:] if len(messages) > 4 else messages
    query_resp = await llm.ainvoke(
        [SystemMessage(content=query_gen_prompt)] + recent_messages
    )
    search_query = query_resp.content.strip().replace('"', "")

    # 2. Execute Tavily search
    search_context = ""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        results = client.search(query=search_query, search_depth="advanced").get(
            "results", []
        )
        if results:
            snippets = [f"- {r.get('title')}: {r.get('content')}" for r in results[:5]]
            search_context = "Web search results:\n" + "\n".join(snippets)
    except Exception:
        pass

    # 3. Generate final answer
    prompt_messages = [
        SystemMessage(content=GENERAL_QA_PROMPT.format(city=city, specialty=specialty))
    ]
    prompt_messages.extend(recent_messages)

    if search_context:
        prompt_messages.append(
            HumanMessage(
                content=f"{search_context}\n\nAnswer the user's latest question using these facts."
            )
        )

    response = await llm.ainvoke(prompt_messages)

    return {
        "messages": [AIMessage(content=response.content)],
        "final_response": response.content,
    }
