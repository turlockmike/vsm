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

# Import memory system
from memory import load_memory, init_memory_files

VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / "state"
STATE_FILE = STATE_DIR / "state.json"
LOG_DIR = STATE_DIR / "logs"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
CLAUDE_BIN = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")

# Model selection strategy:
# - Opus: Complex reasoning, architecture decisions, multi-step builds
# - Sonnet: Standard feature development, code changes
# - Haiku: Quick lookups, email replies, classification, simple tasks
# The controller uses the model specified in state or defaults to opus

# Observation memory paths — the system's long-term memory
HOME_OBS = Path.home() / ".claude" / "projects" / "-home-mike" / "memory" / "observations.md"
VSM_OBS_DIR = Path.home() / ".claude" / "projects" / "-home-mike-projects-vsm-main" / "memory"
VSM_OBS = VSM_OBS_DIR / "observations.md"


def load_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        # Initialize token_usage if not present
        if "token_usage" not in state:
            state["token_usage"] = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "cycles_tracked": 0,
                "avg_input_per_cycle": 0,
                "avg_output_per_cycle": 0,
                "last_cycle_input": 0,
                "last_cycle_output": 0,
            }
        if "token_budget" not in state:
            state["token_budget"] = {
                "daily_soft_cap": 1000000,  # 1M tokens/day soft cap
                "today": datetime.now().date().isoformat(),
                "today_input": 0,
                "today_output": 0,
            }
        return state
    return {
        "criticality": 0.5,
        "last_mode": None,
        "last_action_summary": None,
        "cycle_count": 0,
        "errors": [],
        "health": {},
        "created": datetime.now().isoformat(),
        "token_usage": {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cycles_tracked": 0,
            "avg_input_per_cycle": 0,
            "avg_output_per_cycle": 0,
            "last_cycle_input": 0,
            "last_cycle_output": 0,
        },
        "token_budget": {
            "daily_soft_cap": 1000000,  # 1M tokens/day soft cap
            "today": datetime.now().date().isoformat(),
            "today_input": 0,
            "today_output": 0,
        },
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


def archive_completed_tasks():
    """Move completed tasks to archive/ directory. Keeps active queue clean."""
    if not TASKS_DIR.exists():
        return 0
    archive_dir = TASKS_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    archived = 0
    for f in TASKS_DIR.glob("*.json"):
        try:
            task = json.loads(f.read_text())
            if task.get("status") == "completed":
                f.rename(archive_dir / f.name)
                archived += 1
        except Exception:
            pass
    return archived


def gather_tasks():
    """Load tasks, filtering out blocked/completed ones to save prompt tokens."""
    tasks = []
    if TASKS_DIR.exists():
        for f in sorted(TASKS_DIR.glob("*.json")):
            if f.parent.name == "archive":
                continue
            try:
                task = json.loads(f.read_text())
                # Skip blocked/completed tasks — they can't be acted on this cycle
                if task.get("status") in ("blocked", "completed"):
                    continue
                # Slim down: only include fields System 5 needs
                slim = {
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "description": task.get("description", "")[:300],
                    "priority": task.get("priority", 5),
                    "source": task.get("source"),
                }
                tasks.append(slim)
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


def load_observations():
    """Load observational memory — token-budgeted.

    Owner context is 30KB+; we only need the tail (most recent observations).
    VSM cycle notes are small; keep all. Total target: <4KB (~1000 tokens).
    """
    obs_parts = []
    for obs_file, label, cap in [
        (HOME_OBS, "owner-context", 2500),   # ~625 tokens
        (VSM_OBS, "vsm-cycles", 1500),       # ~375 tokens
    ]:
        if obs_file.exists() and obs_file.stat().st_size > 0:
            content = obs_file.read_text().strip()
            if content:
                if len(content) > cap:
                    content = "[...truncated...]\n" + content[-cap:]
                obs_parts.append(f"[{label}]\n{content}")
    return "\n\n".join(obs_parts) if obs_parts else ""


def save_cycle_observation(cycle_count, mode, summary):
    """Append a brief observation from this cycle to the VSM observations file."""
    VSM_OBS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\nCycle {cycle_count} ({timestamp}) [{mode}]: {summary}\n"
    with open(VSM_OBS, "a") as f:
        f.write(entry)


def _load_owner_email():
    """Load owner email from .env file."""
    config_file = VSM_ROOT / ".env"
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            if line.startswith("OWNER_EMAIL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("VSM_OWNER_EMAIL", "")


def _alert_owner_via_outbox(subject, body):
    """Write alert email to outbox/ for Maildir to send. No LLM, no API."""
    owner = _load_owner_email()
    if not owner:
        return
    outbox = VSM_ROOT / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (outbox / f"alert_{ts}.txt").write_text(
        f"Thread-ID: alert-{ts}\nTo: {owner}\nSubject: {subject}\n---\n{body}\n"
    )


def _slim_state(state):
    """Extract only the fields System 5 needs for decision-making."""
    return {
        "cycle": state.get("cycle_count", 0),
        "last_action": state.get("last_action", ""),
        "criticality": state.get("criticality", 0.5),
        "errors": len(state.get("errors", [])),
        "last_error": state["errors"][-1].get("error") if state.get("errors") else None,
    }


def build_prompt(state, health, tasks, recent_logs, inbox_messages=None):
    # Email replies are handled by email_responder_v2.py (every 1 min via cron).
    # Inbox messages here are read-only context for task prioritization.
    context_section = ""
    if inbox_messages:
        context_section = "## Owner Context (already replied to by email responder)\n\n"
        for msg in inbox_messages:
            context_section += f"- **{msg.get('subject', '(no subject)')}**: {msg.get('body', '(empty)')[:150]}\n"
        context_section += "\n"

    # Load persistent memory (structured knowledge base)
    persistent_memory = load_memory()

    # Load observations (short-term cycle history)
    observations = load_observations()

    # Build memory section with both long-term and short-term context
    memory_section = ""
    if persistent_memory:
        memory_section += persistent_memory + "\n\n"
    if observations:
        memory_section += f"## Recent Observations\n{observations}\n\n"

    slim = _slim_state(state)
    # Only include health fields that matter for decisions
    compact_health = {
        "disk_pct": health.get("disk_pct_used", 0),
        "mem_mb": health.get("mem_available_mb", 0),
        "tasks": health.get("pending_tasks", 0),
        "cron": health.get("cron_installed", False),
    }

    # Cost awareness — let System 5 see today's spend
    budget = state.get("token_budget", {})
    usage = state.get("token_usage", {})
    cost_line = ""
    today_cost = budget.get("today_cost_usd", 0)
    total_cost = usage.get("total_cost_usd", 0)
    if today_cost or total_cost:
        cost_line = f"\nCost: today=${today_cost:.2f} total=${total_cost:.2f} | Prefer sonnet for routine tasks, opus for complex reasoning."

    return f"""{context_section}{memory_section}## Situation
State: {json.dumps(slim)}
Health: {json.dumps(compact_health)}
Tasks: {json.dumps(tasks) if tasks else "None"}
Recent: {json.dumps(recent_logs) if recent_logs else "None"}

Criticality: 0.0=chaos(stabilize!) 0.5=viable(ship!) 1.0=stagnant(shake things up!){cost_line}

Pick highest-value actionable task. Delegate to builder (sonnet) or researcher (haiku) via Task tool. Log to state/logs/. Commit before finishing.

Memory: Use `from core.memory import append_to_memory` to record new learnings (decisions, preferences, project changes).
"""


def parse_json_result(json_output):
    """Parse claude --output-format json result for token usage and cost."""
    try:
        data = json.loads(json_output)
        usage = data.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "cost_usd": data.get("total_cost_usd", 0),
            "duration_ms": data.get("duration_ms", 0),
            "num_turns": data.get("num_turns", 0),
            "result_text": data.get("result", ""),
            "is_error": data.get("is_error", False),
            "success": data.get("subtype") == "success",
        }
    except (json.JSONDecodeError, TypeError):
        return None


def _recent_failure_count(state):
    """Count consecutive recent failures (within last hour)."""
    cutoff = datetime.now().timestamp() - 3600
    count = 0
    for err in reversed(state.get("errors", [])):
        try:
            err_time = datetime.fromisoformat(err["time"]).timestamp()
            if err_time < cutoff:
                break
            count += 1
        except Exception:
            continue
    return count


def _should_backoff(state):
    """Return True if we should skip this cycle due to consecutive failures.

    Backoff schedule: after N consecutive failures within the last hour,
    require at least N*5 minutes since the last failure before retrying.
    This prevents hammering the API during outages or rate limits.
    """
    failures = _recent_failure_count(state)
    if failures < 2:
        return False

    # Calculate required cooldown: failures * 5 minutes
    cooldown_seconds = failures * 5 * 60
    errors = state.get("errors", [])
    if not errors:
        return False

    try:
        last_failure = datetime.fromisoformat(errors[-1]["time"])
        elapsed = (datetime.now() - last_failure).total_seconds()
        if elapsed < cooldown_seconds:
            return True
    except Exception:
        pass
    return False


def _expire_old_errors(state):
    """Remove errors older than 1 hour. Prevents stale errors from inflating counts."""
    cutoff = datetime.now().timestamp() - 3600
    state["errors"] = [
        e for e in state.get("errors", [])
        if _safe_timestamp(e) >= cutoff
    ]


def _safe_timestamp(err):
    """Parse error timestamp safely, returning 0 on failure."""
    try:
        return datetime.fromisoformat(err["time"]).timestamp()
    except Exception:
        return 0


def compute_criticality(state, health):
    """Compute criticality from system signals. 0.0=chaos, 0.5=viable, 1.0=stagnant."""

    # --- Chaos score (0.0 = no chaos, 1.0 = total chaos) ---
    failures = _recent_failure_count(state)
    chaos = 0.0
    chaos += min(failures / 6.0, 1.0) * 0.6        # failures dominate chaos signal
    if not health.get("cron_installed", True):
        chaos += 0.2                                  # no heartbeat is serious
    if health.get("disk_pct_used", 0) > 90:
        chaos += 0.1
    if health.get("mem_available_mb", 9999) < 500:
        chaos += 0.1
    chaos = min(chaos, 1.0)

    # --- Stagnation score (0.0 = active, 1.0 = fully stagnant) ---
    stagnation = 0.0

    # Time since last successful cycle
    updated = state.get("updated")
    if updated:
        hours_since = (datetime.now() - datetime.fromisoformat(updated)).total_seconds() / 3600
        stagnation += min(hours_since / 2.0, 1.0) * 0.5   # 2+ hours idle = max stagnation signal

    # Task backlog growing without completion
    pending = health.get("pending_tasks", 0)
    if pending > 5:
        stagnation += min((pending - 5) / 10.0, 1.0) * 0.3

    # Low cycle count relative to system age (system exists but doesn't do anything)
    cycle_count = state.get("cycle_count", 0)
    created = state.get("created")
    if created and cycle_count > 0:
        age_hours = (datetime.now() - datetime.fromisoformat(created)).total_seconds() / 3600
        expected_cycles = age_hours * 12  # 5-min heartbeat = 12/hr
        if expected_cycles > 0:
            throughput = cycle_count / expected_cycles
            stagnation += max(0, (1.0 - throughput)) * 0.2

    stagnation = min(stagnation, 1.0)

    # --- Criticality: map chaos and stagnation to 0.0-1.0 spectrum ---
    # High chaos → low criticality (toward 0.0)
    # High stagnation → high criticality (toward 1.0)
    # Neither → 0.5 (healthy)
    criticality = 0.5 - (chaos * 0.5) + (stagnation * 0.5)
    return round(max(0.0, min(1.0, criticality)), 2)


def run_claude(prompt, model="opus", timeout=300):
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
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--append-system-prompt", autonomy_prompt,
    ]

    # Wire in MCP servers if config exists
    mcp_config = VSM_ROOT / ".mcp.json"
    if mcp_config.exists():
        cmd.extend(["--mcp-config", str(mcp_config)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(VSM_ROOT),
            env=env,
        )

        output = result.stdout
        parsed = parse_json_result(output)

        if parsed:
            return {
                "success": parsed["success"] and not parsed["is_error"],
                "output": parsed["result_text"][:4000],
                "error": parsed["result_text"][:1000] if parsed["is_error"] else None,
                "model": model,
                "token_usage": {
                    "input_tokens": parsed["input_tokens"],
                    "output_tokens": parsed["output_tokens"],
                    "cache_creation_tokens": parsed["cache_creation_tokens"],
                    "cache_read_tokens": parsed["cache_read_tokens"],
                    "cost_usd": parsed["cost_usd"],
                },
                "duration_ms": parsed["duration_ms"],
                "num_turns": parsed["num_turns"],
            }
        else:
            # Fallback: JSON parsing failed, treat as plain text
            return {
                "success": result.returncode == 0,
                "output": output[:4000],
                "error": result.stderr[:1000] if result.returncode != 0 else None,
                "model": model,
                "token_usage": {"input_tokens": 0, "output_tokens": 0},
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"Timeout ({timeout}s)", "model": model}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e), "model": model}


