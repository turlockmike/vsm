---
name: improve
description: Run the 10-cycle self-improvement procedure
---

# Self-Improvement Procedure

Run this when cycle_count % 10 == 0 and cycle_count > 0.

## Step 1: Consolidate Learning

Read `state/experiences.jsonl` (last 100 entries). Identify patterns:
- Which capabilities succeeded consistently? Increase confidence.
- Which capabilities failed? Decrease confidence or add anti-patterns.
- What new capabilities emerged? Add to `state/capabilities.json`.
- What anti-patterns recurred? Strengthen mitigations.

Update `state/capabilities.json` with findings.

## Step 2: Audit (spawn auditor agent)

Spawn the auditor agent via Task tool:
```
Task tool: subagent_type="general-purpose", name="auditor"
Prompt: "You are the VSM auditor. Verify these capability claims against reality:
[paste top 5 capabilities from capabilities.json]
Check git log, actual file contents, and test results. Report discrepancies."
```

The auditor works read-only in ~/projects/vsm/v2/. No worktree needed.

## Step 3: Improve (spawn improver agent in worktree)

Based on consolidation + audit findings, identify ONE high-leverage improvement.

Create a worktree for the improver:
```bash
cd ~/projects/vsm/.bare
git worktree add ~/projects/vsm/workbench/improve-cycle-NNN -b work/improve-cycle-NNN v2
```

Spawn the improver agent via Task tool:
```
Task tool: subagent_type="general-purpose", name="improver"
Prompt: "You are the VSM improver. Your working directory is ~/projects/vsm/workbench/improve-cycle-NNN.
Based on these findings: [consolidation + audit results]
Make ONE concrete improvement. Commit to your branch with a clear message."
```

## Step 4: Merge

After the improver completes:
```bash
cd ~/projects/vsm/v2
git merge --ff-only work/improve-cycle-NNN
git worktree remove ~/projects/vsm/workbench/improve-cycle-NNN
git branch -d work/improve-cycle-NNN
```

If fast-forward fails, the improvement conflicts with recent changes. Drop it (git worktree remove --force) and try next cycle.

## Step 5: Notify Owner

Write a summary to outbox:
```json
{
  "channel": "telegram",
  "chat_id": "(from .env TELEGRAM_CHAT_ID)",
  "text": "Improvement cycle NNN complete:\n- Consolidated: [summary]\n- Audited: [findings]\n- Improved: [what changed]\n- Next: [what to focus on]",
  "sent": false
}
```
