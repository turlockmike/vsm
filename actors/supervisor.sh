#!/usr/bin/env bash
# actors/supervisor.sh — The init process. Pure bash. No LLM.
#
# Runs every 1 minute via cron. Checks health of all actors.
# Implements OTP's one_for_one restart strategy:
#   - If an actor is stuck (lock exists but PID is dead): clean up lock
#   - If an actor hasn't run recently: log warning
#   - If an actor keeps crashing (3+ consecutive): disable it, alert owner
#   - If responder is down: send emergency message directly to outbox
#
# Additional responsibilities:
#   - Manage telegram sync daemon (start if not running)
#   - Handle RESET command (clear all state, restart everything)
#
# This script MUST be the simplest, most reliable component in the system.
# It MUST NOT use Claude. It MUST NOT fail.

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

VSM_ROOT="$HOME/projects/vsm/v2"
ACTORS_STATE="$VSM_ROOT/state/actors"
OUTBOX="$VSM_ROOT/state/outbox"
LOG="$VSM_ROOT/state/logs/supervisor.log"
SUPERVISOR_LOCK="/tmp/vsm-supervisor.lock"
RESET_FILE="$VSM_ROOT/state/RESET"

mkdir -p "$ACTORS_STATE" "$OUTBOX" "$(dirname "$LOG")"

