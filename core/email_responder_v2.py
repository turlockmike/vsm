#!/usr/bin/env python3
"""
VSM Email Responder v2 — Filesystem-based email processor.

Reads emails from inbox/ directory, classifies them using simple heuristics,
and generates replies or creates tasks.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add core/ to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent))
from maildir import get_inbox_id, mark_thread_read

VSM_ROOT = Path(__file__).parent.parent
INBOX_DIR = VSM_ROOT / "inbox"
OUTBOX_DIR = VSM_ROOT / "outbox"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
LOG_DIR = VSM_ROOT / "state" / "logs"
CLAUDE_BIN = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


def parse_email_file(filepath):
    """Parse email file into structured dict."""
    content = filepath.read_text()
    lines = content.split("\n")

    email = {
        "from": "",
        "subject": "",
        "date": "",
        "thread_id": "",
        "message_id": "",
        "status": "",
        "body": "",
    }

    body_lines = []
    in_body = False

    for line in lines:
        if line.strip() == "---":
            in_body = True
            continue

        if in_body:
            body_lines.append(line)
        elif line.startswith("From:"):
            email["from"] = line.split(":", 1)[1].strip()
        elif line.startswith("Subject:"):
            email["subject"] = line.split(":", 1)[1].strip()
        elif line.startswith("Date:"):
            email["date"] = line.split(":", 1)[1].strip()
        elif line.startswith("Thread-ID:"):
            email["thread_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("Message-ID:"):
            email["message_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("Status:"):
            email["status"] = line.split(":", 1)[1].strip()

    email["body"] = "\n".join(body_lines).strip()
    return email


def classify_email(subject, body):
    """
    Classify email using simple heuristics.

    Returns: "question", "task", or "conversation"
    """
    text = (subject + " " + body).lower()

    # Task keywords
    task_keywords = ["build", "create", "fix", "add", "implement", "deploy",
                     "install", "setup", "configure", "update", "change",
                     "modify", "refactor", "optimize", "improve"]

    # Check if it's a question (short + ends with ?)
    if len(body) < 100 and body.strip().endswith("?"):
        return "question"

    # Check for task keywords
    for keyword in task_keywords:
        if re.search(r'\b' + keyword + r'\b', text):
            return "task"

    # Default to conversation
    return "conversation"


def generate_reply_with_claude(sender_name, subject, body, classification):
    """Use Claude Haiku to generate a reply."""
    if classification == "question":
        prompt = f"""You are VSM, an autonomous AI computer system. Your owner asked you a question.

Answer it directly, warmly, and concisely (under 200 words).

From: {sender_name}
Subject: {subject}
Question:
{body}"""
    else:
        # conversation
        prompt = f"""You are VSM, an autonomous AI computer system. Your owner sent you a message.

Respond warmly and naturally (under 150 words).

From: {sender_name}
Subject: {subject}
Message:
{body}"""

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
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return None


def create_task_from_email(subject, body, thread_id, sender):
    """Create a task JSON file from email."""
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

    # Extract task title from subject or first line of body
    title = subject if subject != "(no subject)" else body.split("\n")[0][:60]

    task = {
        "id": task_id,
        "title": title,
        "description": body[:500],  # First 500 chars
        "priority": 5,
        "source": "email",
        "thread_id": thread_id,
        "subject": subject,
        "from": sender,
        "created_at": datetime.now().isoformat(),
    }

    slug = re.sub(r'[^\w\s-]', '', title.lower())[:40]
    slug = re.sub(r'[-\s]+', '_', slug)
    task_file = TASKS_DIR / f"{task_id}_{slug}.json"
    task_file.write_text(json.dumps(task, indent=2))

    return task_id, task_file


def write_reply_to_outbox(thread_id, to_email, subject, body):
    """Write reply to outbox/ directory."""
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{thread_id}_reply.txt"
    filepath = OUTBOX_DIR / filename

    content = f"""Thread-ID: {thread_id}
