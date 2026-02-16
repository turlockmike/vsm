#!/bin/bash
# PostToolUse hook: log file changes for learning ground truth
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
echo "$(date -Iseconds)|$TOOL|$FILE" >> "$CLAUDE_PROJECT_DIR/state/logs/changes.log"
