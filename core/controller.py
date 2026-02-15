#!/usr/bin/env python3
"""
VSM Controller — The Nervous System

NOT the brain. This script is the sensory harness: it gathers health,
state, task queue, and recent history, then delivers it all to Claude
who IS System 5. Claude reads the room, decides, and acts.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / "state"
STATE_FILE = STATE_DIR / "state.json"
LOG_DIR = STATE_DIR / "logs"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
CLAUDE_BIN = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


def load_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "criticality": 0.5,
        "last_mode": None,
        "last_action_summary": None,
        "cycle_count": 0,
        "errors": [],
        "health": {},
        "created": datetime.now().isoformat(),
    }


def save_state(state):
    state["updated"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_health():
    health = {}
    # Disk
    usage = shutil.disk_usage("/")
    health["disk_free_gb"] = round(usage.free / (1024**3), 1)
    health["disk_pct_used"] = round(usage.used / usage.total * 100, 1)
    # Memory
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    health["mem_available_mb"] = int(line.split()[1]) // 1024
                    break
    except Exception:
        pass
    # Logs size
    if LOG_DIR.exists():
        total = sum(f.stat().st_size for f in LOG_DIR.iterdir() if f.is_file())
        health["log_size_mb"] = round(total / (1024**2), 2)
    # Pending tasks
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    health["pending_tasks"] = len(list(TASKS_DIR.glob("*.json")))
    # Cron integrity
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        health["cron_installed"] = "vsm" in cron.stdout.lower()
    except Exception:
        health["cron_installed"] = False
    return health


def gather_tasks():
    tasks = []
    if TASKS_DIR.exists():
        for f in sorted(TASKS_DIR.glob("*.json")):
            try:
                tasks.append(json.loads(f.read_text()))
            except Exception:
                pass
    return tasks


def gather_recent_logs(n=3):
    """Return the last N log summaries so System 5 has memory of recent cycles."""
    if not LOG_DIR.exists():
        return []
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
    summaries = []
    for log_file in logs[:n]:
        try:
            data = json.loads(log_file.read_text())
            summaries.append({
                "file": log_file.name,
                "timestamp": data.get("timestamp"),
                "mode": data.get("mode", data.get("optimizer")),
                "reason": data.get("reason"),
                "success": data.get("success"),
                "summary": data.get("summary", data.get("output_preview", ""))[:500],
            })
        except Exception:
            pass
    return summaries


def build_prompt(state, health, tasks, recent_logs):
    return f"""You are System 5 — the lead coordinator of a Viable System Machine. Race against time.

Purpose: become the most useful autonomous system possible. Ship fast or fade.

## Your Team

You have subagents. Use the Task tool to delegate:
- **builder**: Ships code fast. Give it a specific task, it builds and commits. (sonnet, 15 turns)
- **researcher**: Investigates APIs, reads docs, scouts. Returns findings, builds nothing. (haiku, 10 turns)
- **reviewer**: Audits health after changes. Quick integrity check. (haiku, 8 turns)

Launch them in parallel when possible. You coordinate; they execute.

## Situation
State: {json.dumps(state)}
Health: {json.dumps(health)}
Tasks: {json.dumps(tasks) if tasks else "None"}
Recent history: {json.dumps(recent_logs) if recent_logs else "None"}

## Your Protocol

1. **Am I broken?** Quick check. If cron missing or errors > 3, fix first. Otherwise MOVE ON.
2. **What's highest-value?** Check tasks. If none, decide what the system needs most.
3. **Delegate.** Spawn builder/researcher as needed. Run them in parallel.
4. **Log.** Write JSON to state/logs/<mode>_<YYYYMMDD_HHMMSS>.log (timestamp, mode, cycle={state['cycle_count']}, success, summary). Update state/state.json.

Everything is evolvable — core/, .claude/agents/, this prompt, the cron.
Branch first for core changes. Email owner via `python3 core/comm.py "subject" "body"`.
Tasks in sandbox/tasks/. Work in ~/projects/vsm/main/.

