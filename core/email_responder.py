#!/usr/bin/env python3
"""
VSM Message Responder — reads inbox/ files, writes outbox/ files.
No API calls. Sync daemons handle the plumbing.
Works with email, telegram, or any channel that writes to inbox/.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
INBOX = VSM_ROOT / "state" / "inbox"
OUTBOX = VSM_ROOT / "state" / "outbox"
ARCHIVE = INBOX / "archive"
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


def classify_and_respond(sender_name, subject, message_text, channel):
    """Use Claude to classify and draft a reply."""
    prompt = f"""You are VSM, an autonomous AI computer system. Your owner messaged you via {channel}.

CLASSIFY this message:
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
        reply_lines = []
        task_info = {}
        is_task = False

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


def create_task(task_info, source_file):
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    existing = [f for f in TASKS_DIR.glob("*.json") if f.name != "archive"]
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
        "source": source_file,
        "created_at": datetime.now().isoformat(),
    }

    safe_title = task_info["title"][:40].replace(" ", "_").replace("/", "-")
    task_file = TASKS_DIR / f"{task_id}_{safe_title}.json"
    task_file.write_text(json.dumps(task, indent=2))
    return task_id


def process_inbox():
    """Read inbox/ files, generate replies, write to outbox/, archive originals."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)
    config = load_config()

    for f in sorted(INBOX.glob("*.json")):
        try:
            msg = json.loads(f.read_text())
        except Exception:
            continue

        channel = msg.get("channel", "email")
        sender = msg.get("from", "Owner")
        subject = msg.get("subject", "(message)")
        text = msg.get("text", "")

        if not text.strip():
            f.rename(ARCHIVE / f.name)
            continue

        sender_name = sender.split("<")[0].strip() if "<" in sender else sender
        print(f"[respond] Processing {channel}: {subject}")

        reply_body, task_info = classify_and_respond(sender_name, subject, text, channel)

        if not reply_body:
            reply_body = "Got it. Working on it."

        # Write reply to outbox
        reply_file = OUTBOX / f"reply_{f.stem}.json"

        if channel == "email":
            reply_file.write_text(json.dumps({
                "channel": "email",
                "to": config.get("OWNER_EMAIL", ""),
                "subject": f"Re: {subject}",
                "text": reply_body,
                "thread_id": msg.get("thread_id"),
                "sent": False,
            }, indent=2))
        elif channel == "telegram":
            reply_file.write_text(json.dumps({
                "channel": "telegram",
                "chat_id": msg.get("chat_id", config.get("TELEGRAM_CHAT_ID", "")),
                "text": reply_body,
                "sent": False,
            }, indent=2))

        if task_info:
            tid = create_task(task_info, f.name)
            print(f"[respond] Task {tid}: {task_info['title']}")

        print(f"[respond] Reply queued via {channel}: {subject}")

        # Archive processed message
        f.rename(ARCHIVE / f.name)


def main():
    INBOX.mkdir(parents=True, exist_ok=True)
    process_inbox()


if __name__ == "__main__":
    main()
