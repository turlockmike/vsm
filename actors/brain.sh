#!/usr/bin/env bash
# actors/brain.sh — The VSM Brain. Manager/Orchestrator.
#
# Runs every 5 minutes via cron. Resumed session provides continuity.
# Spawns sub-agents via Claude Code's Task tool for actual work:
#   - builder/improver → isolated git worktrees (write agents)
#   - researcher/auditor → read-only in v2/ (read agents)
# Brain serializes all git merges to v2 branch.
#
# Every 10 cycles, triggers the self-improvement procedure (/improve skill).
#
# The responder is NOT part of this tree — it runs separately for fault isolation.

set -euo pipefail

source "$(dirname "$0")/lib.sh"

actor_init "brain" || exit 0

# --- Ensure workbench directory exists ---
WORKTREE_BASE="$HOME/projects/vsm"
mkdir -p "$WORKTREE_BASE"

# --- Clean up any stale worktrees from crashed workers ---
cleanup_stale_worktrees() {
    [ -d "$WORKTREE_BASE/.bare" ] || return 0
    cd "$WORKTREE_BASE/.bare"
    for wt in $(git worktree list --porcelain | grep '^worktree ' | awk '{print $2}'); do
        case "$wt" in
            */.bare|*/v2) continue ;;
        esac
        if [ -d "$wt" ]; then
            local wt_age
            wt_age=$(( $(date +%s) - $(stat -c %Y "$wt" 2>/dev/null || echo "$(date +%s)") ))
            if [ "$wt_age" -gt 1800 ]; then
                actor_log "Cleaning stale worktree: $wt (age: ${wt_age}s)"
                git worktree remove --force "$wt" 2>/dev/null || true
            fi
        fi
    done
    cd "$VSM_ROOT"
}

cleanup_stale_worktrees

# --- Read cycle count ---
CYCLE=$(python3 -c "import json; print(json.load(open('state/state.json')).get('cycle_count',0))" 2>/dev/null || echo "0")

# --- Collect mailbox context ---
ESCALATIONS=""
MERGE_REQUESTS=""
OTHER_MAIL=""
shopt -s nullglob
for f in "$ACTOR_MAILBOX"/*.json; do
    content=$(cat "$f" 2>/dev/null || echo "{}")
    msg_type=$(echo "$content" | python3 -c "import json,sys; print(json.load(sys.stdin).get('type',''))" 2>/dev/null || echo "")
    case "$msg_type" in
        escalation) ESCALATIONS="${ESCALATIONS}\n$(cat "$f")\n---" ;;
        merge_request) MERGE_REQUESTS="${MERGE_REQUESTS}\n$(cat "$f")\n---" ;;
        *) OTHER_MAIL="${OTHER_MAIL}\n$(cat "$f")\n---" ;;
    esac
done
shopt -u nullglob

# --- Build the brain prompt ---
PROMPT="You are the VSM brain (cycle $CYCLE). You are a manager — you orchestrate, delegate, and merge.

## Mailbox

### Escalations from Responder
${ESCALATIONS:-None}

### Merge Requests from Workers
${MERGE_REQUESTS:-None}

### Other Messages
${OTHER_MAIL:-None}

## Your Job This Cycle
1. Process any escalations (use /escalation skill or handle directly)
2. Process any merge requests (run the git merge commands in v2/)
3. Read HEARTBEAT.md for standing orders
4. Decide what work to do — spawn sub-agents for complex tasks
5. Update state/state.json: increment cycle_count to $((CYCLE + 1)), set updated to now ISO

## Spawning Sub-Agents
Use the Task tool to spawn agents defined in .claude/agents/:
- **builder/improver** (write agents): Create a worktree first:
  \`cd ~/projects/vsm/.bare && git worktree add ~/projects/vsm/workbench/<task> -b work/<task> v2\`
  Tell the agent its working directory. After it finishes, merge:
  \`cd ~/projects/vsm/v2 && git merge --ff-only work/<task> && git worktree remove ~/projects/vsm/workbench/<task> && git branch -d work/<task>\`
- **researcher/auditor** (read agents): No worktree needed. They work read-only in ~/projects/vsm/v2/

## State Ownership (what you can write)
- state/state.json, state/capabilities.json, state/experiences.jsonl
- state/actors/responder/mailbox/ (to deliver worker results)
- codebase (v2/) — ONLY via merging worker branches, never direct edits"

# --- Improvement cycle trigger ---
if [ "$CYCLE" -gt 0 ] && [ $((CYCLE % 10)) -eq 9 ]; then
    PROMPT="${PROMPT}

## IMPROVEMENT CYCLE
This is cycle $CYCLE — next cycle ($((CYCLE + 1))) is an improvement cycle (divisible by 10).
Invoke the /improve skill to run the self-improvement procedure:
Consolidate learning → Audit → Improve → Merge → Notify owner."
fi

# --- Run the brain ---
SESSION_ARGS=$(actor_session_args)

RESULT=$(timeout 540 claude -p "$PROMPT" \
    $SESSION_ARGS \
    --model opus \
    --output-format json \
    --dangerously-skip-permissions \
    --max-budget-usd 3.00 \
    2>>"$ACTOR_LOG") || true

actor_save_session "$RESULT"
actor_log_cost "$RESULT"

# --- Archive processed mailbox items ---
for f in "$ACTOR_MAILBOX"/*.json; do
    [ -f "$f" ] && actor_archive_message "$f"
done

actor_success