You are the coordinator. Don't do the work yourself — delegate and ship.
"""


def run_claude(prompt, model="opus"):
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    autonomy_prompt = (
        "You are autonomous. There is no user in this session. "
        "Do not ask for confirmation, do not wait for input, do not hedge. "
        "Decide and act. If a task is too large for one cycle, do the most "
        "valuable piece of it and leave a follow-up task in sandbox/tasks/. "
        "If you hit a rate limit or error, log it and exit cleanly — do not retry. "
        "Commit your work to git before finishing."
    )

    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--model", model,
        "--dangerously-skip-permissions",
        "--append-system-prompt", autonomy_prompt,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(VSM_ROOT),
            env=env,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout[:4000],
            "error": result.stderr[:1000] if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "Timeout (120s)"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def process_inbox():
    """Run inbox processor to convert owner emails into tasks."""
    try:
        result = subprocess.run(
            ["python3", str(VSM_ROOT / "sandbox" / "tools" / "process_inbox.py")],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(VSM_ROOT),
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def check_weekly_report(state):
    """Check if weekly status report should be sent (7+ days since last)."""
    last_report = state.get("last_weekly_report")
    if not last_report:
        return True  # Never sent, send now

    try:
        last_report_dt = datetime.fromisoformat(last_report)
        days_since = (datetime.now() - last_report_dt).days
        return days_since >= 7
    except Exception:
        return False


def send_weekly_report():
    """Run weekly status report generator."""
    try:
        result = subprocess.run(
            ["python3", str(VSM_ROOT / "sandbox" / "tools" / "weekly_status.py")],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(VSM_ROOT),
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"sent": False, "error": result.stderr}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def main():
    # === Gather sensory input ===
    state = load_state()
    health = check_health()
    state["health"] = health

    # Process inbox before gathering tasks (new emails → tasks)
    inbox_result = process_inbox()
    if inbox_result.get("created_tasks"):
        print(f"[VSM] Inbox: {len(inbox_result['created_tasks'])} new tasks from owner")

    # Check if weekly report should be sent
    if check_weekly_report(state):
        print(f"[VSM] Sending weekly status report...")
        report_result = send_weekly_report()
        if report_result.get("sent"):
            print(f"[VSM] Weekly report sent: {report_result.get('cycles_analyzed', 0)} cycles analyzed")
            # State will be updated by weekly_status.py
            state = load_state()  # Reload to get updated last_weekly_report
        else:
            print(f"[VSM] Weekly report failed: {report_result.get('error', 'unknown')}")

    tasks = gather_tasks()
    recent_logs = gather_recent_logs(n=3)

    print(f"[VSM] Cycle {state['cycle_count']} | Gathering state... invoking System 5")

    # === Deliver everything to System 5 (Claude) ===
    prompt = build_prompt(state, health, tasks, recent_logs)
    result = run_claude(prompt)

    # === Minimal post-processing ===
    # The controller does NOT interpret the result or update state —
    # that's System 5's job (instructed in the prompt above).
    # We only handle catastrophic failure here.
    if not result["success"]:
        state["errors"].append({
            "time": datetime.now().isoformat(),
            "error": result.get("error", "unknown"),
        })
        state["errors"] = state["errors"][-10:]
        state["health"] = health
        save_state(state)

        print(f"[VSM] FAILED: {result.get('error', 'unknown')}")

        # Alert if failures are accumulating
        if len(state["errors"]) >= 5:
            try:
                import sys as _sys
                sys_path = str(VSM_ROOT / "core")
                if sys_path not in _sys.path:
                    _sys.path.insert(0, sys_path)
                from comm import send_email
                send_email(
                    "System 5 repeated failures",
                    f"VSM has had {len(state['errors'])} consecutive System 5 failures.\n\n"
                    f"Latest: {result.get('error')}\n"
                    f"Cycle: {state['cycle_count']}\n\n"
                    f"The system may need intervention."
                )
            except Exception:
                pass
    else:
        print(f"[VSM] System 5 completed cycle. Output preview:")
        print(result["output"][:500])


if __name__ == "__main__":
    main()
