#!/usr/bin/env python3
"""
VSM Communication Module — agentmail.to integration
Provides the system's ability to reach out when it needs human intervention.
"""

import json
import requests
from pathlib import Path

API_KEY = "am_f645fe5d49c4ceb09695e7586e1456173d22205cd3ea2c0f70768da2ce1e69e1"
BASE_URL = "https://api.agentmail.to/v0"
OWNER_EMAIL = "michael.darmousseh@gmail.com"
STATE_DIR = Path(__file__).parent.parent / "state"
INBOX_FILE = STATE_DIR / "inbox_id"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def get_or_create_inbox():
    """Get cached inbox ID or create a new one."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if INBOX_FILE.exists():
        return INBOX_FILE.read_text().strip()

    resp = requests.post(
        f"{BASE_URL}/inboxes",
        headers=HEADERS,
        json={"display_name": "VSM Criticality Engine"},
    )
    resp.raise_for_status()
    inbox_id = resp.json()["inbox_id"]
    INBOX_FILE.write_text(inbox_id)
    return inbox_id


def send_email(subject, body):
    """Send an email to the owner."""
    inbox_id = get_or_create_inbox()
    resp = requests.post(
        f"{BASE_URL}/inboxes/{inbox_id}/messages/send",
        headers=HEADERS,
        json={
            "to": OWNER_EMAIL,
            "subject": f"[VSM] {subject}",
            "text": body,
        },
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        result = send_email(sys.argv[1], sys.argv[2])
        print(f"Sent: {result}")
    else:
        print("Usage: comm.py <subject> <body>")
