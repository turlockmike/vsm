#!/usr/bin/env python3
"""
Telegram sync daemon — plumbing only.
Long-polls for messages → writes to inbox/.
Reads outbox/ → sends via Telegram API.
No Claude, no intelligence. Just moves data.

Run as a background daemon (not cron — needs persistent polling).
"""

import json
import time
import sys
from datetime import datetime
from pathlib import Path

import requests

VSM_ROOT = Path(__file__).parent.parent
INBOX = VSM_ROOT / "state" / "inbox"
OUTBOX = VSM_ROOT / "state" / "outbox"
OFFSET_FILE = VSM_ROOT / "state" / "telegram_offset"


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


def load_offset():
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except (ValueError, IOError):
            return 0
    return 0


def save_offset(offset):
    OFFSET_FILE.write_text(str(offset))


def _save_chat_id(chat_id):
    """Auto-save discovered chat_id to .env for future use."""
    env_file = VSM_ROOT / ".env"
    content = env_file.read_text()
    if "TELEGRAM_CHAT_ID" not in content:
        with open(env_file, "a") as f:
            f.write(f"\nTELEGRAM_CHAT_ID={chat_id}\n")


def pull_messages(config):
    """Long-poll Telegram → write incoming messages to inbox/."""
    token = config.get("TELEGRAM_BOT_TOKEN", "")
    owner_id = config.get("TELEGRAM_CHAT_ID", "")
    if not token:
        return

    api = f"https://api.telegram.org/bot{token}"
    offset = load_offset()

    try:
        resp = requests.get(
            f"{api}/getUpdates",
            params={"offset": offset, "timeout": 30, "limit": 50},
            timeout=35,
        )
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception as e:
        print(f"[sync-tg] Poll error: {e}")
        return

    for update in updates:
        offset = update["update_id"] + 1
        msg = update.get("message")
        if not msg or not msg.get("text"):
            continue

        chat_id = str(msg["chat"]["id"])

        # If no owner_id configured, accept first message and save chat_id
        if not owner_id:
            owner_id = chat_id
            _save_chat_id(chat_id)
            print(f"[sync-tg] Auto-discovered owner chat_id: {chat_id}")
        elif chat_id != str(owner_id):
            continue

        # Write to shared inbox
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        msg_id = msg.get("message_id", ts)
        inbox_file = INBOX / f"tg_{msg_id}.json"
        inbox_file.write_text(json.dumps({
            "message_id": msg_id,
            "from": msg["from"].get("first_name", "Owner"),
            "text": msg["text"],
            "timestamp": datetime.fromtimestamp(msg["date"]).isoformat(),
            "channel": "telegram",
            "chat_id": chat_id,
        }, indent=2))
        print(f"[sync-tg] Received: {msg['text'][:80]}")

    save_offset(offset)


def push_replies(config):
    """Send outbox/ files tagged as telegram."""
    token = config.get("TELEGRAM_BOT_TOKEN", "")
    owner_id = config.get("TELEGRAM_CHAT_ID", "")
    if not token:
        return

    api = f"https://api.telegram.org/bot{token}"

    for f in OUTBOX.glob("*.json"):
        try:
            msg = json.loads(f.read_text())
        except Exception:
            continue

        if msg.get("channel") != "telegram":
            continue
        if msg.get("sent"):
            continue

        try:
            resp = requests.post(
                f"{api}/sendMessage",
                json={
                    "chat_id": msg.get("chat_id", owner_id),
                    "text": msg["text"],
                },
                timeout=10,
            )
            resp.raise_for_status()

            msg["sent"] = True
            msg["sent_at"] = datetime.now().isoformat()
            f.write_text(json.dumps(msg, indent=2))
            print(f"[sync-tg] Sent: {msg['text'][:80]}")

        except Exception as e:
            print(f"[sync-tg] Send failed: {e}")


def main():
    INBOX.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)
    config = load_config()

    if not config.get("TELEGRAM_BOT_TOKEN"):
        print("[sync-tg] No TELEGRAM_BOT_TOKEN in .env, exiting")
        sys.exit(1)

    print("[sync-tg] Starting Telegram sync daemon...")
    while True:
        try:
            config = load_config()  # Re-read in case .env changes
            pull_messages(config)
            push_replies(config)
        except KeyboardInterrupt:
            print("\n[sync-tg] Stopped")
            break
        except Exception as e:
            print(f"[sync-tg] Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
