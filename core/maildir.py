#!/usr/bin/env python3
"""
VSM Maildir — Filesystem-native email sync daemon.

Polls agentmail API and syncs emails to disk as plain text files.
NO LLM calls — pure Python sync.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests

VSM_ROOT = Path(__file__).parent.parent
CONFIG_FILE = VSM_ROOT / ".env"
STATE_DIR = VSM_ROOT / "state"
INBOX_FILE = STATE_DIR / "inbox_id"
SYNCED_FILE = STATE_DIR / "synced_threads.json"
INBOX_DIR = VSM_ROOT / "inbox"
OUTBOX_DIR = VSM_ROOT / "outbox"
SENT_DIR = VSM_ROOT / "sent"
BASE_URL = "https://api.agentmail.to/v0"


def load_config():
    """Load secrets from .env file."""
    config = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    config["AGENTMAIL_API_KEY"] = os.environ.get("AGENTMAIL_API_KEY", config.get("AGENTMAIL_API_KEY", ""))
    config["OWNER_EMAIL"] = os.environ.get("VSM_OWNER_EMAIL", config.get("OWNER_EMAIL", ""))
    return config


def get_headers():
    config = load_config()
    return {
        "Authorization": f"Bearer {config['AGENTMAIL_API_KEY']}",
        "Content-Type": "application/json",
    }


def get_inbox_id():
    if INBOX_FILE.exists():
        return INBOX_FILE.read_text().strip()
    raise FileNotFoundError("No inbox_id configured")


def load_synced():
    """Load dict of synced thread_id -> last_message_id."""
    if SYNCED_FILE.exists():
        data = json.loads(SYNCED_FILE.read_text())
        # Migrate from old format (list) to new format (dict)
        if isinstance(data.get("synced"), list):
            return {tid: "" for tid in data["synced"]}
        return data.get("synced", {})
    return {}


def save_synced(synced_dict):
    """Save synced thread_id -> last_message_id mapping."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(SYNCED_FILE, "w") as f:
        json.dump({"synced": synced_dict}, f)


def slugify(text):
    """Convert text to filesystem-safe slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text[:40]


def get_unread_threads(inbox_id):
    """Fetch unread threads from agentmail API."""
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox_id}/threads",
        headers=get_headers(),
        params={"labels": "unread", "limit": 20},
    )
    resp.raise_for_status()
    return resp.json().get("threads", [])


def get_thread_messages(inbox_id, thread_id):
    """Fetch full thread details from agentmail API."""
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox_id}/threads/{thread_id}",
        headers=get_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def write_email_file(thread_id, subject, sender, timestamp, body, message_id=""):
    """Write email as plain text file to inbox/."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    subject_slug = slugify(subject) if subject else "no_subject"
    filename = f"{thread_id}_{subject_slug}.txt"
    filepath = INBOX_DIR / filename

    content = f"""From: {sender}
Subject: {subject}
Date: {timestamp}
Thread-ID: {thread_id}
Message-ID: {message_id}
Status: unread
---
{body}
"""

    filepath.write_text(content)
    return filepath


def sync_inbox():
    """Sync unread emails from API to inbox/ directory."""
    inbox_id = get_inbox_id()
    synced = load_synced()

    threads = get_unread_threads(inbox_id)
    new_count = 0

    for thread_summary in threads:
        thread_id = thread_summary["thread_id"]

        thread = get_thread_messages(inbox_id, thread_id)
        messages = thread.get("messages", [])
        if not messages:
            continue

        # Get last inbound message (from someone other than our inbox)
        inbox_addr = inbox_id.split("@")[0] if "@" in inbox_id else inbox_id
        inbound_msgs = [m for m in messages if inbox_addr not in m.get("from", "")]
        if not inbound_msgs:
            continue

        last_msg = inbound_msgs[-1]
        last_msg_id = last_msg.get("message_id", "")

        # Skip if we already synced this exact message
        if synced.get(thread_id) == last_msg_id:
            continue

        sender = last_msg.get("from", "unknown@example.com")
        subject = thread.get("subject", "(no subject)")
        timestamp = last_msg.get("timestamp", datetime.now().isoformat())
        body = last_msg.get("text", "")

        filepath = write_email_file(thread_id, subject, sender, timestamp, body, last_msg_id)
        synced[thread_id] = last_msg_id
        new_count += 1
        print(f"[maildir] Synced: {filepath.name}")

    save_synced(synced)

    if new_count == 0:
        print("[maildir] No new emails")
    else:
        print(f"[maildir] Synced {new_count} new email(s)")


