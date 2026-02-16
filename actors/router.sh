#!/usr/bin/env bash
# actors/router.sh — Message router. Pure bash. No LLM.
#
# Runs every 1 minute via cron. Does two things:
#   1. PULL: Runs sync daemons to fetch new messages from external APIs
#   2. ROUTE: Moves messages from state/inbox/ to the correct actor's mailbox
#   3. PUSH: Delivers outbox messages via sync daemons
#
# Routing rules are simple:
#   - All inbound messages from owner → responder's mailbox
#   - Everything else → responder's mailbox (it decides what to escalate)
#
# This script is the "postman" — it doesn't read mail, it just delivers it.

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

VSM_ROOT="$HOME/projects/vsm/v2"
INBOX="$VSM_ROOT/state/inbox"
OUTBOX="$VSM_ROOT/state/outbox"
RESPONDER_MAILBOX="$VSM_ROOT/state/actors/responder/mailbox"
LOG="$VSM_ROOT/state/logs/router.log"
ROUTER_LOCK="/tmp/vsm-router.lock"

mkdir -p "$INBOX" "$OUTBOX" "$RESPONDER_MAILBOX" "$(dirname "$LOG")" "$INBOX/archive"

# --- Self-protection ---
if [ -f "$ROUTER_LOCK" ]; then
    pid=$(cat "$ROUTER_LOCK" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$ROUTER_LOCK"
fi
echo $$ > "$ROUTER_LOCK"
trap 'rm -f "$ROUTER_LOCK"' EXIT

log() {
    echo "[$(date -Iseconds)] $1" >> "$LOG"
}

cd "$VSM_ROOT"

# --- PULL: Run sync to fetch new messages ---
python3 scripts/sync_email.py 2>>"$LOG" || true
python3 scripts/sync_telegram.py --once 2>>"$LOG" || true

# --- ROUTE: Move inbox messages to responder's mailbox ---
inbox_count=$(find "$INBOX" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)

if [ "$inbox_count" -gt 0 ]; then
    log "Routing $inbox_count messages to responder"
    for msg_file in "$INBOX"/*.json; do
        [ -f "$msg_file" ] || continue
        # Copy to responder's mailbox (not move — keep original for archive)
        cp "$msg_file" "$RESPONDER_MAILBOX/"
        # Move original to inbox archive
        mv "$msg_file" "$INBOX/archive/" 2>/dev/null || true
    done
fi

# --- PUSH: Run sync to deliver any outbox messages ---
outbox_count=$(find "$OUTBOX" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)

if [ "$outbox_count" -gt 0 ]; then
    log "Pushing $outbox_count outbox messages"
    python3 scripts/sync_email.py 2>>"$LOG" || true
    python3 scripts/sync_telegram.py --once 2>>"$LOG" || true
fi
