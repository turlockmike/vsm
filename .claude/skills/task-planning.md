---
name: task-planning
description: Plan and prioritize VSM tasks. Use when deciding what to work on next or creating new tasks.
---

# Task Planning Skill

## Task File Format
Tasks live in `sandbox/tasks/<id>_<slug>.json`:
```json
{
  "id": "021",
  "title": "Short descriptive title",
  "description": "What needs to be done and why. Include context.",
  "priority": 5,
  "source": "owner-directive|system-generated|auto",
  "status": "pending|blocked|completed",
  "created_at": "2026-02-15T00:00:00Z"
}
```

## Priority Scale
- 1-3: Critical — system broken, owner blocked
- 4-5: High — important feature, owner request
- 6-7: Medium — improvement, optimization
- 8-9: Low — research, nice-to-have
- 10: Backlog

## Decision Framework
1. Is the system broken? Fix it first (priority 1-3)
2. Did the owner ask for something? Do it next (priority 4-5)
3. What ships the most value? Build it (priority 6-7)
4. What compounds over time? Research/learn (priority 8-9)

## Task Lifecycle
1. Create: Write JSON file to `sandbox/tasks/`
2. Pick: System 5 selects highest-priority non-blocked task
3. Delegate: Use Task tool with builder/researcher/reviewer agent
4. Complete: Set status to "completed" with result summary
5. Clean up: Completed tasks stay for reference (log what was done)

## When to Create Tasks vs Just Do It
- < 5 minutes of work: Just do it in this cycle
- > 5 minutes or needs research first: Create a task
- Owner request: Always create a task (tracks accountability)
- System-detected issue: Create a task if not urgent