def get_last_message_id(inbox_id, thread_id):
    """Get the last message ID in a thread for replying."""
    try:
        thread = get_thread_messages(inbox_id, thread_id)
        messages = thread.get("messages", [])
        if messages:
            return messages[-1].get("message_id")
    except Exception:
        pass
    return None


def send_reply(inbox_id, thread_id, to_email, subject, body):
    """Send reply via agentmail API. Uses reply endpoint if thread exists."""
    headers = get_headers()

    # Try to reply to existing thread
    message_id = get_last_message_id(inbox_id, thread_id)
    if message_id:
        resp = requests.post(
            f"{BASE_URL}/inboxes/{inbox_id}/messages/{message_id}/reply",
            headers=headers,
            json={
                "to": to_email,
                "text": body,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # Fallback: send as new message
    resp = requests.post(
        f"{BASE_URL}/inboxes/{inbox_id}/messages/send",
        headers=headers,
        json={
            "to": to_email,
            "subject": f"Re: {subject}",
            "text": body,
        },
    )
    resp.raise_for_status()
    return resp.json()


def mark_thread_read(inbox_id, thread_id):
    """Mark all messages in a thread as read by removing 'unread' label."""
    headers = get_headers()
    try:
        thread = get_thread_messages(inbox_id, thread_id)
        for msg in thread.get("messages", []):
            msg_id = msg.get("message_id")
            if msg_id:
                resp = requests.patch(
                    f"{BASE_URL}/inboxes/{inbox_id}/messages/{msg_id}",
                    headers=headers,
                    json={"remove_labels": ["unread"]},
                )
                resp.raise_for_status()
        print(f"[maildir] Marked thread {thread_id[:8]}... as read")
    except Exception as e:
        print(f"[maildir] Error marking thread read: {e}")


def sync_outbox():
    """Send emails from outbox/ directory and move to sent/."""
    if not OUTBOX_DIR.exists():
        return

    inbox_id = get_inbox_id()
    sent_count = 0

    SENT_DIR.mkdir(parents=True, exist_ok=True)

    for outfile in OUTBOX_DIR.glob("*.txt"):
        try:
            content = outfile.read_text()
            lines = content.split("\n")

            # Parse headers
            thread_id = None
            to_email = None
            subject = None
            body_lines = []
            in_body = False

            for line in lines:
                if line.strip() == "---":
                    in_body = True
                    continue

                if in_body:
                    body_lines.append(line)
                elif line.startswith("Thread-ID:"):
                    thread_id = line.split(":", 1)[1].strip()
                elif line.startswith("To:"):
                    to_email = line.split(":", 1)[1].strip()
                elif line.startswith("Subject:"):
                    subject = line.split(":", 1)[1].strip()
                    if subject.startswith("Re: "):
                        subject = subject[4:]  # Strip Re: prefix

            body = "\n".join(body_lines).strip()

            if not thread_id or not to_email:
                print(f"[maildir] Skipping malformed outbox file: {outfile.name}")
                continue

            # Send via API
            send_reply(inbox_id, thread_id, to_email, subject or "(no subject)", body)

            # Move to sent/
            sent_file = SENT_DIR / outfile.name
            outfile.rename(sent_file)

            sent_count += 1
            print(f"[maildir] Sent: {outfile.name}")

        except Exception as e:
            print(f"[maildir] Error sending {outfile.name}: {e}")
            continue

    if sent_count > 0:
        print(f"[maildir] Sent {sent_count} email(s)")


def main():
    """Main entry point for maildir sync daemon."""
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "sync":
            sync_inbox()
            sync_outbox()
        elif cmd == "sync_inbox":
            sync_inbox()
        elif cmd == "sync_outbox":
            sync_outbox()
        else:
            print("Usage: maildir.py [sync|sync_inbox|sync_outbox]")
            sys.exit(1)
    else:
        print("Usage: maildir.py [sync|sync_inbox|sync_outbox]")
        sys.exit(1)


if __name__ == "__main__":
    main()
