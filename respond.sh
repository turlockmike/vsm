#!/usr/bin/env bash
# VSM Responder — fast interrupt handler for owner messages
# Runs every 1 min. Responds to inbox/ messages quickly via haiku.
# Can preempt the brain (kills it if needed for responsiveness).
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/v2"
LOCKFILE="/tmp/vsm-respond.lock"
BRAIN_LOCK="/tmp/vsm-brain.lock"
SESSION_FILE="$VSM_ROOT/state/session_id"
INBOX="$VSM_ROOT/state/inbox"
OUTBOX="$VSM_ROOT/state/outbox"
LOG="$VSM_ROOT/state/logs/respond.log"

mkdir -p "$VSM_ROOT/state/logs" "$INBOX" "$OUTBOX" "$INBOX/archive"

# Own lockfile — prevent concurrent responders
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

# === SYNC: pull new messages ===
python3 scripts/sync_email.py 2>>"$LOG" || true

# === CHECK INBOX ===
INBOX_COUNT=$(find "$INBOX" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)

if [ "$INBOX_COUNT" -eq 0 ]; then
    # Push any pending outbox replies, then exit
    python3 scripts/sync_email.py 2>>"$LOG" || true
    exit 0
fi

# === MESSAGES FOUND — RESPOND ===
echo "[$(date -Iseconds)] $INBOX_COUNT messages in inbox" >> "$LOG"

# Build message context — include recent conversation history from archive
MESSAGES=$(python3 -c "
import json, os
from pathlib import Path

inbox = '$INBOX'
archive = '$INBOX/archive'
msgs = []

# Load recent archived messages (last 10) for context
archived = []
if os.path.isdir(archive):
    files = sorted(os.listdir(archive))
    for f in files[-10:]:  # Last 10 archived messages
        if not f.endswith('.json'): continue
        try:
            m = json.load(open(os.path.join(archive, f)))
            archived.append({
                'file': f,
                'from': m.get('from', '?'),
                'text': m.get('text', '')[:300],
                'ts': m.get('timestamp', '')
            })
        except: pass

# Show conversation context (archive + new)
if archived:
    msgs.append('## Recent conversation (context):')
    for m in archived:
        msgs.append(f'{m[\"ts\"]} {m[\"from\"]}: {m[\"text\"]}')
    msgs.append('')
    msgs.append('## New messages (respond to these):')

# Current inbox messages
for f in sorted(os.listdir(inbox)):
    if not f.endswith('.json'): continue
    try:
        m = json.load(open(os.path.join(inbox, f)))
        msgs.append(f'FILE: state/inbox/{f}')
        msgs.append(f'  channel: {m.get(\"channel\",\"unknown\")}')
        if m.get('thread_id'): msgs.append(f'  thread_id: {m[\"thread_id\"]}')
        if m.get('chat_id'): msgs.append(f'  chat_id: {m[\"chat_id\"]}')
        msgs.append(f'  from: {m.get(\"from\",\"?\")}')
        if m.get('subject'): msgs.append(f'  subject: {m.get(\"subject\")}')
        msgs.append(f'  text: {m.get(\"text\",\"\")[:500]}')
        msgs.append('')
    except: pass
print('\n'.join(msgs))
" 2>/dev/null)

PROMPT="OWNER MESSAGES (respond immediately):
$MESSAGES
For each message, write a reply JSON file to state/outbox/:
- Email: {\"channel\":\"email\", \"to\":\"(read OWNER_EMAIL from .env)\", \"subject\":\"Re: ...\", \"thread_id\":\"(from inbox file)\", \"text\":\"your reply\", \"sent\":false}
- Telegram: {\"channel\":\"telegram\", \"chat_id\":\"(from inbox file)\", \"text\":\"your reply\", \"sent\":false}
Copy the EXACT channel, thread_id, and chat_id from the inbox file. Then move each inbox file to state/inbox/archive/."

# Resume the shared session
SESSION_ARGS=""
if [ -f "$SESSION_FILE" ]; then
    SID=$(cat "$SESSION_FILE")
    if [ -n "$SID" ]; then
        SESSION_ARGS="--resume $SID"
    fi
fi

# Wait for brain to finish if it's running (max 30 sec, then preempt)
if [ -f "$BRAIN_LOCK" ]; then
    brain_pid=$(cat "$BRAIN_LOCK" 2>/dev/null)
    if kill -0 "$brain_pid" 2>/dev/null; then
        echo "[$(date -Iseconds)] Brain running (pid $brain_pid), waiting 30s..." >> "$LOG"
        for i in $(seq 1 30); do
            kill -0 "$brain_pid" 2>/dev/null || break
            sleep 1
        done
        # If still running, preempt it — owner messages take priority
        if kill -0 "$brain_pid" 2>/dev/null; then
            echo "[$(date -Iseconds)] Preempting brain (pid $brain_pid)" >> "$LOG"
            kill "$brain_pid" 2>/dev/null || true
            sleep 2
            rm -f "$BRAIN_LOCK"
        fi
    fi
fi

RESULT=$(timeout 120 claude -p "$PROMPT" \
    $SESSION_ARGS \
    --model haiku \
    --output-format json \
    --dangerously-skip-permissions \
    --max-budget-usd 0.50 \
    2>>"$LOG") || true

# Save session ID
NEW_SID=$(echo "$RESULT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$NEW_SID" ]; then
    echo "$NEW_SID" > "$SESSION_FILE"
fi

# Push replies
python3 scripts/sync_email.py 2>>"$LOG" || true

COST=$(echo "$RESULT" | jq -r '.total_cost_usd // 0' 2>/dev/null)
echo "[$(date -Iseconds)] Responded: cost=\$$COST" >> "$LOG"
