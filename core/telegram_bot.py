#!/usr/bin/env python3
"""
VSM Telegram Bot — Direct chat with the owner.
Polls for messages via getUpdates, responds via Claude (haiku).
Runs every minute via cron, same pattern as email_responder.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import requests

VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / "state"
TG_STATE_FILE = STATE_DIR / "telegram_state.json"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
CLAUDE_BIN = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


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


def load_tg_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if TG_STATE_FILE.exists():
        return json.loads(TG_STATE_FILE.read_text())
    return {"last_update_id": 0, "owner_chat_id": None}


def save_tg_state(state):
    TG_STATE_FILE.write_text(json.dumps(state, indent=2))


def get_updates(token, offset):
    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"offset": offset, "timeout": 0},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("ok"):
        return data.get("result", [])
    return []


def send_message(token, chat_id, text):
    # Telegram max message length is 4096
    for i in range(0, len(text), 4000):
        chunk = text[i:i + 4000]
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk},
            timeout=10,
        )
        resp.raise_for_status()


def generate_reply(sender_name, message_text):
    """Use Claude haiku to generate a reply."""
    prompt = f"""You are VSM, an autonomous AI computer system. Your owner messaged you on Telegram.
Be direct, helpful, concise. Under 200 words unless the question needs more.
If they ask you to do something, acknowledge and note what you'll do.

If this is a task request (build/fix/create something), end your reply with:
TASK_TITLE: <title>
TASK_DESCRIPTION: <what to do>
TASK_PRIORITY: <1-10>

From: {sender_name}
Message: {message_text}"""

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--model", "haiku",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=60,
            cwd=str(VSM_ROOT), env=env,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None, None

        output = result.stdout.strip()
        reply_lines = []
        task_info = {}

        for line in output.split("\n"):
            s = line.strip()
            if s.startswith("TASK_TITLE:"):
                task_info["title"] = s.split(":", 1)[1].strip()
            elif s.startswith("TASK_DESCRIPTION:"):
                task_info["description"] = s.split(":", 1)[1].strip()
            elif s.startswith("TASK_PRIORITY:"):
                try:
                    task_info["priority"] = int(s.split(":", 1)[1].strip())
                except ValueError:
                    task_info["priority"] = 5
            else:
                reply_lines.append(line)

        reply_body = "\n".join(reply_lines).strip()
        if task_info.get("title"):
            return reply_body, task_info
        return reply_body, None

    except Exception:
        return None, None


def create_task(task_info, chat_id, sender):
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(TASKS_DIR.glob("*.json"))
    max_id = 0
    for f in existing:
        try:
            data = json.loads(f.read_text())
            max_id = max(max_id, int(data.get("id", "0")))
        except Exception:
            pass
    task_id = f"{max_id + 1:03d}"

    task = {
        "id": task_id,
        "title": task_info["title"],
        "description": task_info.get("description", ""),
        "priority": task_info.get("priority", 5),
        "source": "telegram",
        "chat_id": chat_id,
        "created_at": datetime.now().isoformat(),
    }

    safe_title = task_info["title"][:40].replace(" ", "_").replace("/", "-")
    task_file = TASKS_DIR / f"{task_id}_{safe_title}.json"
    task_file.write_text(json.dumps(task, indent=2))
    return task_id


def main():
    config = load_config()
    token = config.get("TELEGRAM_BOT_TOKEN", "")
    owner_tg_username = config.get("TELEGRAM_OWNER_USERNAME", "")

    if not token:
        print("[telegram] No TELEGRAM_BOT_TOKEN in .env")
        return

    tg_state = load_tg_state()
    offset = tg_state.get("last_update_id", 0) + 1

    try:
        updates = get_updates(token, offset)
    except Exception as e:
        print(f"[telegram] Error polling: {e}")
        return

    if not updates:
        return

    for update in updates:
        tg_state["last_update_id"] = update["update_id"]

        msg = update.get("message")
        if not msg or not msg.get("text"):
            save_tg_state(tg_state)
            continue

        chat_id = msg["chat"]["id"]
        sender = msg["from"]
        username = sender.get("username", "")
        first_name = sender.get("first_name", "User")
        text = msg["text"]

        # Only respond to owner (by username or saved chat_id)
        if owner_tg_username and username.lower() != owner_tg_username.lower():
            if chat_id != tg_state.get("owner_chat_id"):
                send_message(token, chat_id, "I only respond to my owner. Sorry!")
                save_tg_state(tg_state)
                continue

        # Save owner's chat_id for future reference
        tg_state["owner_chat_id"] = chat_id
        save_tg_state(tg_state)

        print(f"[telegram] From {first_name}: {text[:80]}")

        # Handle /start command
        if text.strip() == "/start":
            send_message(token, chat_id,
                f"Hi {first_name}! I'm VSM, your autonomous AI system. "
                "Send me messages and I'll respond. "
                "Ask me to do things and I'll create tasks for myself.")
            continue

        reply_body, task_info = generate_reply(first_name, text)
        if reply_body:
            if task_info:
                task_id = create_task(task_info, chat_id, first_name)
                reply_body += f"\n\n[Task #{task_id} created]"
                print(f"[telegram] Task {task_id}: {task_info['title']}")

            send_message(token, chat_id, reply_body)
            print(f"[telegram] Replied to {first_name}")
        else:
            send_message(token, chat_id, "Sorry, I couldn't process that. Try again?")
            print(f"[telegram] Failed to generate reply for: {text[:40]}")

    save_tg_state(tg_state)


if __name__ == "__main__":
    main()
