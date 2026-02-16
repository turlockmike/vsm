#!/usr/bin/env bash
# VSM Brain — long-running heartbeat work (exploration, building, self-improvement)
# Runs every 5 min. Can be preempted by respond.sh for owner messages.
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export GITHUB_TOKEN="$($HOME/.local/bin/gh auth token 2>/dev/null || echo '')"
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/v2"
LOCKFILE="/tmp/vsm-brain.lock"
SESSION_FILE="$VSM_ROOT/state/session_id"
STATE="$VSM_ROOT/state/state.json"
LOG="$VSM_ROOT/state/logs/brain.log"

mkdir -p "$VSM_ROOT/state/logs"

# === LOCKFILE ===
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$LOCKFILE"
fi

# Don't start if responder is active (it has priority)
RESPOND_LOCK="/tmp/vsm-respond.lock"
if [ -f "$RESPOND_LOCK" ]; then
    rpid=$(cat "$RESPOND_LOCK" 2>/dev/null)
    if kill -0 "$rpid" 2>/dev/null; then
        exit 0
    fi
fi

echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

cd "$VSM_ROOT"

# === BUILD HEARTBEAT PULSE ===
HEALTH=$(python3 -c "
import json, shutil
from pathlib import Path
h = {}
u = shutil.disk_usage('/')
h['disk_pct'] = round(u.used/u.total*100,1)
h['pending_tasks'] = len(list(Path('sandbox/tasks').glob('*.json'))) if Path('sandbox/tasks').exists() else 0
print(json.dumps(h))
" 2>/dev/null)

CYCLE=$(python3 -c "import json; print(json.load(open('$STATE')).get('cycle_count',0))" 2>/dev/null)

PULSE="HEARTBEAT (cycle $CYCLE):
Health: $HEALTH
Read HEARTBEAT.md for standing orders. Check capabilities.json. Do work. Commit.
After work, update state/state.json: increment cycle_count, set updated to now ISO timestamp."

# === RESUME THE BRAIN ===
SESSION_ARGS=""
if [ -f "$SESSION_FILE" ]; then
    SID=$(cat "$SESSION_FILE")
    if [ -n "$SID" ]; then
        SESSION_ARGS="--resume $SID"
    fi
fi

echo "[$(date -Iseconds)] Heartbeat cycle $CYCLE" >> "$LOG"

RESULT=$(timeout 540 claude -p "$PULSE" \
    $SESSION_ARGS \
    --model opus \
    --output-format json \
    --dangerously-skip-permissions \
    --max-budget-usd 2.00 \
    --fallback-model sonnet \
    2>>"$LOG") || true

# === SAVE SESSION ID ===
NEW_SID=$(echo "$RESULT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$NEW_SID" ]; then
    echo "$NEW_SID" > "$SESSION_FILE"
fi

# === LOG ===
COST=$(echo "$RESULT" | jq -r '.total_cost_usd // 0' 2>/dev/null)
echo "[$(date -Iseconds)] Done: cost=\$$COST" >> "$LOG"
