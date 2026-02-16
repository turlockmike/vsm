#!/usr/bin/env bash
# actors/responder.sh — Fast message handler. Uses haiku. Never blocks.
#
# Runs every 1 minute via cron.
# Reads its own mailbox, replies to owner messages.
# If a question requires deep thinking, it:
#   1. Sends an immediate "thinking about it" reply
#   2. Escalates the question to the worker's mailbox
#   3. On a future cycle, checks for worker results and sends follow-up
#
# CRITICAL DESIGN CONSTRAINTS:
#   - Max runtime: 60 seconds (hard kill via timeout)
#   - Own session, never shared with any other actor
#   - If it can't answer in 60s, it says so and escalates
#   - The owner must NEVER be locked out

source "$(dirname "$0")/lib.sh"

actor_init "responder" || exit 0

# --- Check mailbox ---
MSG_COUNT=$(actor_mailbox_count)

if [ "$MSG_COUNT" -eq 0 ]; then
    actor_log "No messages. Idle."
    actor_success
    exit 0
fi

actor_log "$MSG_COUNT messages in mailbox"

# --- Build message context ---
# Read all messages from our mailbox
MESSAGES=$(python3 -c "
import json, os, sys

mailbox = '$ACTOR_MAILBOX'
archive = '$ACTOR_DIR/archive'
msgs = []

# Recent archive for conversation context (last 10)
if os.path.isdir(archive or ''):
    files = sorted(os.listdir(archive))
    for f in files[-10:]:
        if not f.endswith('.json'): continue
        try:
            m = json.load(open(os.path.join(archive, f)))
            channel = m.get('channel', m.get('type', 'unknown'))
            msgs.append(f'[CONTEXT] {m.get(\"timestamp\",\"\")} via {channel}: {m.get(\"from\",\"?\")} > {m.get(\"text\",\"\")[:200]}')
        except: pass

if msgs:
    msgs.append('')
    msgs.append('--- NEW MESSAGES (respond to these) ---')
    msgs.append('')

# Current mailbox messages
for f in sorted(os.listdir(mailbox)):
    if not f.endswith('.json'): continue
    fpath = os.path.join(mailbox, f)
    try:
        m = json.load(open(fpath))

        # Check if this is a result from the worker (not a message to reply to)
        if m.get('type') == 'worker_result':
            msgs.append(f'[WORKER RESULT] Task: {m.get(\"task\",\"?\")}')
            msgs.append(f'  Result: {m.get(\"result\",\"\")}')
            msgs.append(f'  Send follow-up reply to owner about this.')
            msgs.append(f'  Original channel: {m.get(\"channel\",\"unknown\")}')
            if m.get('chat_id'): msgs.append(f'  chat_id: {m[\"chat_id\"]}')
            if m.get('thread_id'): msgs.append(f'  thread_id: {m[\"thread_id\"]}')
            msgs.append('')
            continue

        # Normal inbound message
        channel = m.get('channel', 'unknown')
        msgs.append(f'FILE: {f}')
        msgs.append(f'  channel: {channel}')
        if m.get('thread_id'): msgs.append(f'  thread_id: {m[\"thread_id\"]}')
        if m.get('chat_id'): msgs.append(f'  chat_id: {m[\"chat_id\"]}')
        msgs.append(f'  from: {m.get(\"from\",\"?\")}')
        if m.get('subject'): msgs.append(f'  subject: {m.get(\"subject\")}')
        msgs.append(f'  text: {m.get(\"text\",\"\")[:500]}')
        msgs.append('')
    except Exception as e:
        msgs.append(f'[ERROR reading {f}: {e}]')

print('\n'.join(msgs))
" 2>/dev/null)

# If no parseable messages, just clean up and exit
if [ -z "$MESSAGES" ]; then
    actor_log "No parseable messages. Archiving all."
    for f in "$ACTOR_MAILBOX"/*.json; do
        [ -f "$f" ] && actor_archive_message "$f"
    done
    actor_success
    exit 0
fi

# --- Build the prompt ---
PROMPT="OWNER MESSAGES — respond immediately.

$MESSAGES

INSTRUCTIONS:
1. For each message, write a reply JSON file to state/outbox/:
   - Email: {\"channel\":\"email\", \"to\":\"(address from .env OWNER_EMAIL)\", \"subject\":\"Re: ...\", \"thread_id\":\"(from message)\", \"text\":\"your reply\", \"sent\":false}
   - Telegram: {\"channel\":\"telegram\", \"chat_id\":\"(from message)\", \"text\":\"your reply\", \"sent\":false}
   Copy the EXACT channel, thread_id, and chat_id from the source message.

2. If a question requires deep thinking (research, coding, multi-step work):
   - Send an immediate reply: \"Let me think about that — I'll follow up shortly.\"
   - Write an escalation file to state/actors/brain/mailbox/ with:
     {\"type\":\"escalation\", \"task\":\"description of what to do\", \"channel\":\"original channel\", \"chat_id\":\"if telegram\", \"thread_id\":\"if email\", \"from\":\"responder\"}
   The brain (supervisor) will decide whether to handle it directly or spawn a worker.

3. If you see a [WORKER RESULT], send a follow-up reply to the owner with the result.

4. After processing each message file from your mailbox, move it:
   mv state/actors/responder/mailbox/<filename> state/actors/responder/archive/

Be concise. Be helpful. Respond to every message."

# --- Call Claude ---
SESSION_ARGS=$(actor_session_args)

RESULT=$(timeout 60 claude -p "$PROMPT" \
    $SESSION_ARGS \
    --model haiku \
    --output-format json \
    --dangerously-skip-permissions \
    --max-budget-usd 0.25 \
    2>>"$ACTOR_LOG") || true

# --- Post-processing ---
actor_save_session "$RESULT"
actor_log_cost "$RESULT"
actor_success
