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
                recent_logs.append({
                    "file": logfile.name,
                    "time": mtime.strftime("%H:%M:%S"),
                    "content": content[:500]  # First 500 chars
                })
        except Exception:
            continue

    return recent_logs


def get_pending_tasks():
    """Get list of pending tasks."""
    if not TASKS_DIR.exists():
        return []

    tasks = []
    for taskfile in sorted(TASKS_DIR.glob("*.json")):
        try:
            task = json.loads(taskfile.read_text())
            tasks.append({
                "id": taskfile.stem,
                "title": task.get("title", "No title"),
                "status": task.get("status", "pending"),
                "criticality": task.get("criticality", 0.0)
            })
        except Exception:
            continue

    return tasks


def format_report(state, logs, tasks):
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
            "Token usage (this hour):",
            f"  Input: {token_usage.get('last_cycle_input', 0):,}",
            f"  Output: {token_usage.get('last_cycle_output', 0):,}",
            f"  Cycles tracked: {token_usage.get('cycles_tracked', 0)}",
            "",
            "Token budget (today):",
            f"  Daily soft cap: {token_budget.get('daily_soft_cap', 0):,}",
            f"  Today input: {token_budget.get('today_input', 0):,}",
            f"  Today output: {token_budget.get('today_output', 0):,}",
        ])

        if errors:
            status_lines.append("")
            status_lines.append("Recent errors:")
            for err in errors[-3:]:  # Last 3 errors
                status_lines.append(f"  {err.get('time', 'unknown')}: {err.get('error', 'unknown')}")
    else:
        status_lines.append("No state data available")

    # Activity this hour
    status_lines.extend([
        "",
        "ACTIVITY THIS HOUR",
        "-" * 60,
    ])

    if logs:
        status_lines.append(f"Log files updated: {len(logs)}")
        for log in logs[-5:]:  # Last 5 logs
            status_lines.append(f"  [{log['time']}] {log['file']}")
            preview = log['content'].split('\n')[0][:80]
            status_lines.append(f"    {preview}...")
    else:
        status_lines.append("No activity logged this hour")

    # Pending tasks
    status_lines.extend([
        "",
        "PENDING TASKS",
        "-" * 60,
    ])

    if tasks:
        for task in tasks:
            status = task['status']
            crit = task['criticality']
            status_lines.append(f"  [{task['id']}] {task['title']} (status: {status}, crit: {crit:.2f})")
    else:
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
    tasks = get_pending_tasks()

    report = format_report(state, logs, tasks)

    success = send_report(report)

    if success:
        print("[hourly_report] Report sent successfully")
    else:
        print("[hourly_report] Failed to send report")


if __name__ == "__main__":
    main()
