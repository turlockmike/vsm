#!/usr/bin/env python3
"""
VSM Inbox Processor — Converts owner inbox messages into executable tasks.
Reads unreplied threads from owner and creates task JSON files.
"""

import json
import requests
import sys
from pathlib import Path
from datetime import datetime

# Import check_inbox functionality
sys.path.insert(0, str(Path(__file__).parent))
from check_inbox import check_inbox, get_inbox_id

API_KEY = "am_f645fe5d49c4ceb09695e7586e1456173d22205cd3ea2c0f70768da2ce1e69e1"
BASE_URL = "https://api.agentmail.to/v0"
OWNER_EMAIL = "michael.darmousseh@gmail.com"
TASKS_DIR = Path(__file__).parent.parent / "tasks"
STATE_DIR = Path(__file__).parent.parent.parent / "state"
PROCESSED_FILE = STATE_DIR / "processed_threads.json"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def load_processed_threads():
    """Load set of already processed thread IDs."""
    if not PROCESSED_FILE.exists():
        return set()
    with open(PROCESSED_FILE, 'r') as f:
        data = json.load(f)
    return set(data.get("processed_thread_ids", []))


def save_processed_thread(thread_id):
    """Mark a thread as processed."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    processed = load_processed_threads()
    processed.add(thread_id)
    with open(PROCESSED_FILE, 'w') as f:
        json.dump({"processed_thread_ids": list(processed)}, f, indent=2)


def get_next_task_id():
    """Find the next available task ID by checking existing task files."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_files = list(TASKS_DIR.glob("*.json"))
    if not task_files:
        return "001"

    max_id = 0
    for task_file in task_files:
        try:
            with open(task_file, 'r') as f:
                task = json.load(f)
                task_id = int(task.get("id", "0"))
                max_id = max(max_id, task_id)
        except (ValueError, json.JSONDecodeError):
            continue

    return f"{max_id + 1:03d}"


def add_label_to_message(inbox_id, message_id, label):
    """Add a label to a message via API."""
    resp = requests.patch(
        f"{BASE_URL}/inboxes/{inbox_id}/messages/{message_id}",
        headers=HEADERS,
        json={"add_labels": [label]}
    )
    resp.raise_for_status()
    return resp.json()


def extract_title(text):
    """Extract a short title from message text."""
    if not text:
        return "Task from owner"

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return "Task from owner"

    first_line = lines[0]
    # Limit to 80 chars for title
    if len(first_line) > 80:
        return first_line[:77] + "..."
    return first_line


def create_task_from_thread(thread_data, task_id):
    """Create a task JSON file from a thread."""
    messages = thread_data.get("messages", [])
    if not messages:
        return None

    # Get the first message (from owner)
    first_msg = messages[0]
    text = first_msg.get("text", "")
    subject = thread_data.get("subject", "")

    # Use subject as title if available, otherwise extract from text
    title = subject if subject else extract_title(text)

    task = {
        "id": task_id,
        "title": title,
        "description": text,
        "priority": 5,  # High priority for owner requests
        "source": "inbox",
        "thread_id": thread_data["thread_id"],
        "created_at": datetime.now().isoformat(),
        "from": first_msg.get("from", "")
    }

    task_file = TASKS_DIR / f"{task_id}.json"
    with open(task_file, 'w') as f:
        json.dump(task, f, indent=2)

    return task_file


def process_inbox():
    """
    Main processor: reads inbox, creates tasks from owner messages.
    Returns summary of processing.
    """
    result = {
        "processed": 0,
        "skipped": 0,
        "created_tasks": [],
        "errors": []
    }

    try:
        # Get unreplied threads
        inbox_data = check_inbox(unreplied_only=True)
        processed_threads = load_processed_threads()
        inbox_id = inbox_data.get("inbox_id")

        for thread in inbox_data.get("threads", []):
            thread_id = thread["thread_id"]

            # Skip if already processed
            if thread_id in processed_threads:
                result["skipped"] += 1
                continue

            # Check if thread is from owner
            messages = thread.get("messages", [])
            if not messages:
                continue

            first_msg = messages[0]
            sender = first_msg.get("from", "")

            if OWNER_EMAIL not in sender:
                # Not from owner, mark as processed but don't create task
                save_processed_thread(thread_id)
                result["skipped"] += 1
                continue

            # Create task from this thread
            task_id = get_next_task_id()
            task_file = create_task_from_thread(thread, task_id)

            if task_file:
                # Mark thread as processed
                save_processed_thread(thread_id)

                # Add "processed" label to first message (optional, for tracking)
                # Note: This might fail if message_id isn't available, so we wrap it
                try:
                    # Messages don't always have IDs in the thread response, skip labeling for now
                    pass
                except Exception as e:
                    result["errors"].append(f"Failed to label thread {thread_id}: {str(e)}")

                result["created_tasks"].append({
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "title": thread.get("subject", ""),
                    "file": str(task_file)
                })
                result["processed"] += 1

    except Exception as e:
        result["errors"].append(f"Processing error: {str(e)}")

    return result


if __name__ == "__main__":
    try:
        result = process_inbox()
        print(json.dumps(result, indent=2))

        # Exit with error code if there were errors
        if result["errors"]:
            sys.exit(1)
    except Exception as e:
        error_result = {
            "error": str(e),
            "type": type(e).__name__
        }
        print(json.dumps(error_result, indent=2), file=sys.stderr)
        sys.exit(1)
