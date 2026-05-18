"""
Run this script ONCE to update token.json with Gmail + Google Calendar scopes.

Usage:
    python reauthorize_google.py

This will open your browser → click Allow → a new token.json will be saved.
After that, the backend can send emails AND read/write Google Calendar.
"""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: '{CREDENTIALS_FILE}' not found. Please ensure it exists in the backend directory.")
        return

    print("Opening browser for Google authorization...")
    print("Please log in and click 'Allow' to grant Gmail + Calendar permissions.\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Save the new token
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✅ Success! '{TOKEN_FILE}' has been updated with Gmail + Calendar scopes.")
    print("You can now restart the backend server.")


if __name__ == "__main__":
    main()
