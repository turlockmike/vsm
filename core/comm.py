#!/usr/bin/env python3
"""Send email via agentmail.to API."""

import sys
from pathlib import Path

import requests

VSM_ROOT = Path(__file__).parent.parent


def load_config():
    config = {}
    env_file = VSM_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config


def send_email(subject, body, to=None):
    config = load_config()
    api_key = config.get("AGENTMAIL_API_KEY", "")
    inbox = config.get("VSM_INBOX", "vsm-bot@agentmail.to")
    to = to or config.get("OWNER_EMAIL", "")

    if not api_key or not to:
        print("Missing AGENTMAIL_API_KEY or OWNER_EMAIL in .env")
        return False

    resp = requests.post(
        f"https://api.agentmail.to/v0/inboxes/{inbox}/messages/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"to": to, "subject": subject, "text": body},
    )
    return resp.status_code == 200


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ok = send_email(sys.argv[1], sys.argv[2])
        print("Sent" if ok else "Failed")
