#!/bin/bash
# VSM Dashboard Launcher
# Starts the web dashboard on port 8090

PIDFILE=/tmp/vsm-dashboard.pid
DASHBOARD_SCRIPT=/home/mike/projects/vsm/main/web/server.py

# Check if already running
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Dashboard already running (PID: $OLD_PID)"
        exit 0
    else
        echo "Stale PID file found, removing..."
        rm -f "$PIDFILE"
    fi
fi

# Start the dashboard in background
python3 "$DASHBOARD_SCRIPT" > /tmp/vsm-dashboard.log 2>&1 &
NEW_PID=$!

# Save PID
echo "$NEW_PID" > "$PIDFILE"

echo "Dashboard started (PID: $NEW_PID)"
echo "Logs: /tmp/vsm-dashboard.log"
