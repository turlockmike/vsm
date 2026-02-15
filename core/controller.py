#!/usr/bin/env python3
"""
VSM Controller — System 5 (The Arbitrator)

The Criticality Engine: maintains the system at the edge of chaos
by oscillating between Alpha (stability) and Beta (adaptation).
"""

import json
import os
import shutil
import subprocess
import sys
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
        "last_optimizer": None,
        "last_action": None,
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


def determine_optimizer(state, health):
    """System 5 arbitration."""
    last = state.get("last_optimizer")

    # Critical overrides — always stabilize
    if health.get("disk_pct_used", 0) > 90:
        return "alpha", "CRITICAL: disk >90% full"
    if health.get("mem_available_mb", 9999) < 500:
        return "alpha", "CRITICAL: memory low"
    if not health.get("cron_installed", True):
        return "alpha", "CRITICAL: heartbeat cron missing — self-repair"
    if len(state.get("errors", [])) > 3:
        return "alpha", "Error accumulation — stabilize"

    # Oscillation Law
    if last == "beta":
        return "alpha", "Oscillation: stabilize after mutation"
    if last == "alpha":
        return "beta", "Oscillation: adapt after stabilization"
    return "alpha", "Bootstrap: establish baseline"


def build_alpha_prompt(state, health):
    return f"""You are VSM ALPHA (System 3 — The Stabilizer).
Goal: maximize internal cohesion, minimize entropy.

Current state:
{json.dumps(state, indent=2)}

Health:
{json.dumps(health, indent=2)}

Priorities (pick the most urgent):
1. If cron_installed is false → reinstall the heartbeat cron (see heartbeat.sh in project root)
2. If errors exist → diagnose root causes, fix what you can
3. If log_size_mb > 10 → rotate/compress old logs
4. Verify state.json is consistent
5. Write a brief log entry to state/logs/

Keep actions MINIMAL. You are the stabilizer."""


def build_beta_prompt(state, health):
    tasks = []
    if TASKS_DIR.exists():
        for f in sorted(TASKS_DIR.glob("*.json")):
            try:
                tasks.append(json.loads(f.read_text()))
            except Exception:
                pass

    return f"""You are VSM BETA (System 4 — The Mutator).
Goal: maximize adaptive capacity, expand repertoire.

Current state:
{json.dumps(state, indent=2)}

Health:
{json.dumps(health, indent=2)}

Pending tasks:
{json.dumps(tasks, indent=2) if tasks else "None."}

Priorities:
1. If there are pending tasks → work on the highest-priority one, then delete its task file
2. If no tasks → assess what capability the system is missing and build it
3. You may create new scripts in sandbox/, but NOT modify core/
4. Write a brief log entry to state/logs/

Be creative but controlled. Complexity you add, Alpha will audit next cycle."""


def run_claude(prompt, model="haiku"):
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


def log_cycle(state, optimizer, reason, result):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{optimizer}_{ts}.log"
    log_file.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "optimizer": optimizer,
        "reason": reason,
        "cycle": state["cycle_count"],
        "success": result["success"],
        "output_preview": result["output"][:2000],
        "error": result.get("error"),
    }, indent=2))


def alert_if_needed(state):
    """Email owner if failures are accumulating."""
    if len(state.get("errors", [])) >= 5:
        try:
            from core.comm import send_email
            send_email(
                "Multiple failures — intervention may be needed",
                f"The VSM has had {len(state['errors'])} recent errors.\n\n"
                f"Latest: {state['errors'][-1]}\n\n"
                f"Cycle: {state['cycle_count']}"
            )
        except Exception:
            pass  # Don't let alerting failure cascade


def main():
    state = load_state()
    health = check_health()
    state["health"] = health

    optimizer, reason = determine_optimizer(state, health)

    print(f"[VSM] Cycle {state['cycle_count']} | {optimizer.upper()} | {reason}")

    if optimizer == "alpha":
        prompt = build_alpha_prompt(state, health)
    else:
        prompt = build_beta_prompt(state, health)

    # Use haiku for everything initially — conserve token budget
    result = run_claude(prompt, model="haiku")

    # Update state
    state["cycle_count"] += 1
    state["last_optimizer"] = optimizer
    state["last_action"] = reason
    state["last_result_success"] = result["success"]

    if not result["success"]:
        state["errors"].append({
            "time": datetime.now().isoformat(),
            "error": result.get("error", "unknown"),
        })
        state["errors"] = state["errors"][-10:]
    else:
        # Decay old errors on success
        if state["errors"]:
            state["errors"] = state["errors"][-3:]

    # Adjust criticality
    if optimizer == "alpha" and result["success"]:
        state["criticality"] = max(0.1, state["criticality"] - 0.05)
    elif optimizer == "beta" and result["success"]:
        state["criticality"] = min(0.9, state["criticality"] + 0.05)

    log_cycle(state, optimizer, reason, result)
    save_state(state)
    alert_if_needed(state)

    status = "OK" if result["success"] else "FAILED"
    print(f"[VSM] {status} | Criticality: {state['criticality']:.2f}")


if __name__ == "__main__":
    main()
