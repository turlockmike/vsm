#!/usr/bin/env python3
"""
VSM Communication Module — agentmail.to integration
Provides the system's ability to reach out when it needs human intervention.
"""

import json
import os
import requests
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / ".env"
STATE_DIR = Path(__file__).parent.parent / "state"
INBOX_FILE = STATE_DIR / "inbox_id"
BASE_URL = "https://api.agentmail.to/v0"


def load_config():
    """Load secrets from .env file (gitignored)."""
    config = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()
    # Environment variables override file
    config["AGENTMAIL_API_KEY"] = os.environ.get("AGENTMAIL_API_KEY", config.get("AGENTMAIL_API_KEY", ""))
    config["OWNER_EMAIL"] = os.environ.get("VSM_OWNER_EMAIL", config.get("OWNER_EMAIL", ""))
    return config


def get_headers():
    config = load_config()
    return {
        "Authorization": f"Bearer {config['AGENTMAIL_API_KEY']}",
        "Content-Type": "application/json",
    }


def get_or_create_inbox():
    """Get cached inbox ID or create a new one."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if INBOX_FILE.exists():
        return INBOX_FILE.read_text().strip()

    resp = requests.post(
        f"{BASE_URL}/inboxes",
        headers=get_headers(),
        json={"display_name": "VSM Criticality Engine"},
    )
    resp.raise_for_status()
    inbox_id = resp.json()["inbox_id"]
    INBOX_FILE.write_text(inbox_id)
    return inbox_id


def send_email(subject, body):
    """Send an email to the owner."""
    config = load_config()
    inbox_id = get_or_create_inbox()
    resp = requests.post(
        f"{BASE_URL}/inboxes/{inbox_id}/messages/send",
        headers=get_headers(),
        json={
            "to": config["OWNER_EMAIL"],
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
