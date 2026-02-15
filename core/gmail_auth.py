#!/usr/bin/env python3
"""
Gmail OAuth 2.0 Authentication Module
Handles OAuth flow and provides authenticated Gmail API client.
"""

import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes - gmail.modify allows read, label, archive, and draft creation
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Path configuration
VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / 'state'
CREDENTIALS_FILE = STATE_DIR / 'gmail_credentials.json'
TOKEN_FILE = STATE_DIR / 'gmail_token.json'


def get_gmail_service():
    """
    Returns an authenticated Gmail API service.

    Raises:
        FileNotFoundError: If credentials file doesn't exist
        Exception: If authentication fails
    """
    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            creds.refresh(Request())
        else:
            # Run OAuth flow
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Gmail credentials file not found at {CREDENTIALS_FILE}\n\n"
                    "To set up Gmail access:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a new project or select existing\n"
                    "3. Enable Gmail API\n"
                    "4. Create OAuth 2.0 credentials (Desktop app)\n"
                    "5. Download credentials JSON and save to:\n"
                    f"   {CREDENTIALS_FILE}\n"
                    "6. Run: vsm email setup\n"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for next run
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def setup_oauth():
    """
    Run the OAuth setup flow interactively.
    This opens a browser window for the user to authenticate.
    """
    print("Starting Gmail OAuth setup...\n")

    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: Credentials file not found at {CREDENTIALS_FILE}")
        print("\nTo set up Gmail access:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download credentials JSON and save to:")
        print(f"   {CREDENTIALS_FILE}")
        print("\nThen run this setup again.")
        return False

    try:
        # Force new authentication
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()

        service = get_gmail_service()

        # Test the connection
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')

        print(f"\nSUCCESS! Authenticated as: {email}")
        print(f"Token saved to: {TOKEN_FILE}")
        print("\nYou can now use 'vsm email scan' and 'vsm email digest'")
        return True

    except Exception as e:
        print(f"\nERROR during OAuth setup: {e}")
        return False


if __name__ == '__main__':
    setup_oauth()
