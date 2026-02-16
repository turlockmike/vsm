#!/usr/bin/env python3
"""
Send messages to owner — writes to outbox/ files.
Sync daemons handle actual delivery.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
OUTBOX = VSM_ROOT / "state" / "outbox"


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


def send_message(text, channel=None, subject=None):
    """Queue a message for delivery. Auto-picks best channel if not specified."""
    config = load_config()
    OUTBOX.mkdir(parents=True, exist_ok=True)

    if channel is None:
        # Prefer telegram if configured, fall back to email
        channel = "telegram" if config.get("TELEGRAM_BOT_TOKEN") else "email"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    if channel == "telegram":
        msg = {
            "channel": "telegram",
            "chat_id": config.get("TELEGRAM_CHAT_ID", ""),
            "text": text,
            "sent": False,
        }
    else:
        msg = {
            "channel": "email",
            "to": config.get("OWNER_EMAIL", ""),
            "subject": subject or "[VSM] Notification",
            "text": text,
            "sent": False,
        }

    outfile = OUTBOX / f"notify_{ts}.json"
    outfile.write_text(json.dumps(msg, indent=2))
    return True


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        subject = sys.argv[1] if len(sys.argv) >= 3 else None
        body = sys.argv[-1]
        ok = send_message(body, subject=subject)
        print("Queued" if ok else "Failed")
