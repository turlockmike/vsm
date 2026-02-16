#!/usr/bin/env bash
# VSM Telegram — runs daemon and processes messages
# Called every 1 min via cron
set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
unset CLAUDECODE 2>/dev/null || true

VSM_ROOT="$HOME/projects/vsm/v2"
DAEMON_LOCK="/tmp/vsm-telegram-daemon.lock"
PID_FILE="/tmp/vsm-telegram-daemon.pid"

cd "$VSM_ROOT"

# Ensure daemon is running
if [ ! -f "$PID_FILE" ] || ! kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
    nohup python3 scripts/sync_telegram.py > state/logs/telegram_daemon.log 2>&1 &
    echo $! > "$PID_FILE"
fi

# Process any messages in inbox/
for msg_file in state/inbox/tg_*.json 2>/dev/null; do
    [ -f "$msg_file" ] || continue

    # Create a task for the main controller to pick up
    python3 -c "
import json
from pathlib import Path

msg = json.loads(Path('$msg_file').read_text())
task = {
    'type': 'message',
    'channel': 'telegram',
    'from': msg['from'],
    'text': msg['text'],
    'chat_id': msg['chat_id'],
    'timestamp': msg['timestamp'],
}
Path('sandbox/tasks').mkdir(parents=True, exist_ok=True)
task_file = Path('sandbox/tasks') / f\"tg_{msg['message_id']}.json\"
task_file.write_text(json.dumps(task, indent=2))
"

    # Mark as processed
    rm "$msg_file"
done

# Send any queued replies
python3 scripts/send_telegram_replies.py 2>/dev/null || true
