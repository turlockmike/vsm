#!/usr/bin/env python3
"""
Hourly Status Report Generator
Sends a terse summary of VSM state at the top of every hour.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent.parent
STATE_DIR = VSM_ROOT / "state"
LOG_DIR = STATE_DIR / "logs"
STATE_FILE = STATE_DIR / "state.json"
TASK_DIR = VSM_ROOT / "sandbox" / "tasks"
OUTBOX_DIR = VSM_ROOT / "outbox"
CONFIG_FILE = VSM_ROOT / ".env"


def _load_owner_email():
    """Load owner email from .env."""
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if line.startswith("OWNER_EMAIL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("VSM_OWNER_EMAIL", "")


def get_recent_logs(hours=1):
    """Get logs from the past N hours."""
    if not LOG_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    logs = []

    for log_file in LOG_DIR.glob("*.log"):
        try:
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                continue
            data = json.loads(log_file.read_text())
            logs.append(data)
        except Exception:
            pass

    return sorted(logs, key=lambda x: x.get("timestamp", ""))


def get_active_tasks():
    """Count active tasks in queue."""
    if not TASK_DIR.exists():
        return 0
    return len(list(TASK_DIR.glob("*.json")))


def main():
    # Load state
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    else:
        state = {}

    # Gather metrics
    logs = get_recent_logs(hours=1)
    active_tasks = get_active_tasks()
    token_budget = state.get("token_budget", {})

    # Build terse report
    criticality = state.get("criticality", 0.0)
    cycle_count = state.get("cycle_count", 0)
    cost_today = token_budget.get("today_cost_usd", 0.0)

    report = f"""VSM Hourly Status — {datetime.now().strftime('%Y-%m-%d %H:00')}

Criticality: {criticality:.2f} | Cycles: {cycle_count} | Tasks: {active_tasks}
Cost today: ${cost_today:.2f}

Last hour: {len(logs)} cycles run
"""

    if logs:
        successful = sum(1 for log in logs if log.get("success"))
        report += f"Success rate: {successful}/{len(logs)}\n"

        # Show last action
        last_log = logs[-1]
        last_action = last_log.get("summary", state.get("last_action", "None"))[:150]
        report += f"Last action: {last_action}\n"
    else:
        report += "No cycles in past hour.\n"

    # Write to outbox
    owner_email = _load_owner_email()
    if not owner_email:
        print(json.dumps({"sent": False, "error": "No OWNER_EMAIL"}))
        return

    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    thread_id = f"hourly-{now.strftime('%Y%m%d-%H')}"
    outfile = OUTBOX_DIR / f"{thread_id}.txt"
    outfile.write_text(f"""Thread-ID: {thread_id}
To: {owner_email}
Subject: Hourly Status {now.strftime('%H:00')}
---
{report}""")

    print(json.dumps({
        "sent": True,
        "criticality": criticality,
        "cycles_last_hour": len(logs),
        "cost_today": cost_today
    }))


if __name__ == "__main__":
    main()
