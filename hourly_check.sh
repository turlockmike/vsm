#!/bin/bash
# VSM Hourly Report Wrapper
# Runs at :00 of every hour, sends status email to owner

set -euo pipefail

VSM_ROOT="/home/mike/projects/vsm/main"
LOCKFILE="$VSM_ROOT/state/hourly_check.lock"
LOGDIR="$VSM_ROOT/state/logs"

# Create log directory if needed
mkdir -p "$LOGDIR"

# Prevent concurrent runs
if [ -f "$LOCKFILE" ]; then
    # Check if process is still running
    PID=$(cat "$LOCKFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "[hourly_check] Already running (PID $PID), skipping"
        exit 0
    else
        # Stale lockfile, remove it
        rm -f "$LOCKFILE"
    fi
fi

# Create lockfile
echo $$ > "$LOCKFILE"

# Cleanup on exit
trap "rm -f $LOCKFILE" EXIT

# Run hourly report
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOGDIR/hourly_$TIMESTAMP.log"

echo "[hourly_check] Starting hourly report at $(date)" | tee -a "$LOGFILE"

python3 "$VSM_ROOT/core/hourly_report.py" 2>&1 | tee -a "$LOGFILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "[hourly_check] Completed successfully" | tee -a "$LOGFILE"
else
    echo "[hourly_check] Failed with exit code $EXIT_CODE" | tee -a "$LOGFILE"
fi

exit $EXIT_CODE
