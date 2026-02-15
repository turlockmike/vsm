#!/usr/bin/env bash
# VSM Intelligence Monitor — Proactive scanning for AI/agent developments
# Runs every 6 hours to check HN, GitHub, competitor releases

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Export GitHub token for gh CLI
export GITHUB_TOKEN="$($HOME/.local/bin/gh auth token 2>/dev/null || echo '')"

VSM_ROOT="$HOME/projects/vsm/main"
LOCKFILE="/tmp/vsm-intelligence.lock"
LOG="$VSM_ROOT/state/logs/intelligence.log"

mkdir -p "$VSM_ROOT/state/logs"
mkdir -p "$VSM_ROOT/state/intelligence"

# Prevent concurrent runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        echo "$(date -Iseconds) SKIP: previous scan still running (pid $pid)" >> "$LOG"
        exit 0
    fi
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

echo "$(date -Iseconds) START: intelligence scan" >> "$LOG"

cd "$VSM_ROOT"
python3 core/proactive_monitor.py >> "$LOG" 2>&1

echo "$(date -Iseconds) END: intelligence scan" >> "$LOG"
