#!/usr/bin/env python3
"""
VSM Inbox Reader — agentmail.to integration
Provides the system's ability to read inbound emails from the owner.
"""

import json
import requests
from pathlib import Path
import sys

BASE_URL = "https://api.agentmail.to/v0"
STATE_DIR = Path(__file__).parent.parent.parent / "state"
INBOX_FILE = STATE_DIR / "inbox_id"
CONFIG_FILE = Path(__file__).parent.parent.parent / ".env"


def _load_api_key():
    import os
    key = os.environ.get("AGENTMAIL_API_KEY", "")
    if not key and CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if line.startswith("AGENTMAIL_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def _get_headers():
    return {
        "Authorization": f"Bearer {_load_api_key()}",
        "Content-Type": "application/json",
    }


def get_inbox_id():
    """Read the inbox ID from state file."""
    if not INBOX_FILE.exists():
        raise FileNotFoundError(f"Inbox ID file not found: {INBOX_FILE}")
    return INBOX_FILE.read_text().strip()


def list_threads(inbox_id, labels=None, limit=50):
    """List threads in the inbox."""
    params = {"limit": limit}
    if labels:
        params["labels"] = labels

    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox_id}/threads",
        headers=_get_headers(),
        params=params,
    )
    resp.raise_for_status()
    return resp.json()


def get_thread(inbox_id, thread_id):
    """Get a specific thread with all its messages."""
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox_id}/threads/{thread_id}",
        headers=_get_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def check_inbox(unreplied_only=True):
    """
    Check inbox for messages.

    Returns structured data about messages:
    {
        "thread_count": int,
        "threads": [
            {
                "thread_id": str,
                "subject": str,
                "preview": str,
                "message_count": int,
                "timestamp": str,
                "labels": list,
                "messages": [
                    {
                        "from": str,
                        "to": str,
                        "subject": str,
                        "text": str,
                        "html": str,
                        "timestamp": str
                    }
                ]
            }
        ]
    }
    """
    inbox_id = get_inbox_id()

    # List threads, optionally filtering to unreplied
    labels = ["unread"] if unreplied_only else None
    threads_data = list_threads(inbox_id, labels=labels)

    result = {
        "inbox_id": inbox_id,
        "thread_count": threads_data.get("count", 0),
        "threads": []
    }

    # Fetch full thread details for each thread
    for thread_summary in threads_data.get("threads", []):
        thread_id = thread_summary["thread_id"]
        thread_detail = get_thread(inbox_id, thread_id)

        thread_info = {
            "thread_id": thread_detail["thread_id"],
            "subject": thread_detail.get("subject", ""),
            "preview": thread_detail.get("preview", ""),
            "message_count": thread_detail.get("message_count", 0),
            "timestamp": thread_detail.get("received_timestamp") or thread_detail.get("sent_timestamp", ""),
            "labels": thread_detail.get("labels", []),
            "messages": []
        }

        # Extract message details
        for msg in thread_detail.get("messages", []):
            message_info = {
                "from": msg.get("from", ""),
                "to": msg.get("to", ""),
                "subject": msg.get("subject", ""),
                "text": msg.get("text", ""),
                "html": msg.get("html", ""),
                "timestamp": msg.get("timestamp", "")
            }
            thread_info["messages"].append(message_info)

        result["threads"].append(thread_info)

    return result


if __name__ == "__main__":
    # Parse command line args
    unreplied_only = True
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        unreplied_only = False

    try:
        inbox_data = check_inbox(unreplied_only=unreplied_only)
        print(json.dumps(inbox_data, indent=2))
    except Exception as e:
        error_result = {
            "error": str(e),
            "type": type(e).__name__
        }
        print(json.dumps(error_result, indent=2), file=sys.stderr)
        sys.exit(1)
