#!/usr/bin/env python3
"""
Weekly Status Report Generator
Analyzes the past 7 days of VSM activity and emails a concise summary to the owner.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent.parent
STATE_DIR = VSM_ROOT / "state"
LOG_DIR = STATE_DIR / "logs"
STATE_FILE = STATE_DIR / "state.json"

sys.path.insert(0, str(VSM_ROOT / "core"))
from comm import send_email


def get_logs_from_last_n_days(days=7):
    """Retrieve all log files from the past N days."""
    if not LOG_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    logs = []

    for log_file in LOG_DIR.glob("*.log"):
        try:
            # Filter by file modification time
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                continue

            data = json.loads(log_file.read_text())
            logs.append(data)
        except Exception:
            pass

    return sorted(logs, key=lambda x: x.get("timestamp", ""))


def analyze_logs(logs):
    """Extract key metrics from logs."""
    total_cycles = len(logs)
    successful_cycles = sum(1 for log in logs if log.get("success"))
    errors = []
    capabilities_shipped = []
    tasks_completed = []

    for log in logs:
        # Collect errors
        if not log.get("success"):
            errors.append({
                "timestamp": log.get("timestamp"),
                "reason": log.get("reason", "unknown")
            })

        # Extract capabilities/deliverables from summaries
        summary = log.get("summary", "")
        if summary and any(keyword in summary.lower() for keyword in ["shipped", "created", "built", "added", "integrated"]):
            capabilities_shipped.append({
                "timestamp": log.get("timestamp"),
                "summary": summary[:200]  # First 200 chars
            })

        # Track completed tasks
        actions = log.get("actions", [])
        for action in actions:
            if action.get("type") == "delegate":
                tasks_completed.append({
                    "agent": action.get("agent"),
                    "task": action.get("task"),
                    "result": action.get("result", "")[:100]
                })

    return {
        "total_cycles": total_cycles,
        "successful_cycles": successful_cycles,
        "errors": errors,
        "capabilities_shipped": capabilities_shipped,
        "tasks_completed": tasks_completed,
    }


def generate_report(analysis, state):
    """Generate markdown-formatted weekly status report."""
    success_rate = (analysis["successful_cycles"] / max(analysis["total_cycles"], 1)) * 100

    report = f"""# VSM Weekly Status Report
**Period**: Past 7 days
**Date**: {datetime.now().strftime('%Y-%m-%d')}

## System Health
- **Cycles Run**: {analysis["total_cycles"]}
- **Success Rate**: {success_rate:.1f}%
- **Current Criticality**: {state.get("criticality", "unknown")}
- **Pending Tasks**: {state.get("health", {}).get("pending_tasks", 0)}

## Value Delivered

"""

    if analysis["capabilities_shipped"]:
        report += "### Capabilities Shipped\n\n"
        # Show up to 5 most recent capabilities
        for cap in analysis["capabilities_shipped"][-5:]:
            summary_lines = cap["summary"].split("\n")
            first_line = summary_lines[0].strip("*# ").strip()
            report += f"- **{cap['timestamp'][:10]}**: {first_line}\n"
        report += "\n"
    else:
        report += "No new capabilities shipped this week.\n\n"

    if analysis["tasks_completed"]:
        report += "### Tasks Completed\n\n"
        # Show up to 5 most recent tasks
        for task in analysis["tasks_completed"][-5:]:
            report += f"- **{task['agent']}**: {task['task']}\n"
        report += "\n"

    # System Status
    report += "## Current State\n\n"
    report += f"**Last Action**: {state.get('last_action', 'No recent action')}\n\n"

    health = state.get("health", {})
    report += f"**Resources**:\n"
    report += f"- Disk: {health.get('disk_free_gb', 'N/A')} GB free\n"
    report += f"- Memory: {health.get('mem_available_mb', 'N/A')} MB available\n"
    report += f"- Cron: {'Active' if health.get('cron_installed') else 'Inactive'}\n\n"

    # Errors (if any)
    if analysis["errors"]:
        report += f"## Issues Encountered ({len(analysis['errors'])})\n\n"
        for err in analysis["errors"][-3:]:  # Show last 3 errors
            report += f"- {err['timestamp'][:10]}: {err['reason'][:100]}\n"
        report += "\n"

    # What's Working Now
    report += "## What's Working Now\n\n"
    if analysis["total_cycles"] > 0:
        report += "- Autonomous heartbeat running via cron\n"
        report += "- Inbox monitoring and task conversion pipeline\n"
        report += "- Email communication with owner\n"
        report += "- Multi-agent delegation system (builder, researcher, reviewer)\n"
        report += "- Self-modification with git-based governance\n"
    else:
        report += "System is initializing. Check logs for details.\n"

    report += f"\n---\n\n"
    report += f"Repository: https://github.com/turlockmike/vsm\n"
    report += f"Generated by VSM Criticality Engine\n"

    return report


def main():
    # Load current state
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    else:
        state = {}

    # Gather logs from past 7 days
    logs = get_logs_from_last_n_days(days=7)

    if not logs:
        print(json.dumps({
            "sent": False,
            "reason": "No logs from past 7 days"
        }))
        return

    # Analyze and generate report
    analysis = analyze_logs(logs)
    report = generate_report(analysis, state)

    # Send email
    try:
        result = send_email("Weekly Status Report", report)

        # Update state to track last report
        state["last_weekly_report"] = datetime.now().isoformat()
        STATE_FILE.write_text(json.dumps(state, indent=2))

        print(json.dumps({
            "sent": True,
            "cycles_analyzed": analysis["total_cycles"],
            "capabilities_shipped": len(analysis["capabilities_shipped"]),
            "result": result
        }))
    except Exception as e:
        print(json.dumps({
            "sent": False,
            "error": str(e)
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
