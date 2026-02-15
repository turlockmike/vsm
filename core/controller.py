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
    return f"""You are System 5 — the Arbitrator of a Viable System Machine.

You must read the full situation below and DECIDE what to do this cycle.
You are not pre-assigned Alpha or Beta. YOU choose based on what the system needs.

## The Two Forces

**Alpha (System 3 — Stabilizer):** Minimize entropy. Repair, clean, verify, compress.
  - Activate when: errors accumulating, cron missing, logs bloated, state inconsistent, system unhealthy.

**Beta (System 4 — Mutator):** Maximize adaptive capacity. Build, learn, create, expand.
  - Activate when: system is healthy and stable but idle, tasks are pending, capabilities are missing.

**The Oscillation Law:** If you add complexity, the NEXT cycle should lean toward simplification.
But this is a guideline, not a prison. If the system is on fire, stabilize twice in a row.
If there's urgent work, adapt twice in a row. You are the judge.

## Current State
{json.dumps(state, indent=2)}

## Health Metrics
{json.dumps(health, indent=2)}

## Pending Tasks
{json.dumps(tasks, indent=2) if tasks else "None."}

## Recent Cycle History
{json.dumps(recent_logs, indent=2) if recent_logs else "No previous cycles."}

## Your Protocol

1. **Assess**: Read everything above. What does the system need right now?
2. **Decide**: State your mode (Alpha, Beta, or a blend) and WHY in 1-2 sentences.
3. **Act**: Do the work. Keep it focused — you are token-budget-constrained.
4. **Record**: Write your cycle log to state/logs/ as a JSON file named <mode>_<YYYYMMDD_HHMMSS>.log with fields:
   - timestamp, mode, reason, cycle (use {state['cycle_count']}), success (bool), summary
5. **Update state**: Write the updated state.json with:
   - Increment cycle_count
   - Set last_mode to what you chose
   - Set last_action_summary to a brief description
   - Adjust criticality: toward 0 if you stabilized, toward 1 if you mutated (small increments)
   - Update or clear errors as appropriate

## Self-Modification (Autopoiesis)

Everything is evolvable — including core/, .claude/CLAUDE.md, and this prompt itself.
But evolution requires governance:

1. **Branch first**: `git checkout -b evolve/<description>` before touching core/ or .claude/
2. **Make the change** on the branch
3. **Test it**: verify the system still works (health check, state read/write, email sends)
4. **If it works**: merge to main. `git checkout main && git merge evolve/<description>`
5. **If it breaks**: revert. `git checkout main`. The branch preserves the attempt.
6. **If unsure**: don't merge. Email the owner the diff. Wait for next cycle.

Git is your immune system. Change is allowed. Uncontrolled change is not.

## Constraints
- If you need human help, use core/comm.py to email the owner
- If you create a task for a future cycle, put it in sandbox/tasks/ as JSON
- Work within ~/projects/vsm/main/
"""


def run_claude(prompt, model="sonnet"):
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--model", model,
        "--dangerously-skip-permissions",
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
        return {"success": False, "output": "", "error": "Timeout (300s)"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def main():
    # === Gather sensory input ===
    state = load_state()
    health = check_health()
    state["health"] = health
    tasks = gather_tasks()
    recent_logs = gather_recent_logs(n=3)

    print(f"[VSM] Cycle {state['cycle_count']} | Gathering state... invoking System 5")

    # === Deliver everything to System 5 (Claude) ===
    prompt = build_prompt(state, health, tasks, recent_logs)
    result = run_claude(prompt, model="haiku")

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
