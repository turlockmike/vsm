#!/bin/bash
# PostToolUseFailure hook: log failures for anti-pattern detection
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
ERROR=$(echo "$INPUT" | jq -r '.error // "unknown"' | head -c 200)
echo "$(date -Iseconds)|FAIL|$TOOL|$ERROR" >> "$CLAUDE_PROJECT_DIR/state/logs/failures.log"
