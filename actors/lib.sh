#!/usr/bin/env bash
# actors/lib.sh — Common actor functions (the "gen_server" behaviour)
#
# Every actor sources this. It provides:
#   - Lock management (one instance per actor)
#   - Session management (each actor owns its session)
#   - Mailbox operations (filesystem-based message passing)
#   - Health reporting (for supervisor visibility)
#   - Crash tracking (for supervisor escalation)
#
# Usage in an actor script:
#   source "$(dirname "$0")/lib.sh"
#   actor_init "responder"        # Sets up dirs, acquires lock
#   actor_read_mailbox            # Returns list of message files
#   actor_session_args            # Returns "--resume <id>" or ""
#   actor_save_session "$RESULT"  # Extracts and saves session_id from JSON
#   actor_log "message"           # Writes to actor's log
#   actor_success                 # Records successful run, resets crash count
#   actor_cleanup                 # Removes lock (call in trap)

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export GITHUB_TOKEN="$($HOME/.local/bin/gh auth token 2>/dev/null || echo '')"
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/v2"
ACTORS_STATE="$VSM_ROOT/state/actors"

# --- Init ---
# Sets up the actor's world: directories, lock, working directory.
# Returns 1 if another instance is already running (caller should exit 0).
actor_init() {
    ACTOR_NAME="$1"
    ACTOR_DIR="$ACTORS_STATE/$ACTOR_NAME"
    ACTOR_LOCK="$ACTOR_DIR/lock"
    ACTOR_SESSION="$ACTOR_DIR/session_id"
    ACTOR_MAILBOX="$ACTOR_DIR/mailbox"
    ACTOR_LOG="$VSM_ROOT/state/logs/${ACTOR_NAME}.log"
    ACTOR_LAST_RUN="$ACTOR_DIR/last_run"
    ACTOR_CRASH_COUNT="$ACTOR_DIR/crash_count"
    ACTOR_DISABLED="$ACTOR_DIR/disabled"

    mkdir -p "$ACTOR_DIR" "$ACTOR_MAILBOX" "$(dirname "$ACTOR_LOG")"

    # Check if disabled by supervisor
    if [ -f "$ACTOR_DISABLED" ]; then
        echo "[$(date -Iseconds)] $ACTOR_NAME is disabled by supervisor. Exiting." >> "$ACTOR_LOG"
        return 1
    fi

    # Acquire lock — only one instance per actor
    if [ -f "$ACTOR_LOCK" ]; then
        pid=$(cat "$ACTOR_LOCK" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            # Another instance is genuinely running
            return 1
        fi
        # Stale lock — previous instance crashed
        rm -f "$ACTOR_LOCK"
    fi

    echo $$ > "$ACTOR_LOCK"
    trap 'actor_cleanup' EXIT

    cd "$VSM_ROOT"
    actor_log "Starting (pid $$)"
    return 0
}

# --- Lock cleanup ---
actor_cleanup() {
    rm -f "$ACTOR_LOCK"
}

# --- Logging ---
actor_log() {
    echo "[$(date -Iseconds)] $1" >> "$ACTOR_LOG"
}

# --- Session management ---
# Returns claude CLI args to resume this actor's session (or empty string)
actor_session_args() {
    if [ -f "$ACTOR_SESSION" ]; then
        local sid
        sid=$(cat "$ACTOR_SESSION" 2>/dev/null || echo "")
        if [ -n "$sid" ]; then
            echo "--resume $sid"
        fi
    fi
}

# Saves the session ID from a claude JSON result
actor_save_session() {
    local result="$1"
    local new_sid
    new_sid=$(echo "$result" | jq -r '.session_id // empty' 2>/dev/null || echo "")
    if [ -n "$new_sid" ]; then
        echo "$new_sid" > "$ACTOR_SESSION"
    fi
}

# Clears the session (forces fresh start next run)
actor_clear_session() {
    rm -f "$ACTOR_SESSION"
}

# --- Mailbox operations ---
# Lists message files in this actor's mailbox, sorted by name (oldest first)
actor_read_mailbox() {
    find "$ACTOR_MAILBOX" -maxdepth 1 -name '*.json' 2>/dev/null | sort
}

# Count messages in mailbox
actor_mailbox_count() {
    find "$ACTOR_MAILBOX" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l
}

# Send a message to another actor's mailbox
# Usage: actor_send "worker" "escalation" '{"task": "...", "from": "responder"}'
actor_send() {
    local target="$1"
    local msg_type="$2"
    local content="$3"
    local target_mailbox="$ACTORS_STATE/$target/mailbox"
    local filename
    filename="$(date +%s%N)-${ACTOR_NAME}-${msg_type}.json"

    mkdir -p "$target_mailbox"
    echo "$content" > "$target_mailbox/$filename"
    actor_log "Sent $msg_type to $target ($filename)"
}

# Archive a processed message (move out of mailbox)
actor_archive_message() {
    local msg_file="$1"
    local archive_dir="$ACTOR_DIR/archive"
    mkdir -p "$archive_dir"
    mv "$msg_file" "$archive_dir/" 2>/dev/null || true
}

# --- Health reporting ---
# Mark this run as successful — resets crash count, updates timestamp
actor_success() {
    date -Iseconds > "$ACTOR_LAST_RUN"
    echo "0" > "$ACTOR_CRASH_COUNT"
}

# Get consecutive crash count
actor_get_crash_count() {
    if [ -f "$ACTOR_CRASH_COUNT" ]; then
        cat "$ACTOR_CRASH_COUNT" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Increment crash count (called by supervisor, not by actors themselves)
actor_increment_crash_count() {
    local count
    count=$(actor_get_crash_count)
    echo $((count + 1)) > "$ACTOR_CRASH_COUNT"
}

# --- Cost tracking ---
actor_log_cost() {
    local result="$1"
    local cost
    cost=$(echo "$result" | jq -r '.total_cost_usd // 0' 2>/dev/null || echo "0")
    echo "$cost" > "$ACTOR_DIR/last_cost"
    actor_log "Cost: \$$cost"
}
