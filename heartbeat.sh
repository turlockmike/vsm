#!/usr/bin/env bash
# VSM Heartbeat — The pulse that keeps the system alive.
# Invoked by cron. Runs the controller which decides Alpha or Beta.

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Prevent nested session errors
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/main"
LOCKFILE="/tmp/vsm-heartbeat.lock"
LOG="$VSM_ROOT/state/logs/heartbeat.log"

mkdir -p "$VSM_ROOT/state/logs"

# Prevent concurrent runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        echo "$(date -Iseconds) SKIP: previous cycle still running (pid $pid)" >> "$LOG"
        exit 0
    fi
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

echo "$(date -Iseconds) START: heartbeat cycle" >> "$LOG"

cd "$VSM_ROOT"
python3 core/controller.py >> "$LOG" 2>&1

echo "$(date -Iseconds) END: heartbeat cycle" >> "$LOG"
