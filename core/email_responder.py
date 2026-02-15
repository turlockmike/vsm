#!/usr/bin/env python3
"""
VSM Email Responder — Fast, lightweight email reply loop.

Runs every minute via cron. Checks inbox for unread owner emails,
generates a reply using Haiku (fast + cheap), sends it, marks read.
Completely independent from the main heartbeat cycle.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

VSM_ROOT = Path(__file__).parent.parent
CONFIG_FILE = VSM_ROOT / ".env"
STATE_DIR = VSM_ROOT / "state"
INBOX_FILE = STATE_DIR / "inbox_id"
REPLIED_FILE = STATE_DIR / "replied_threads.json"
LOG_DIR = STATE_DIR / "logs"
BASE_URL = "https://api.agentmail.to/v0"
CLAUDE_BIN = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


def load_config():
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


def load_replied():
    if REPLIED_FILE.exists():
        return set(json.loads(REPLIED_FILE.read_text()).get("replied", []))
    return set()


def save_replied(replied_set):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPLIED_FILE, "w") as f:
        json.dump({"replied": list(replied_set)}, f)


def get_unread_threads(inbox_id):
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox_id}/threads",
        headers=get_headers(),
        params={"labels": "unread", "limit": 10},
    )
    resp.raise_for_status()
    return resp.json().get("threads", [])


def get_thread_messages(inbox_id, thread_id):
    resp = requests.get(
        f"{BASE_URL}/inboxes/{inbox_id}/threads/{thread_id}",
        headers=get_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def send_reply(inbox_id, thread_id, to_email, subject, body):
    resp = requests.post(
        f"{BASE_URL}/inboxes/{inbox_id}/messages/send",
        headers=get_headers(),
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
    """Classify the email and generate an appropriate response.

    Returns (reply_body, task_dict_or_none).
    - Quick questions/conversation: reply directly, no task
    - Real work requests: reply with acknowledgment, create task for main cycle
    """
    prompt = f"""You are VSM, an autonomous AI computer system. Your owner just emailed you.

STEP 1 — CLASSIFY this email. Output one line starting with exactly:
CLASSIFY: question
OR
CLASSIFY: task

Use "question" for: quick questions, opinions, conversational messages, status checks,
things you can answer fully right now.
Use "task" for: requests to build/create/fix something, multi-step work, anything requiring
code changes, research projects, system modifications.

STEP 2 — If CLASSIFY: question, write a helpful reply. Be direct, warm, concise (<200 words).
If CLASSIFY: task, write a short acknowledgment (<50 words) saying you'll handle it in your
next work cycle, then on a new line write:
TASK_TITLE: <short title for the task>
TASK_DESCRIPTION: <1-2 sentence description of what needs to be done>
TASK_PRIORITY: <1-10, where 10 is most urgent>

From: {sender_name}
Subject: {subject}
Message:
{message_text}"""

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--model", "haiku", "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(VSM_ROOT),
            env=env,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None, None

        output = result.stdout.strip()
        lines = output.split("\n")

        # Parse classification
        is_task = False
        reply_lines = []
        task_info = {}

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("CLASSIFY:"):
                is_task = "task" in stripped.lower()
            elif stripped.startswith("TASK_TITLE:"):
                task_info["title"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("TASK_DESCRIPTION:"):
                task_info["description"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("TASK_PRIORITY:"):
                try:
                    task_info["priority"] = int(stripped.split(":", 1)[1].strip())
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
    """Create a task JSON file for the main heartbeat cycle to pick up."""
    TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    # Find next task ID
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
        "subject": subject,
        "from": sender,
        "created_at": datetime.now().isoformat(),
    }

    task_file = TASKS_DIR / f"{task_id}_{task_info['title'][:40].replace(' ', '_').replace('/', '-')}.json"
    task_file.write_text(json.dumps(task, indent=2))
    return task_id, task_file


def main():
    config = load_config()
    inbox_id = get_inbox_id()
    replied = load_replied()
    owner_email = config["OWNER_EMAIL"]

    threads = get_unread_threads(inbox_id)
    if not threads:
        return

    for thread_summary in threads:
        thread_id = thread_summary["thread_id"]

        if thread_id in replied:
            continue

        thread = get_thread_messages(inbox_id, thread_id)
        messages = thread.get("messages", [])
        if not messages:
            continue

        # Find the latest message from the owner that we haven't replied to
        last_msg = messages[-1]
        sender = last_msg.get("from", "")

        if owner_email not in sender:
            # Not from owner — skip
            replied.add(thread_id)
            save_replied(replied)
            continue

        subject = thread.get("subject", "(no subject)")
        text = last_msg.get("text", "")
        sender_name = sender.split("<")[0].strip() if "<" in sender else sender

        print(f"[email-responder] Processing: {subject}")

        reply_body, task_info = classify_and_respond(sender_name, subject, text)
        if reply_body:
            # If it's a task, create a task file for the main cycle
            if task_info:
                task_id, task_file = create_task(task_info, thread_id, subject, sender)
                print(f"[email-responder] Created task {task_id}: {task_info['title']}")
                classification = "task"
            else:
                classification = "question"

            send_reply(inbox_id, thread_id, owner_email, subject, reply_body)
            replied.add(thread_id)
            save_replied(replied)
            print(f"[email-responder] Replied ({classification}): {subject}")

            # Log it
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_file = LOG_DIR / f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "thread_id": thread_id,
                "subject": subject,
                "classification": classification,
                "reply_length": len(reply_body),
            }
            if task_info:
                log_entry["task_created"] = task_info.get("title")
            log_file.write_text(json.dumps(log_entry, indent=2))
        else:
            print(f"[email-responder] Failed to process: {subject}")


if __name__ == "__main__":
    main()
