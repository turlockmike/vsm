#!/bin/bash
# SubagentStop hook: log sub-agent completions for learning signals
INPUT=$(cat)
AGENT=$(echo "$INPUT" | jq -r '.agent_name // "unknown"')
DURATION=$(echo "$INPUT" | jq -r '.duration_ms // 0')
COST=$(echo "$INPUT" | jq -r '.total_cost_usd // 0')
echo "$(date -Iseconds)|$AGENT|${DURATION}ms|\$$COST" >> "$CLAUDE_PROJECT_DIR/state/logs/subagents.log"
