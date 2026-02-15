#!/usr/bin/env bash
# VSM Hourly Report — System status digest every hour.
# Runs at top of every hour via cron.

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Export GitHub token for MCP server (from gh CLI auth)
export GITHUB_TOKEN="$($HOME/.local/bin/gh auth token 2>/dev/null || echo '')"

unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/main"
LOCKFILE="/tmp/vsm-hourly.lock"

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

# Step 1: Sync outbox first (flush any pending emails)
python3 core/maildir.py sync 2>&1 | head -10

# Step 2: Generate hourly report
python3 core/hourly_report.py 2>&1

# Step 3: Send the report
python3 core/maildir.py sync 2>&1 | head -10
