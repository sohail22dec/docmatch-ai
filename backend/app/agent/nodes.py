import json
from datetime import datetime, timedelta
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langgraph.graph import END
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

2. "booking_request" - User wants to book an appointment with a specific doctor or clinic
   Examples: "I want to book an appointment with Dr. Akash", "book a visit to dental care", "I pick the first one"

3. "general_qa" - User is asking a general question or anything else
   Examples: "what is Dr. X's phone number?", "what are symptoms of diabetes?", "tell me more about clinic 3"

Respond with ONLY one word: clinic_search, booking_request, OR general_qa
"""


async def orchestrator_node(state: AgentState) -> dict:
    print(f"[DEBUG] Entering orchestrator. Specialty: {state.get('specialty_needed')}")
    """
    Central decision-maker. Uses state-based routing as defined in the plan.
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
    # This prevents infinite loops when an agent (like symptom_agent) asks a question.
    if final_response:
        return {"next": END}

    # NEW: PRIORITIZE BOOKING FLOW
    # If a clinic is selected, we MUST stay in booking mode.
    if selected_clinic and not booking_confirmed:
        print(f"[DEBUG] Booking mode locked for clinic: {selected_clinic.get('name')}")
        return {"next": "booking_agent"}

    # 1. Fresh message - If no specialty yet, check if it's a general question
    if specialty is None:
        messages = state.get("messages", [])
        latest_user_msg = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                latest_user_msg = msg.content
                break
        if latest_user_msg:
            llm = _get_llm()
            intent_resp = await llm.ainvoke(
                [
                    SystemMessage(content=INTENT_PROMPT),
                    HumanMessage(content=latest_user_msg),
                ]
            )
            intent = intent_resp.content.strip().lower()
            print(f"[DEBUG] Intent: {intent}")
            if "general_qa" in intent:
                print("[DEBUG] Routing to general_qa_agent")
                return {"next": "general_qa_agent"}
            if "booking_request" in intent:
                print("[DEBUG] Routing to booking_agent")
                return {"next": "booking_agent"}

        print("[DEBUG] Routing to symptom_agent")
        return {"next": "symptom_agent"}

    # 2. latitude and city are both None → location_agent
    if latitude is None and not city:
        print("[DEBUG] Routing to location_agent")
        return {"next": "location_agent"}

    # 3. clinics_found is None and search_attempted is False → search_agent
    if clinics is None and not searched:
        print("[DEBUG] Routing to search_agent")
        return {"next": "search_agent"}

    # 4. clinics_found is set and selected_clinic is None → formatter_agent
    if clinics is not None and selected_clinic is None:
        print("[DEBUG] Routing to formatter_agent")
        return {"next": "formatter_agent"}

    # 5. booking_confirmed is True → confirmation_agent
    if booking_confirmed:
        print("[DEBUG] Routing to confirmation_agent")
        return {"next": "confirmation_agent"}

    print("[DEBUG] Routing to END (default)")
    return {"next": END}


# ---------------------------------------------------------------------------
# SYMPTOM AGENT
# ---------------------------------------------------------------------------

SYMPTOM_PROMPT = """You are a medical triage specialist. 
Your job is to read the user's conversation and determine if you have enough information to assign a medical specialty.

Rules:
- Respond with ONLY a JSON object.
- If the user explicitly requests a specific doctor or specialty (e.g. "find a gynecologist", "I need a dentist", "where is a cardiologist"), DO NOT ask for symptoms. Immediately output: {"status": "diagnosed", "specialty": "Requested Specialty", "symptoms_summary": "User directly requested this specialty"}.
- If the latest message is "📍 Here is my current location.":
    - If symptoms were ALREADY discussed: Ignore the location message and continue the triage (re-ask your last question if needed).
    - If NO symptoms have been mentioned yet: Ask "I've received your location! What symptoms are you experiencing today so I can help you find the right doctor?"
- If symptoms are vague (e.g. "headache", "stomach hurts"), ask a clarifying question.
  Format: {"status": "clarifying", "message": "When did the headache start and how severe is it?"}
- If symptoms are clear, assign a specialist and extract the city if mentioned.
  Format: {"status": "diagnosed", "specialty": "Neurologist", "city": "Mumbai", "symptoms_summary": "severe headache for 3 days"}
- If no city is mentioned, leave "city" as null.
- Choose from common specialties: Dermatologist, Cardiologist, Neurologist, Orthopedist, Pediatrician, Psychiatrist, Gastroenterologist, ENT Specialist, Ophthalmologist, General Physician, Dentist, Gynecologist, Urologist, Pulmonologist.
- Do NOT include any other text — only the JSON object.
"""


