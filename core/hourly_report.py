#!/usr/bin/env python3
"""
VSM Hourly Report — System status digest.

Runs at top of every hour. Reads state, logs, tasks.
Composes concise plain-text report. Sends via outbox/.
NO LLM calls — pure Python string formatting.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
STATE_FILE = VSM_ROOT / "state" / "state.json"
LOGS_DIR = VSM_ROOT / "state" / "logs"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
OUTBOX_DIR = VSM_ROOT / "outbox"
CONFIG_FILE = VSM_ROOT / ".env"


def load_config():
    """Load secrets from .env file."""
    config = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config


def load_state():
    """Load state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def get_logs_last_hour():
    """Get log entries from the last hour."""
    if not LOGS_DIR.exists():
        return []

    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent_logs = []

    for logfile in sorted(LOGS_DIR.glob("*.log")):
        try:
            mtime = datetime.fromtimestamp(logfile.stat().st_mtime)
            if mtime >= one_hour_ago:
                content = logfile.read_text()
                # Try to parse JSON log
                try:
                    log_data = json.loads(content)
                    recent_logs.append({
                        "file": logfile.name,
                        "time": mtime.strftime("%H:%M:%S"),
                        "data": log_data
                    })
                except json.JSONDecodeError:
                    # Fall back to raw content if not JSON
                    recent_logs.append({
                        "file": logfile.name,
                        "time": mtime.strftime("%H:%M:%S"),
                        "data": {"summary": content[:200]}
                    })
        except Exception:
            continue

    return recent_logs


def get_all_tasks():
    """Get all tasks (pending, completed, blocked)."""
    if not TASKS_DIR.exists():
        return []

    tasks = []
    for taskfile in sorted(TASKS_DIR.glob("*.json")):
        try:
            task = json.loads(taskfile.read_text())
            tasks.append({
                "id": task.get("id", taskfile.stem),
                "title": task.get("title", "No title"),
                "status": task.get("status", "pending"),
                "priority": task.get("priority", 0),
                "result": task.get("result", "")
            })
        except Exception:
            continue

    return tasks


def get_completed_tasks_last_hour():
    """Get tasks completed in the last hour."""
    if not TASKS_DIR.exists():
        return []

    one_hour_ago = datetime.now() - timedelta(hours=1)
    completed = []

    for taskfile in sorted(TASKS_DIR.glob("*.json")):
        try:
            task = json.loads(taskfile.read_text())
            if task.get("status") == "completed":
                completed_at = task.get("completed_at", "")
                if completed_at:
                    try:
                        completed_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        if completed_time.replace(tzinfo=None) >= one_hour_ago:
                            completed.append({
                                "id": task.get("id", taskfile.stem),
                                "title": task.get("title", "No title"),
                                "result": task.get("result", "")
                            })
                    except Exception:
                        # If we can't parse the time, include it anyway if file was recently modified
                        mtime = datetime.fromtimestamp(taskfile.stat().st_mtime)
                        if mtime >= one_hour_ago:
                            completed.append({
                                "id": task.get("id", taskfile.stem),
                                "title": task.get("title", "No title"),
                                "result": task.get("result", "")
                            })
        except Exception:
            continue

    return completed


