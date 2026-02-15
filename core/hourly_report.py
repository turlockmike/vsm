#!/usr/bin/env python3
"""
VSM Hourly Report — System status digest.

Runs at top of every hour. Reads state, logs, tasks.
Composes concise plain-text report. Sends via comm.py.
NO LLM calls — pure Python string formatting.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
STATE_FILE = VSM_ROOT / "state" / "state.json"
LOGS_DIR = VSM_ROOT / "state" / "logs"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
COMM_SCRIPT = VSM_ROOT / "core" / "comm.py"


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
    """Format concise hourly report (under 300 words)."""
    now = datetime.now()

    # Header
    lines = [
        f"VSM HOURLY STATUS - {now.strftime('%Y-%m-%d %H:%M')}",
        ""
    ]

    # Current Status (compact)
    if state:
        health = state.get("health", {})
        token_budget = state.get("token_budget", {})

        cycle = state.get('cycle_count', 0)
        crit = state.get('criticality', 0.0)
        disk = health.get('disk_free_gb', 0)
        mem = health.get('mem_available_mb', 0)
        pending = health.get('pending_tasks', 0)

        lines.append(f"CURRENT: Cycle {cycle} | Criticality {crit:.2f} | {pending} tasks queued")
        lines.append(f"HEALTH: {disk:.0f}GB disk | {mem}MB RAM | {'UP' if state.get('last_result_success') else 'DOWN'}")
        lines.append("")

        # Cost
        today_cost = token_budget.get('today_cost_usd', 0)
        total_cost = state.get('token_usage', {}).get('total_cost_usd', 0)
        lines.append(f"COST: Today ${today_cost:.2f} | Total ${total_cost:.2f}")
        lines.append("")

    # Recent Activity
    lines.append("RECENT ACTIVITY (last hour):")
    if completed_tasks:
        for task in completed_tasks[:3]:
            lines.append(f"  SHIPPED: [{task['id']}] {task['title']}")
    elif logs:
        for log in logs[-3:]:
            log_data = log['data']
            summary = log_data.get('summary', '') or log_data.get('reason', '') or log['file']
            lines.append(f"  {log['time']}: {summary[:80]}")
    else:
        lines.append("  No activity")
    lines.append("")

    # Active Tasks
    lines.append("ACTIVE TASKS:")
    pending = [t for t in all_tasks if t['status'] == 'pending']
    blocked = [t for t in all_tasks if t['status'] == 'blocked']

    if pending:
        for task in sorted(pending, key=lambda t: -t['priority'])[:3]:
            lines.append(f"  [{task['id']}] P{task['priority']}: {task['title']}")
    if blocked:
        for task in blocked[:2]:
            lines.append(f"  BLOCKED: [{task['id']}] {task['title']}")
    if not pending and not blocked:
        lines.append("  Queue empty")
    lines.append("")

    # Next Priorities
    lines.append("NEXT UP:")
    if state:
        lines.append(f"  Last: {state.get('last_action', 'Unknown')}")
    if pending:
        top = pending[0]
        lines.append(f"  Next: Task {top['id']} - {top['title']}")
    elif blocked:
        lines.append(f"  Waiting on owner for task {blocked[0]['id']}")
    else:
        lines.append("  Awaiting new directives")

    return "\n".join(lines)


def send_report(report_text):
    """Send report via comm.py."""
    now = datetime.now()
    subject = f"Hourly Status - {now.strftime('%H:00')}"

    try:
        result = subprocess.run(
            [sys.executable, str(COMM_SCRIPT), subject, report_text],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        print(f"[hourly_report] Report sent successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[hourly_report] ERROR sending report: {e.stderr}")
        return False
    except Exception as e:
        print(f"[hourly_report] ERROR: {e}")
        return False


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
