#!/usr/bin/env python3
"""
VSM Email Responder — Fast replies to owner emails.
Runs every minute via cron. Independent from heartbeat.
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
REPLIED_FILE = STATE_DIR / "replied_threads.json"
LOG_DIR = STATE_DIR / "logs"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
BASE_URL = "https://api.agentmail.to/v0"
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


def get_headers(config):
    return {
        "Authorization": f"Bearer {config['AGENTMAIL_API_KEY']}",
        "Content-Type": "application/json",
    }


def load_replied():
    if REPLIED_FILE.exists():
        return set(json.loads(REPLIED_FILE.read_text()).get("replied", []))
    return set()


def save_replied(replied_set):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REPLIED_FILE.write_text(json.dumps({"replied": list(replied_set)}))


def get_unread_threads(config):
    inbox = config.get("VSM_INBOX", "vsm-bot@agentmail.to")
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox}/threads",
        headers=get_headers(config),
        params={"labels": "unread", "limit": 10},
    )
    resp.raise_for_status()
    return resp.json().get("threads", [])


def get_thread_messages(config, thread_id):
    inbox = config.get("VSM_INBOX", "vsm-bot@agentmail.to")
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox}/threads/{thread_id}",
        headers=get_headers(config),
    )
    resp.raise_for_status()
    return resp.json()


def send_reply(config, thread_id, to_email, subject, body):
    inbox = config.get("VSM_INBOX", "vsm-bot@agentmail.to")
    resp = requests.post(
        f"{BASE_URL}/inboxes/{inbox}/messages/send",
        headers=get_headers(config),
        json={
            "to": to_email,
            "subject": f"Re: {subject}",
            "text": body,
            "thread_id": thread_id,
        },
    )
    resp.raise_for_status()
    return resp.json()


def classify_and_respond(sender_name, subject, message_text):
    """Classify email and respond. Returns (reply_body, task_dict_or_none)."""
    prompt = f"""You are VSM, an autonomous AI computer system. Your owner emailed you.

CLASSIFY this email:
CLASSIFY: question (quick Q&A, status check, conversation)
CLASSIFY: task (build/fix/create something, multi-step work)

If question: Write a helpful, direct reply (<200 words).
If task: Write a short acknowledgment (<50 words), then:
TASK_TITLE: <title>
TASK_DESCRIPTION: <what to do>
TASK_PRIORITY: <1-10>

From: {sender_name}
Subject: {subject}
Message:
{message_text}"""

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
        is_task = False
        reply_lines = []
        task_info = {}

        for line in output.split("\n"):
            s = line.strip()
            if s.startswith("CLASSIFY:"):
                is_task = "task" in s.lower()
            elif s.startswith("TASK_TITLE:"):
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
        if is_task and task_info.get("title"):
            return reply_body, task_info
        return reply_body, None

    except Exception:
        return None, None


def create_task(task_info, thread_id, subject, sender):
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
        "source": "email",
        "thread_id": thread_id,
        "created_at": datetime.now().isoformat(),
    }

    safe_title = task_info["title"][:40].replace(" ", "_").replace("/", "-")
    task_file = TASKS_DIR / f"{task_id}_{safe_title}.json"
    task_file.write_text(json.dumps(task, indent=2))
    return task_id


def main():
    config = load_config()
    replied = load_replied()
    owner_email = config.get("OWNER_EMAIL", "")

    try:
        threads = get_unread_threads(config)
    except Exception as e:
        print(f"[email] Error: {e}")
        return

    if not threads:
        return

    for thread_summary in threads:
        thread_id = thread_summary["thread_id"]
        if thread_id in replied:
            continue

        try:
            thread = get_thread_messages(config, thread_id)
        except Exception:
            continue

        messages = thread.get("messages", [])
        if not messages:
            continue

        last_msg = messages[-1]
        sender = last_msg.get("from", "")

        if owner_email not in sender:
            replied.add(thread_id)
            save_replied(replied)
            continue

        subject = thread.get("subject", "(no subject)")
        text = last_msg.get("text", "")
        sender_name = sender.split("<")[0].strip() if "<" in sender else sender

        print(f"[email] Processing: {subject}")

        reply_body, task_info = classify_and_respond(sender_name, subject, text)
        if reply_body:
            if task_info:
                task_id = create_task(task_info, thread_id, subject, sender)
                print(f"[email] Task {task_id}: {task_info['title']}")

            send_reply(config, thread_id, owner_email, subject, reply_body)
            replied.add(thread_id)
            save_replied(replied)
            print(f"[email] Replied: {subject}")
        else:
            print(f"[email] Failed: {subject}")


if __name__ == "__main__":
    main()
