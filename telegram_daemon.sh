#!/usr/bin/env bash
# VSM Telegram Daemon — runs as a persistent background process
# Long-polls Telegram API, writes to inbox/, reads from outbox/
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/v2"
LOCKFILE="/tmp/vsm-telegram.lock"

mkdir -p "$VSM_ROOT/state/logs" "$VSM_ROOT/state/inbox" "$VSM_ROOT/state/outbox"

if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        echo "[telegram] Already running (pid $pid)"
        exit 0
    fi
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

cd "$VSM_ROOT"
python3 scripts/sync_telegram.py 2>&1 | tee -a state/logs/telegram.log
