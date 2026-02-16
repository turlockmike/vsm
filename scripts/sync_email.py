#!/usr/bin/env python3
"""
Email sync daemon — plumbing only.
Pulls unread emails to inbox/, sends files from outbox/.
No Claude, no classification, no intelligence. Just moves data.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests

VSM_ROOT = Path(__file__).parent.parent
INBOX = VSM_ROOT / "state" / "inbox"
OUTBOX = VSM_ROOT / "state" / "outbox"
SYNCED_FILE = VSM_ROOT / "state" / "synced_threads.json"
BASE_URL = "https://api.agentmail.to/v0"


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


def load_synced():
    if SYNCED_FILE.exists():
        return set(json.loads(SYNCED_FILE.read_text()).get("synced", []))
    return set()


def save_synced(synced):
    SYNCED_FILE.write_text(json.dumps({"synced": list(synced)}))


def pull_emails(config):
    """Fetch unread emails → write to inbox/ as JSON files."""
    mailbox = config.get("VSM_INBOX", "vsm-bot@agentmail.to")
    headers = {
        "Authorization": f"Bearer {config['AGENTMAIL_API_KEY']}",
        "Content-Type": "application/json",
    }
    synced = load_synced()

    resp = requests.get(
        f"{BASE_URL}/inboxes/{mailbox}/threads",
        headers=headers,
        params={"labels": "unread", "limit": 10},
    )
    resp.raise_for_status()
    threads = resp.json().get("threads", [])

    new_count = 0
    for t in threads:
        tid = t["thread_id"]
        if tid in synced:
            continue

        detail = requests.get(
            f"{BASE_URL}/inboxes/{mailbox}/threads/{tid}",
            headers=headers,
        ).json()

        messages = detail.get("messages", [])
        if not messages:
            synced.add(tid)
            continue

        last_msg = messages[-1]
        sender = last_msg.get("from", "")
        owner = config.get("OWNER_EMAIL", "")

        # Only sync owner emails
        if owner not in sender:
            synced.add(tid)
            continue

        inbox_file = INBOX / f"{tid}.json"
        inbox_file.write_text(json.dumps({
            "thread_id": tid,
            "subject": detail.get("subject", "(no subject)"),
            "from": sender,
            "text": last_msg.get("text", ""),
            "timestamp": last_msg.get("created_at", datetime.now().isoformat()),
            "channel": "email",
            "message_count": len(messages),
        }, indent=2))
        new_count += 1

        synced.add(tid)

    save_synced(synced)
    if new_count:
        print(f"[sync-email] Pulled {new_count} new emails")


def push_replies(config):
    """Send files from outbox/ that are email replies."""
    mailbox = config.get("VSM_INBOX", "vsm-bot@agentmail.to")
    headers = {
        "Authorization": f"Bearer {config['AGENTMAIL_API_KEY']}",
        "Content-Type": "application/json",
    }

    for f in OUTBOX.glob("*.json"):
        try:
            msg = json.loads(f.read_text())
        except Exception:
            continue

        if msg.get("channel") != "email":
            continue
        if msg.get("sent"):
            continue

        try:
            payload = {
                "to": msg["to"],
                "subject": msg.get("subject", ""),
                "text": msg["text"],
            }
            if msg.get("thread_id"):
                payload["thread_id"] = msg["thread_id"]

            resp = requests.post(
                f"{BASE_URL}/inboxes/{mailbox}/messages/send",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()

            # Mark as sent
            msg["sent"] = True
            msg["sent_at"] = datetime.now().isoformat()
            f.write_text(json.dumps(msg, indent=2))
            print(f"[sync-email] Sent: {msg.get('subject', '?')}")

        except Exception as e:
            print(f"[sync-email] Failed to send {f.name}: {e}")


def main():
    config = load_config()
    INBOX.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)

    pull_emails(config)
    push_replies(config)


if __name__ == "__main__":
    main()