# --- Self-protection: only one supervisor at a time ---
if [ -f "$SUPERVISOR_LOCK" ]; then
    pid=$(cat "$SUPERVISOR_LOCK" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$SUPERVISOR_LOCK"
fi
echo $$ > "$SUPERVISOR_LOCK"
trap 'rm -f "$SUPERVISOR_LOCK"' EXIT

log() {
    echo "[$(date -Iseconds)] $1" >> "$LOG"
}

# --- RESET handler ---
# Owner sends "RESET" via Telegram → sync_telegram.py touches state/RESET
# Supervisor clears all actor state and restarts everything
if [ -f "$RESET_FILE" ]; then
    log "RESET command detected — clearing all actor state"

    # Remove all actor locks, session files, disabled flags, crash counts
    for actor_dir in "$ACTORS_STATE"/*/; do
        [ -d "$actor_dir" ] || continue
        rm -f "${actor_dir}lock" "${actor_dir}session_id" "${actor_dir}disabled" "${actor_dir}crash_count"
    done

    # Kill any running telegram daemon so it restarts fresh
    pkill -f "sync_telegram.py" 2>/dev/null || true

    rm -f "$RESET_FILE"
    log "RESET executed — all actors restarted"
fi

# --- Actor health check ---
check_actor() {
    local name="$1"
    local max_age_seconds="$2"
    local max_crashes="$3"
    local critical="$4"

    local actor_dir="$ACTORS_STATE/$name"
    local lock_file="$actor_dir/lock"
    local last_run_file="$actor_dir/last_run"
    local crash_count_file="$actor_dir/crash_count"
    local disabled_file="$actor_dir/disabled"
    local session_file="$actor_dir/session_id"

    mkdir -p "$actor_dir/mailbox"

    # Skip if disabled
    if [ -f "$disabled_file" ]; then
        return 0
    fi

    # 1. Check for stale locks (crashed process left a lock behind)
    if [ -f "$lock_file" ]; then
        local pid
        pid=$(cat "$lock_file" 2>/dev/null || echo "")
        if [ -n "$pid" ]; then
            if ! kill -0 "$pid" 2>/dev/null; then
                # Process is dead but lock exists — CRASH detected
                log "CRASH detected: $name (pid $pid is dead, lock exists)"
                rm -f "$lock_file"

                # Increment crash count
                local crashes=0
                if [ -f "$crash_count_file" ]; then
                    crashes=$(cat "$crash_count_file" 2>/dev/null || echo "0")
                fi
                crashes=$((crashes + 1))
                echo "$crashes" > "$crash_count_file"
                log "$name crash count: $crashes"

                # Clear session on crash — let it crash, start fresh
                rm -f "$session_file"
                log "$name session cleared (fresh start on next run)"

                # Check if we've hit the crash limit
                if [ "$crashes" -ge "$max_crashes" ]; then
                    log "ESCALATION: $name has crashed $crashes times. Disabling."
                    touch "$disabled_file"

                    if [ "$critical" = "yes" ]; then
                        send_emergency_alert "$name" "$crashes"
                    fi
                fi
            else
                # Process is alive — check if stuck
                local lock_age
                lock_age=$(( $(date +%s) - $(stat -c %Y "$lock_file" 2>/dev/null || echo "0") ))
                local max_runtime=$((max_age_seconds * 3))

                if [ "$lock_age" -gt "$max_runtime" ]; then
                    log "STUCK detected: $name (pid $pid) running for ${lock_age}s (max ${max_runtime}s)"
                    kill "$pid" 2>/dev/null || true
                    sleep 2
                    kill -9 "$pid" 2>/dev/null || true
                    rm -f "$lock_file"
                    rm -f "$session_file"
                    log "$name force-killed and session cleared"
                fi
            fi
        fi
    fi

    # 2. Check last_run freshness
    if [ -f "$last_run_file" ]; then
        local last_run_ts
        last_run_ts=$(date -d "$(cat "$last_run_file")" +%s 2>/dev/null || echo "0")
        local now_ts
        now_ts=$(date +%s)
        local age=$((now_ts - last_run_ts))

        if [ "$age" -gt "$max_age_seconds" ] && [ ! -f "$lock_file" ]; then
            log "WARNING: $name hasn't run in ${age}s (expected every ${max_age_seconds}s)"
        fi
    fi
}

# --- Emergency alert: bypass Claude entirely ---
send_emergency_alert() {
    local actor_name="$1"
    local crash_count="$2"
    local alert_file="$OUTBOX/emergency-$(date +%s).json"
    local chat_id

    chat_id=$(grep TELEGRAM_CHAT_ID "$VSM_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || echo "")

    if [ -n "$chat_id" ]; then
        cat > "$alert_file" <<ALERT
{
    "channel": "telegram",
    "chat_id": "$chat_id",
    "text": "VSM ALERT: $actor_name has crashed $crash_count times and has been disabled.\n\nTo recover, send RESET via Telegram.\n\nOr SSH: tail ~/projects/vsm/v2/state/logs/${actor_name}.log",
    "sent": false
}
ALERT
        log "Emergency alert written to outbox for $actor_name"
    else
        log "WARNING: No TELEGRAM_CHAT_ID in .env — cannot send emergency alert"
    fi
}

# --- Main supervision loop ---
log "Supervisor tick"

# Check each actor
#                  name        max_age  max_crashes  critical
check_actor       "responder"  180      3            "yes"
check_actor       "brain"      900      3            "yes"

# --- Telegram daemon management ---
# Ensure the telegram sync daemon is running (supervisor owns this)
if ! pgrep -f "sync_telegram.py" > /dev/null 2>&1; then
    log "Telegram daemon not running — starting"
    nohup python3 "$VSM_ROOT/scripts/sync_telegram.py" >> "$VSM_ROOT/state/logs/telegram.log" 2>&1 &
    log "Telegram daemon started (pid $!)"
fi

# --- Clean stale git worktrees ---
WORKTREE_BASE="$HOME/projects/vsm"
if command -v git &>/dev/null && [ -d "$WORKTREE_BASE/.bare" ]; then
    cd "$WORKTREE_BASE/.bare"
    while IFS= read -r line; do
        wt_path="${line#worktree }"
        case "$wt_path" in
            */.bare|*/v2) continue ;;
        esac
        if [ -d "$wt_path" ]; then
            wt_age=$(( $(date +%s) - $(stat -c %Y "$wt_path" 2>/dev/null || echo "$(date +%s)") ))
            if [ "$wt_age" -gt 3600 ]; then
                log "Cleaning orphaned worktree: $wt_path (age: ${wt_age}s)"
                git worktree remove --force "$wt_path" 2>/dev/null || true
                branch_name=$(basename "$wt_path")
                git branch -D "work/$branch_name" 2>/dev/null || true
            fi
        fi
    done < <(git worktree list --porcelain 2>/dev/null | grep '^worktree ')
    cd "$VSM_ROOT"
fi

# --- Ensure state directories exist ---
mkdir -p "$VSM_ROOT/state/inbox" "$VSM_ROOT/state/outbox" "$VSM_ROOT/state/inbox/archive"

log "Supervisor tick complete"
