---
name: escalation
description: Process an escalation from the responder
---

# Escalation Processing

The responder sends escalations to `state/actors/brain/mailbox/` when a question requires deep thinking, research, coding, or multi-step work.

## Step 1: Read Escalation

Read the escalation file from your mailbox. It contains:
- `type`: "escalation"
- `task`: Description of what the owner asked
- `channel`: "telegram" or "email"
- `chat_id`: (if telegram) for reply routing
- `thread_id`: (if email) for reply threading
- `from`: "responder"

## Step 2: Assess Complexity

- **Simple research**: Spawn a researcher agent (read-only, no worktree)
- **Code change**: Spawn a builder agent (needs worktree)
- **Quick answer**: Handle directly (no sub-agent needed)

## Step 3: Execute

### For research:
```
Task tool: subagent_type="general-purpose", name="researcher"
Prompt: "Research this question: [task]. Report findings concisely."
```

### For code changes:
Create worktree first:
```bash
cd ~/projects/vsm/.bare
git worktree add ~/projects/vsm/workbench/task-NAME -b work/task-NAME v2
```
Then spawn builder in that worktree.

### For direct answers:
Just reason about it and write the response.

## Step 4: Deliver Result

Write the result to the responder's mailbox so it can follow up with the owner:
```json
// state/actors/responder/mailbox/result-TIMESTAMP.json
{
  "type": "worker_result",
  "task": "original task description",
  "result": "the answer or summary of work done",
  "channel": "telegram or email",
  "chat_id": "if telegram",
  "thread_id": "if email"
}
```

The responder will pick this up on its next cycle and relay it to the owner.