To: {to_email}
Subject: Re: {subject}
---
{body}
"""

    filepath.write_text(content)
    return filepath


def mark_as_read(filepath):
    """Update email file status from unread to read."""
    content = filepath.read_text()
    updated = content.replace("Status: unread", "Status: read")
    filepath.write_text(updated)


def already_replied(thread_id):
    """Check if we already sent a reply for this thread_id."""
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    SENT_DIR = VSM_ROOT / "sent"
    SENT_DIR.mkdir(parents=True, exist_ok=True)

    reply_filename = f"{thread_id}_reply.txt"

    # Check if reply is queued in outbox
    if (OUTBOX_DIR / reply_filename).exists():
        return True

    # Check if reply already sent
    if (SENT_DIR / reply_filename).exists():
        return True

    return False


def process_inbox():
    """Process all unread emails in inbox/ directory."""
    if not INBOX_DIR.exists():
        print("[email-responder-v2] No inbox directory found")
        return

    unread_files = []
    for filepath in INBOX_DIR.glob("*.txt"):
        content = filepath.read_text()
        if "Status: unread" in content:
            unread_files.append(filepath)

    if not unread_files:
        print("[email-responder-v2] No unread emails")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for filepath in unread_files:
        email = parse_email_file(filepath)

        subject = email["subject"]
        body = email["body"]
        thread_id = email["thread_id"]
        sender = email["from"]
        sender_name = sender.split("<")[0].strip() if "<" in sender else sender

        # Skip if we already replied to this thread
        if already_replied(thread_id):
            print(f"[email-responder-v2] Skipping (already replied): {subject}")
            # Still mark as read locally to clean up inbox
            mark_as_read(filepath)
            continue

        print(f"[email-responder-v2] Processing: {subject}")

        # Classify
        classification = classify_email(subject, body)
        print(f"[email-responder-v2] Classification: {classification}")

        if classification == "task":
            # Create task and send acknowledgment
            task_id, task_file = create_task_from_email(subject, body, thread_id, sender)
            reply_body = f"""Got it! I'll work on this in my next cycle.

Created task {task_id}: {subject}

I'll update you when it's done."""

            write_reply_to_outbox(thread_id, sender, subject, reply_body)
            print(f"[email-responder-v2] Created task {task_id}: {subject}")

        elif classification in ["question", "conversation"]:
            # Generate reply with Claude
            reply_body = generate_reply_with_claude(sender_name, subject, body, classification)

            if reply_body:
                write_reply_to_outbox(thread_id, sender, subject, reply_body)
                print(f"[email-responder-v2] Replied ({classification}): {subject}")
            else:
                print(f"[email-responder-v2] Failed to generate reply for: {subject}")
                continue

        # Mark as read locally
        mark_as_read(filepath)

        # Mark as read in API to prevent re-sync
        try:
            inbox_id = get_inbox_id()
            mark_thread_read(inbox_id, thread_id)
        except Exception as e:
            print(f"[email-responder-v2] Warning: could not mark thread read in API: {e}")

        # DEFENSIVE: Also update synced_threads.json to prevent reprocessing
        # even if mark_thread_read fails
        try:
            from pathlib import Path
            import json
            synced_file = Path(__file__).parent.parent / "state" / "synced_threads.json"
            if synced_file.exists():
                data = json.loads(synced_file.read_text())
                synced = data.get("synced", {})
            else:
                synced = {}

            # Mark this thread as processed (use message_id if available)
            synced[thread_id] = email.get("message_id", "processed")
            synced_file.write_text(json.dumps({"synced": synced}, indent=2))
            print(f"[email-responder-v2] Updated synced tracking for thread {thread_id[:8]}...")
        except Exception as e:
            print(f"[email-responder-v2] Warning: could not update sync tracking: {e}")

        # Log it
        log_file = LOG_DIR / f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "thread_id": thread_id,
            "subject": subject,
            "classification": classification,
        }
        log_file.write_text(json.dumps(log_entry, indent=2))


def main():
    process_inbox()


if __name__ == "__main__":
    main()