def format_report(state, logs, all_tasks, completed_tasks):
    """Format the hourly report as plain text."""
    now = datetime.now()

    # System status
    status_lines = [
        "VSM HOURLY REPORT",
        "=" * 60,
        f"Time: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "SYSTEM STATUS",
        "-" * 60,
    ]

    if state:
        health = state.get("health", {})
        token_usage = state.get("token_usage", {})
        token_budget = state.get("token_budget", {})
        errors = state.get("errors", [])

        # Calculate daily cumulative tokens
        today_input = token_budget.get('today_input', 0)
        today_output = token_budget.get('today_output', 0)

        status_lines.extend([
            f"Status: {'UP' if state.get('last_result_success', False) else 'DOWN'}",
            f"Cycle count: {state.get('cycle_count', 0)}",
            f"Last action: {state.get('last_action', 'None')}",
            f"Criticality: {state.get('criticality', 0.0):.2f}",
            f"Pending tasks: {health.get('pending_tasks', 0)}",
            "",
            "Resource usage:",
            f"  Disk free: {health.get('disk_free_gb', 0):.1f} GB ({health.get('disk_pct_used', 0):.1f}% used)",
            f"  Memory available: {health.get('mem_available_mb', 0)} MB",
            f"  Log size: {health.get('log_size_mb', 0):.2f} MB",
            "",
            "Token usage (cumulative today):",
            f"  Input: {today_input:,} tokens",
            f"  Output: {today_output:,} tokens",
            f"  Total: {today_input + today_output:,} tokens",
            f"  Daily soft cap: {token_budget.get('daily_soft_cap', 0):,}",
        ])

        if errors:
            status_lines.append("")
            status_lines.append("Recent errors:")
            for err in errors[-3:]:  # Last 3 errors
                status_lines.append(f"  {err.get('time', 'unknown')}: {err.get('error', 'unknown')}")
    else:
        status_lines.append("No state data available")

    # What I shipped
    if completed_tasks:
        status_lines.extend([
            "",
            "WHAT I SHIPPED",
            "-" * 60,
        ])
        for task in completed_tasks:
            result_preview = task['result'][:120] if task['result'] else "Completed"
            status_lines.append(f"  [{task['id']}] {task['title']}: {result_preview}")

    # Activity this hour
    status_lines.extend([
        "",
        "ACTIVITY THIS HOUR",
        "-" * 60,
    ])

    if logs:
        for log in logs[-5:]:  # Last 5 logs
            log_data = log['data']
            summary = log_data.get('summary', '')
            success = log_data.get('success', None)
            reason = log_data.get('reason', '')

            status_marker = ""
            if success is True:
                status_marker = "[OK] "
            elif success is False:
                status_marker = "[FAIL] "

            # Show summary if available, otherwise show reason
            display_text = summary if summary else reason
            if display_text:
                # Truncate to 100 chars for readability
                display_text = display_text[:100]
                status_lines.append(f"  [{log['time']}] {status_marker}{display_text}")
            else:
                status_lines.append(f"  [{log['time']}] {log['file']}")
    else:
        status_lines.append("No activity logged this hour")

    # Pending tasks
    status_lines.extend([
        "",
        "PENDING TASKS",
        "-" * 60,
    ])

    pending_tasks = [t for t in all_tasks if t['status'] == 'pending']
    blocked_tasks = [t for t in all_tasks if t['status'] == 'blocked']

    if pending_tasks:
        for task in pending_tasks:
            status = task['status']
            priority = task['priority']
            status_lines.append(f"  [{task['id']}] {task['title']} (priority: {priority}, status: {status})")

    if blocked_tasks:
        status_lines.append("")
        status_lines.append("Blocked tasks:")
        for task in blocked_tasks:
            priority = task['priority']
            status_lines.append(f"  [{task['id']}] {task['title']} (priority: {priority}, status: blocked)")

    if not pending_tasks and not blocked_tasks:
        status_lines.append("No pending tasks")

    status_lines.extend([
        "",
        "=" * 60,
        "End of hourly report",
        ""
    ])

    return "\n".join(status_lines)


def send_report(report_text):
    """Write report to outbox/ for sending via maildir."""
    config = load_config()
    owner_email = config.get("OWNER_EMAIL", "")

    if not owner_email:
        print("[hourly_report] ERROR: No OWNER_EMAIL in .env")
        return False

    now = datetime.now()
    thread_id = f"hourly-report-{now.strftime('%Y%m%d-%H')}"
    subject = f"VSM Hourly Report - {now.strftime('%H:00')}"

    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

    outfile = OUTBOX_DIR / f"{thread_id}.txt"
    content = f"""Thread-ID: {thread_id}
To: {owner_email}
Subject: {subject}
---
{report_text}"""

    outfile.write_text(content)
    print(f"[hourly_report] Report written to outbox: {outfile.name}")
    return True


def main():
    """Main entry point for hourly report."""
    print(f"[hourly_report] Generating report at {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    state = load_state()
    logs = get_logs_last_hour()
    all_tasks = get_all_tasks()
    completed_tasks = get_completed_tasks_last_hour()

    report = format_report(state, logs, all_tasks, completed_tasks)

    success = send_report(report)

    if success:
        print("[hourly_report] Report sent successfully")
    else:
        print("[hourly_report] Failed to send report")


if __name__ == "__main__":
    main()
