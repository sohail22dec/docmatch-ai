import base64
import json
import os
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


class EmailService:
    """
    Handles sending booking confirmation emails to patients using the Gmail API.
    """

    async def send_booking_confirmation(self, booking: dict) -> bool:
        # Resolve keys correctly (email_id holds email, booking_id holds APT-XXXXX)
        patient_email = booking.get("email_id")
        booking_id = booking.get("booking_id")
        clinic_name = booking.get("clinic_name")
        patient_name = booking.get("patient_name")
        appointment_date = booking.get("appointment_date")
        time_slot = booking.get("time_slot")

        print(
            f"[EMAIL SENT] Confirmation → {patient_email}\n"
            f"  Booking ID : {booking_id}\n"
            f"  Clinic     : {clinic_name}\n"
            f"  Patient    : {patient_name}\n"
            f"  Date       : {appointment_date}\n"
            f"  Time       : {time_slot}\n"
        )

        if not patient_email:
            print("EmailService Error: patient_email is empty.")
            return False

        # Load token file from backend root directory
        token_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "token.json"
        )
        if not os.path.exists(token_path):
            print(f"EmailService Error: token.json not found at {token_path}")
            return False

        try:
            creds = Credentials.from_authorized_user_file(
                token_path,
                ["https://mail.google.com/"]
            )
            
            # Refresh if credentials are expired
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                
                # Save the refreshed token back
                token_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                }
                with open(token_path, "w") as f:
                    json.dump(token_data, f, indent=2)

            service = build("gmail", "v1", credentials=creds)

            # Create message
            subject = f"Appointment Confirmation: {booking_id} at {clinic_name}"
            body_text = (
                f"Hello {patient_name},\n\n"
                f"Your appointment has been successfully confirmed!\n\n"
                f"Booking ID: {booking_id}\n"
                f"Clinic: {clinic_name}\n"
                f"Date: {appointment_date}\n"
                f"Time: {time_slot}\n\n"
                f"Thank you for choosing DocMatch AI!"
            )

            message = MIMEText(body_text)
            message["to"] = patient_email
            message["subject"] = subject

            # Encode message for Gmail API Send endpoint
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = {"raw": raw}

            service.users().messages().send(userId="me", body=send_message).execute()
            print(f"Gmail confirmation sent successfully to {patient_email}")
            return True
        except Exception as e:
            print(f"EmailService Exception while sending email: {e}")
            return False
