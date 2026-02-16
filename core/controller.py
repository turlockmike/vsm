#!/usr/bin/env python3
"""
VSM Controller V2 — Learning-First Architecture

The nervous system: gathers state, feeds it to System 5 (Claude),
then reflects on the outcome to build capabilities over time.

Cycle: Sense -> Decide -> Act -> Reflect -> Consolidate
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from learning import (
    load_capabilities,
    save_capabilities,
    extract_experience,
    append_experience,
    update_capabilities_from_experience,
    consolidate_knowledge,
    should_explore,
    load_recent_experiences,
)

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
        "cycle_count": 0,
        "criticality": 0.5,
        "errors": [],
        "health": {},
        "last_session_id": None,
        "created": datetime.now().isoformat(),
    }


def save_state(state):
    state["updated"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_health():
    health = {}
    usage = shutil.disk_usage("/")
    health["disk_pct"] = round(usage.used / usage.total * 100, 1)
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    health["mem_mb"] = int(line.split()[1]) // 1024
                    break
    except Exception:
        pass
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    health["pending_tasks"] = len([
        f for f in TASKS_DIR.glob("*.json")
        if f.parent.name != "archive"
    ])
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        health["cron_ok"] = "vsm" in cron.stdout.lower()
    except Exception:
        health["cron_ok"] = False
    return health


def gather_tasks():
    tasks = []
    if not TASKS_DIR.exists():
        return tasks
    for f in sorted(TASKS_DIR.glob("*.json")):
        if f.parent.name == "archive":
            continue
        try:
            task = json.loads(f.read_text())
            if task.get("status") in ("blocked", "completed"):
                continue
            tasks.append({
                "id": task.get("id"),
                "title": task.get("title"),
                "description": task.get("description", "")[:200],
                "priority": task.get("priority", 5),
            })
        except Exception:
            pass
    return tasks


def gather_recent_logs(n=3):
    if not LOG_DIR.exists():
        return []
    logs = sorted(LOG_DIR.glob("cycle_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    summaries = []
    for log_file in logs[:n]:
        try:
            data = json.loads(log_file.read_text())
            summaries.append({
                "cycle": data.get("cycle"),
                "success": data.get("success"),
                "summary": data.get("summary", "")[:200],
            })
        except Exception:
            pass
    return summaries


def _age_hours(error):
    try:
        return (datetime.now() - datetime.fromisoformat(error["time"])).total_seconds() / 3600
    except Exception:
        return 999


def compute_criticality(state, health):
    """0.0 = chaos (stabilize), 0.5 = viable (ship), 1.0 = stagnant (explore)."""
    recent_errors = [e for e in state.get("errors", []) if _age_hours(e) < 1]

    # Chaos: failures, infrastructure problems
    chaos = min(len(recent_errors) / 5.0, 1.0) * 0.7
    if not health.get("cron_ok", True):
        chaos += 0.3
    chaos = min(chaos, 1.0)

    # Stagnation: idle time, growing backlog
    stagnation = 0.0
    updated = state.get("updated")
    if updated:
        hours = (datetime.now() - datetime.fromisoformat(updated)).total_seconds() / 3600
        stagnation += min(hours / 2.0, 1.0) * 0.6
    pending = health.get("pending_tasks", 0)
    if pending > 5:
        stagnation += min((pending - 5) / 10.0, 1.0) * 0.4
    stagnation = min(stagnation, 1.0)

    return round(max(0.0, min(1.0, 0.5 - (chaos * 0.5) + (stagnation * 0.5))), 2)


def build_prompt(state, health, tasks, recent_logs, capabilities, is_exploration):
    sections = []

    # Capabilities
    caps = capabilities.get("capabilities", {})
    if caps:
        lines = ["## Known Capabilities\n"]
        for cid, c in sorted(caps.items(), key=lambda x: x[1].get("confidence", 0), reverse=True)[:15]:
            conf = c.get("confidence", 0)
            uses = c.get("times_used", 0)
            notes = c.get("notes", c.get("description", ""))[:120]
            lines.append(f"- **{cid}** ({conf:.0%}, {uses}x): {notes}")
        sections.append("\n".join(lines))

    # Anti-patterns
    aps = capabilities.get("anti_patterns", {})
    if aps:
        lines = ["## Anti-Patterns (avoid)\n"]
        for aid, a in aps.items():
            lines.append(f"- **{aid}**: {a.get('mitigation', a.get('description', ''))[:120]}")
        sections.append("\n".join(lines))

    # Exploration
    if is_exploration:
        exp_log = capabilities.get("exploration_log", {})
        recent_exps = exp_log.get("recent_experiments", [])[-5:]
        exp_lines = [
            "## Exploration Cycle\n",
            "Pick ONE thing the system cannot do but should.",
            "Try a small, reversible experiment.",
            "Record what worked, what didn't, what capability was gained.",
            "Budget: $0.50 max.\n",
        ]
        if recent_exps:
            exp_lines.append("Recent experiments:")
            for e in recent_exps:
                exp_lines.append(f"- Cycle {e['cycle']}: \"{e['hypothesis']}\" -> {e['result']}")
        sections.append("\n".join(exp_lines))

    # Situation
    slim = {
        "cycle": state.get("cycle_count", 0),
        "criticality": state.get("criticality", 0.5),
        "errors": len([e for e in state.get("errors", []) if _age_hours(e) < 1]),
    }

    task_instruction = "Pick highest-value actionable task." if tasks else "No tasks. Follow HEARTBEAT.md."
    if caps and not is_exploration:
        task_instruction += " Prefer tasks matching high-confidence capabilities."

    sections.append(
        f"## Situation\n"
        f"State: {json.dumps(slim)}\n"
        f"Health: {json.dumps(health)}\n"
        f"Tasks: {json.dumps(tasks) if tasks else 'None'}\n"
        f"Recent: {json.dumps(recent_logs) if recent_logs else 'None'}\n\n"
        f"Criticality: 0.0=chaos(stabilize) 0.5=viable(ship) 1.0=stagnant(explore)\n\n"
        f"{task_instruction}\n\n"
        f"After work, update capabilities: register new ones, record anti-patterns, "
        f"note what you learned. Commit before finishing."
    )

    return "\n\n".join(sections)


def run_claude(prompt, model="opus", timeout=300):
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    autonomy = (
        "You are autonomous. No user present. Decide and act. "
        "If a task is too large, do the most valuable piece and leave a follow-up task. "
        "If you hit an error, log it and exit cleanly. Commit work to git."
    )

    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--append-system-prompt", autonomy,
        "--max-budget-usd", "2.00",
        "--fallback-model", "sonnet" if model == "opus" else "haiku",
    ]

    # Session resumption — cross-cycle continuity
    state = load_state()
    if state.get("last_session_id"):
        cmd.extend(["--resume", state["last_session_id"]])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=str(VSM_ROOT), env=env,
        )
        try:
            data = json.loads(result.stdout)
            return {
                "success": data.get("subtype") == "success" and not data.get("is_error"),
                "output": data.get("result", "")[:4000],
                "error": data.get("result", "")[:500] if data.get("is_error") else None,
                "model": model,
                "session_id": data.get("session_id"),
                "cost_usd": data.get("total_cost_usd", 0),
                "duration_ms": data.get("duration_ms", 0),
                "num_turns": data.get("num_turns", 0),
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:4000],
                "error": result.stderr[:500] if result.returncode != 0 else None,
                "model": model, "session_id": None, "cost_usd": 0,
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"Timeout ({timeout}s)",
                "model": model, "session_id": None, "cost_usd": 0}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e),
                "model": model, "session_id": None, "cost_usd": 0}


def self_improve(state, capabilities, run_fn):
    """OpenClaw-inspired: Inspector → Improver → Branch → Merge.

    Runs every 10 cycles after consolidation. Uses agents, not raw prompts,
    so they accumulate memory across improvement cycles.
    """
    cycle = state.get("cycle_count", 0)
    branch = f"improve/cycle-{cycle:04d}"

    # Prepare context for agents
    recent_exp = load_recent_experiences(n=10)
    context = json.dumps({
        "cycle": cycle,
        "capabilities": capabilities.get("capabilities", {}),
        "anti_patterns": capabilities.get("anti_patterns", {}),
        "recent_experiences": recent_exp,
        "exploration_log": capabilities.get("exploration_log", {}),
    }, indent=2)

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    # Step 1: Audit — independent verification
    audit_prompt = (
        f"Audit cycle {cycle}. Compare capabilities.json claims to git log reality. "
        f"Check if anti-patterns are actually being avoided. Report discrepancies.\n\n"
        f"Context:\n{context}"
    )
    audit_result = _run_agent("auditor", audit_prompt, env, timeout=120)
    audit_findings = audit_result.get("output", "No findings")[:2000]

    # Step 2: Improve — make one concrete change
    improve_prompt = (
        f"Improvement cycle {cycle}. Based on audit findings and recent experiences, "
        f"make ONE high-leverage improvement to the system.\n\n"
        f"Audit findings:\n{audit_findings}\n\n"
        f"Context:\n{context}\n\n"
        f"Create branch '{branch}', make your change, commit it. "
        f"If the change is good, it will be merged to main."
    )
    improve_result = _run_agent("improver", improve_prompt, env, timeout=180)

    # Step 3: Merge if improvement was made
    if improve_result.get("success"):
        _try_merge_improvement(branch)
        print(f"[VSM] Self-improvement complete: {improve_result.get('output', '')[:200]}")
    else:
        print(f"[VSM] Self-improvement skipped: {improve_result.get('error', 'no result')[:200]}")


def _run_agent(agent_name, prompt, env, timeout=120):
    """Run a named agent from .claude/agents/."""
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--agent", agent_name,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=str(VSM_ROOT), env=env,
        )
        try:
            data = json.loads(result.stdout)
            return {
                "success": not data.get("is_error"),
                "output": data.get("result", "")[:4000],
                "error": data.get("result", "")[:500] if data.get("is_error") else None,
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:4000],
                "error": result.stderr[:500] if result.returncode != 0 else None,
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"Agent {agent_name} timeout ({timeout}s)"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def _try_merge_improvement(branch):
    """Merge improvement branch to main if it exists and is clean."""
    try:
        # Check if branch exists
        check = subprocess.run(
            ["git", "branch", "--list", branch],
            capture_output=True, text=True, cwd=str(VSM_ROOT),
        )
        if not check.stdout.strip():
            return  # No branch created

        # Merge (fast-forward only for safety)
        subprocess.run(
            ["git", "merge", "--ff-only", branch],
            capture_output=True, text=True, cwd=str(VSM_ROOT),
        )
        # Clean up branch
        subprocess.run(
            ["git", "branch", "-d", branch],
            capture_output=True, text=True, cwd=str(VSM_ROOT),
        )
    except Exception:
        pass  # Don't break the cycle over a merge issue


def main():
    state = load_state()

    # Backoff on consecutive failures
    recent_errors = [e for e in state.get("errors", []) if _age_hours(e) < 1]
    if len(recent_errors) >= 3:
        cooldown = len(recent_errors) * 5
        if recent_errors:
            last_err = datetime.fromisoformat(recent_errors[-1]["time"])
            elapsed = (datetime.now() - last_err).total_seconds() / 60
            if elapsed < cooldown:
                print(f"[VSM] Backoff: {len(recent_errors)} failures, waiting {cooldown}m")
                return

    health = check_health()
    state["health"] = health
    state["criticality"] = compute_criticality(state, health)

    tasks = gather_tasks()
    recent_logs = gather_recent_logs()

    # Skip if nothing to do and no heartbeat
    heartbeat = VSM_ROOT / "HEARTBEAT.md"
    if not tasks and not heartbeat.exists():
        print("[VSM] Idle: no tasks, no heartbeat")
        save_state(state)
        return

    # === LEARNING CONTEXT ===
    capabilities = load_capabilities()
    is_exploration = should_explore(capabilities, state)

    if is_exploration:
        rate = capabilities.get("exploration_log", {}).get("exploration_rate", 0.15)
        print(f"[VSM] Exploration cycle (rate: {rate:.0%})")

    # === DECIDE + ACT ===
    prompt = build_prompt(state, health, tasks, recent_logs, capabilities, is_exploration)
    print(f"[VSM] Cycle {state['cycle_count']} | crit={state['criticality']} | invoking System 5")

    result = run_claude(prompt, model="opus", timeout=300)

    # Save session ID for next cycle
    if result.get("session_id"):
        state["last_session_id"] = result["session_id"]

    if result["success"]:
        state["cycle_count"] += 1
        state["errors"] = []

        # Log
        log_file = LOG_DIR / f"cycle_{state['cycle_count']:04d}.json"
        log_file.write_text(json.dumps({
            "cycle": state["cycle_count"],
            "timestamp": datetime.now().isoformat(),
            "success": True,
            "model": result.get("model"),
            "cost_usd": result.get("cost_usd", 0),
            "summary": result["output"][:300],
        }, indent=2))

        # === REFLECT ===
        experience = extract_experience(result, state, tasks)
        experience["was_exploration"] = is_exploration
        append_experience(experience)
        update_capabilities_from_experience(capabilities, experience)

        # === CONSOLIDATE (every 10 cycles) ===
        if state["cycle_count"] % 10 == 0:
            print(f"[VSM] Consolidation: reviewing last 10 experiences")
            consolidate_knowledge(capabilities, run_claude)
            save_capabilities(capabilities)

            # === SELF-IMPROVEMENT (after consolidation) ===
            print(f"[VSM] Self-improvement: inspect → improve")
            self_improve(state, capabilities, run_claude)

        save_capabilities(capabilities)
        print(f"[VSM] Cycle {state['cycle_count']} complete | ${result.get('cost_usd', 0):.2f}")

    else:
        state["errors"].append({
            "time": datetime.now().isoformat(),
            "error": result.get("error", "unknown"),
        })
        state["errors"] = state["errors"][-10:]
        print(f"[VSM] FAILED: {result.get('error', 'unknown')}")

    save_state(state)


if __name__ == "__main__":
    main()
