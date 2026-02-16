#!/usr/bin/env bash
# VSM Heartbeat — invoked by cron every 5 minutes
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export GITHUB_TOKEN="$($HOME/.local/bin/gh auth token 2>/dev/null || echo '')"
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/v2"
LOCKFILE="/tmp/vsm-heartbeat.lock"

mkdir -p "$VSM_ROOT/state/logs"

# Prevent concurrent runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

cd "$VSM_ROOT"
python3 core/controller.py 2>&1 | tee -a state/logs/heartbeat.log