async def symptom_agent(state: AgentState) -> dict:
    print("[DEBUG] Entering symptom_agent")
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
            specialty = data.get("specialty", "General Physician")
            city = data.get("city")
            symptoms_summary = data.get("symptoms_summary", "General symptoms")

            if "directly requested" in symptoms_summary.lower():
                diag_msg = f"Got it! I can help you find a **{specialty}**."
            else:
                diag_msg = (
                    f"Based on your symptoms, I recommend seeing a **{specialty}**."
                )

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
        print(f"[symptom_agent] Error: {e}")
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
            f"To find the closest clinics, I am requesting your location now. Please click **Allow** on the popup that just appeared. (If you prefer not to share your GPS, you can deny the request and simply type your city name instead)."
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
1. Identify "patient_name", "appointment_date", "time_slot", and "email_id" from the User Message.
2. Use the "Last Question Asked" as context. For example, if asked for a time, "10am" refers to "time_slot".
3. For "appointment_date", if the user specifies a date, ensure it is strictly between Today and the 14-Day Window Ends. If it is beyond 14 days or in the past, output "appointment_date" as "INVALID_DATE".
4. For "time_slot", automatically format it to a 1-hour slot (e.g., if user says "10am", output "10:00 AM - 11:00 AM").
5. Respond with ONLY a JSON object. No conversational text.
6. If no new info is found, return {{}}.
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
            # Could not identify which clinic. Ask user to be more specific or click a button.
            msg = "I'm not sure which clinic you'd like to book. Could you please provide the full name or click the **'Book'** button next to your choice?"
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
        if any(
            w in user_input_lower for w in ["tomorrow", "friday", "monday", "today"]
        ):
            current_booking["appointment_date"] = user_input.capitalize()

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
        # Clean up markdown code blocks if present
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.split("```")[0]

        new_data = json.loads(content.strip())
        print(f"[booking_agent] Extracted: {new_data}")
        current_booking.update(new_data)
    except Exception as e:
        print(
            f"[booking_agent] Data extraction error: {e} | Content: {extract_resp.content}"
        )

    # 3. Find first missing field
    # SAFETY: If we STILL don't have a clinic, we can't book.
    if not clinic:
        msg = "I'm ready to help you book an appointment! Could you please tell me **which clinic** or **which doctor** you'd like to visit from the list above?"
        return {"messages": [AIMessage(content=msg)], "final_response": msg}

    # IMPORTANT: Explicitly check for truthy values to avoid empty string loops
    patient_name = current_booking.get("patient_name")
    if not patient_name or len(str(patient_name).strip()) < 2:
        clinic_name = clinic.get("name", "this clinic")
        msg = f"Great choice! Booking with **{clinic_name}**.\nI'll need a few details. What's your **full name**?"
        return {
            "selected_clinic": clinic,
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    appointment_date = current_booking.get("appointment_date")
    if appointment_date == "INVALID_DATE":
        current_booking.pop("appointment_date")  # Remove it so they are asked again
        msg = f"I'm sorry, {patient_name}, but you can only book appointments up to 14 days in advance. What **valid date** works for you?"
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    if not appointment_date:
        msg = f"Nice to meet you, {patient_name}!\nWhat **date** would you like to book? (e.g., **Tomorrow**, **Next Friday**). You can book up to 14 days in advance."
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    time_slot = current_booking.get("time_slot")
    if not time_slot:
        msg = f"And what **time** works best for you on {appointment_date}? (e.g., **10 AM**, **2:30 PM**). Appointments are 1 hour long."
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    email_id = current_booking.get("email_id")
    if not email_id:
        msg = f"Got it. A 1-hour slot at {time_slot}. Lastly, what is your **email address** so we can send you the confirmation?"
        return {
            "current_booking": current_booking,
            "messages": [AIMessage(content=msg)],
            "final_response": msg,
        }

    # Ask for final confirmation
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

    from app.models.crud import create_booking

    create_booking(booking_data)

    # 2. Attempt to send Email via Gmail API (direct, no uvx/MCP needed)
    email_status = "Confirmation email will be sent shortly."
    try:
        import os
        import json
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
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
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=client_info.get("client_id") or token_data.get("client_id"),
                client_secret=client_info.get("client_secret") or token_data.get("client_secret"),
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

            html_body = f"""
<html><body style="font-family:Georgia,serif;max-width:560px;margin:auto;padding:32px;background:#f9fafb;color:#374151;">
  <div style="background:#fff;border-radius:12px;padding:36px 40px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

    <p style="margin:0 0 24px;font-size:15px;">Dear <strong>{patient}</strong>,</p>

    <p style="margin:0 0 16px;font-size:15px;line-height:1.7;">
      This is a confirmation of your appointment with <strong>{doctor}</strong> at the clinic.
      The appointment details are as follows:
    </p>

    <table style="width:100%;border-collapse:collapse;font-size:15px;margin:0 0 20px;">
      <tr>
        <td style="padding:8px 0;color:#6b7280;width:60px;">Date:</td>
        <td style="padding:8px 0;color:#111827;font-weight:600;">{appt_date}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;">Time:</td>
        <td style="padding:8px 0;color:#111827;font-weight:600;">{appt_time}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;vertical-align:top;">Location:</td>
        <td style="padding:8px 0;color:#111827;">{address}</td>
      </tr>
    </table>

    <p style="margin:0 0 16px;font-size:15px;line-height:1.7;">
      Please arrive <strong>15 minutes prior</strong> to your scheduled time and bring any necessary
      documents or information. If you need to reschedule or have any questions, please do not
      hesitate to contact us.
    </p>

    <p style="margin:0 0 32px;font-size:15px;line-height:1.7;">
      We look forward to seeing you at the clinic.
    </p>

    <p style="margin:0;font-size:15px;">Best regards,<br>
      <strong>{doctor} Clinic</strong>
    </p>

    <hr style="margin:28px 0;border:none;border-top:1px solid #e5e7eb;">
    <p style="margin:0;font-size:11px;color:#9ca3af;">This email was sent by DocMatch AI on behalf of {doctor} Clinic.</p>
  </div>
</body></html>"""

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Appointment Confirmed – {doctor}"
            msg["From"] = "me"
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            email_status = f"📧 Confirmation email sent to {recipient}!"
            print(f"[confirmation_agent] Email sent successfully to {recipient}")
        else:
            print("[confirmation_agent] No credentials found, skipping email.")
    except Exception as e:
        print(f"[confirmation_agent] Email Error: {e}")

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

🎉 Your appointment has been successfully scheduled and saved!
{email_status}
"""
    return {
        "messages": [AIMessage(content=confirmation_msg)],
        "final_response": confirmation_msg,
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