def _strip_quoted_text(body):
    """Remove email signatures and quoted replies to save tokens."""
    lines = body.split("\n")
    clean = []
    for line in lines:
        # Stop at quoted text markers
        if line.startswith(">") or line.startswith("On ") and "wrote:" in line:
            break
        # Stop at signature markers
        if line.strip() in ("--", "---", "-----------------------------"):
            break
        clean.append(line)
    return "\n".join(clean).strip()


def process_inbox():
    """Read owner emails from inbox/ for context injection. Zero API calls."""
    inbox_dir = VSM_ROOT / "inbox"
    if not inbox_dir.exists():
        return {"created_tasks": []}

    messages = []
    for filepath in sorted(inbox_dir.glob("*.txt")):
        try:
            content = filepath.read_text()
            email = {}
            body_lines = []
            in_body = False
            for line in content.split("\n"):
                if line.strip() == "---":
                    in_body = True
                    continue
                if in_body:
                    body_lines.append(line)
                elif line.startswith("Subject:"):
                    email["subject"] = line.split(":", 1)[1].strip()
                elif line.startswith("Thread-ID:"):
                    email["thread_id"] = line.split(":", 1)[1].strip()
            raw_body = "\n".join(body_lines).strip()
            email["body"] = _strip_quoted_text(raw_body)
            if email.get("subject"):
                messages.append(email)
        except Exception:
            pass

    if messages:
        return {"messages": messages}
    return {}


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

    # Initialize memory files if this is first run
    init_memory_files()

    # Expire old errors (>1 hour) to prevent stale accumulation
    _expire_old_errors(state)

    # Backoff check — skip cycle if too many recent failures
    if _should_backoff(state):
        failures = _recent_failure_count(state)
        cooldown_min = failures * 5
        print(f"[VSM] Backoff: {failures} recent failures, cooling down ({cooldown_min}m window)")
        save_state(state)
        return

    health = check_health()
    state["health"] = health

    # === Launch support infrastructure ===
    # Monitor GitHub metrics and auto-triage issues during launch window
    try:
        from github_monitor import check as check_github_metrics
        github_result = check_github_metrics()
        if github_result.get("success"):
            if github_result.get("significant"):
                print(f"[VSM] GitHub: {github_result.get('changes', {})}")
        else:
            print(f"[VSM] GitHub monitor: {github_result.get('error', 'failed')}")
    except Exception as e:
        print(f"[VSM] GitHub monitor error (non-fatal): {e}")

    try:
        from issue_triage import scan as scan_issues
        triage_result = scan_issues()
        if triage_result.get("success"):
            if triage_result.get("new_issues", 0) > 0:
                print(f"[VSM] Issue triage: {triage_result.get('new_issues')} new, {triage_result.get('tasks_created')} tasks created")
        else:
            print(f"[VSM] Issue triage: {triage_result.get('error', 'failed')}")
    except Exception as e:
        print(f"[VSM] Issue triage error (non-fatal): {e}")

    # Compute criticality from system signals
    state["criticality"] = compute_criticality(state, health)

    # Read inbox emails from filesystem (Maildir) for context injection
    inbox_result = process_inbox()
    inbox_messages = inbox_result.get("messages")

    if inbox_messages:
        print(f"[VSM] Inbox: {len(inbox_messages)} emails loaded from filesystem")

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

    # Auto-archive completed tasks before gathering
    archived = archive_completed_tasks()
    if archived:
        print(f"[VSM] Archived {archived} completed task(s)")

    tasks = gather_tasks()
    recent_logs = gather_recent_logs(n=3)

    # Model selection: downgrade to sonnet after 3+ consecutive failures
    # or when daily cost exceeds threshold
    failures = _recent_failure_count(state)
    budget = state.get("token_budget", {})
    today_cost = budget.get("today_cost_usd", 0)
    cost_downgrade = today_cost > 5.0  # Downgrade to sonnet after $5/day

    model = "sonnet" if (failures >= 3 or cost_downgrade) else "opus"
    # Increase timeout for retry attempts (up to 600s max)
    timeout = min(300 + (failures * 60), 600)

    if failures > 0:
        print(f"[VSM] Recovery mode: {failures} recent failures, using model={model}, timeout={timeout}s")
    if cost_downgrade:
        print(f"[VSM] Cost cap: today=${today_cost:.2f}, downgrading to sonnet")

    print(f"[VSM] Cycle {state['cycle_count']} | Gathering state... invoking System 5")

    # === Deliver everything to System 5 (Claude) ===
    prompt = build_prompt(state, health, tasks, recent_logs, inbox_messages)
    result = run_claude(prompt, model=model, timeout=timeout)

    # Track token usage (now with real data from --output-format json)
    if result.get("token_usage"):
        tokens = result["token_usage"]
        usage = state.setdefault("token_usage", {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cache_creation": 0,
            "total_cache_read": 0,
            "total_cost_usd": 0.0,
            "cycles_tracked": 0,
            "avg_input_per_cycle": 0,
            "avg_output_per_cycle": 0,
            "last_cycle_input": 0,
            "last_cycle_output": 0,
            "last_cycle_cost_usd": 0.0,
        })

        # Update totals
        usage["total_input_tokens"] += tokens.get("input_tokens", 0)
        usage["total_output_tokens"] += tokens.get("output_tokens", 0)
        usage["total_cache_creation"] = usage.get("total_cache_creation", 0) + tokens.get("cache_creation_tokens", 0)
        usage["total_cache_read"] = usage.get("total_cache_read", 0) + tokens.get("cache_read_tokens", 0)
        usage["total_cost_usd"] = round(usage.get("total_cost_usd", 0) + tokens.get("cost_usd", 0), 4)
        usage["cycles_tracked"] += 1
        usage["last_cycle_input"] = tokens.get("input_tokens", 0)
        usage["last_cycle_output"] = tokens.get("output_tokens", 0)
        usage["last_cycle_cost_usd"] = tokens.get("cost_usd", 0)

        # Update averages
        if usage["cycles_tracked"] > 0:
            usage["avg_input_per_cycle"] = usage["total_input_tokens"] // usage["cycles_tracked"]
            usage["avg_output_per_cycle"] = usage["total_output_tokens"] // usage["cycles_tracked"]

        # Track daily budget
        budget = state.setdefault("token_budget", {
            "daily_soft_cap": 1000000,
            "today": datetime.now().date().isoformat(),
            "today_input": 0,
            "today_output": 0,
            "today_cost_usd": 0.0,
        })

        today = datetime.now().date().isoformat()
        if budget["today"] != today:
            # New day, reset daily counters
            budget["today"] = today
            budget["today_input"] = 0
            budget["today_output"] = 0
            budget["today_cost_usd"] = 0.0

        budget["today_input"] += tokens.get("input_tokens", 0)
        budget["today_output"] += tokens.get("output_tokens", 0)
        budget["today_cost_usd"] = round(budget.get("today_cost_usd", 0) + tokens.get("cost_usd", 0), 4)

    # === Minimal post-processing ===
    # The controller does NOT interpret the result or update state —
    # that's System 5's job (instructed in the prompt above).
    # We only handle catastrophic failure here.
    if not result["success"]:
        state["errors"].append({
            "time": datetime.now().isoformat(),
            "error": result.get("error", "unknown"),
            "model": result.get("model", "unknown"),
        })
        state["errors"] = state["errors"][-10:]
        state["health"] = health
        save_state(state)

        print(f"[VSM] FAILED: {result.get('error', 'unknown')}")

        # Alert if failures are accumulating — write to outbox for Maildir to send
        if len(state["errors"]) >= 5:
            try:
                _alert_owner_via_outbox(
                    "System 5 repeated failures",
                    f"VSM has had {len(state['errors'])} consecutive failures.\n"
                    f"Latest: {result.get('error')}\n"
                    f"Cycle: {state['cycle_count']}"
                )
            except Exception:
                pass
    else:
        # Increment cycle count on success
        state["cycle_count"] = state.get("cycle_count", 0) + 1
        state["last_result_success"] = True
        # Clear errors on success — the system has recovered
        state["errors"] = []
        state["health"] = health
        save_state(state)

        # Extract a brief summary from output for observation memory
        output_preview = result["output"][:300].replace("\n", " ").strip()
        if output_preview:
            try:
                save_cycle_observation(
                    state.get("cycle_count", 0),
                    "cycle",
                    output_preview[:200]
                )
            except Exception:
                pass

        # Log token usage
        token_info = ""
        if result.get("token_usage"):
            tokens = result["token_usage"]
            cost = tokens.get("cost_usd", 0)
            token_info = f" | in={tokens.get('input_tokens', 0)} out={tokens.get('output_tokens', 0)} ${cost:.4f}"

        print(f"[VSM] System 5 completed cycle{token_info}. Output preview:")
        print(result["output"][:500])


if __name__ == "__main__":
    main()
