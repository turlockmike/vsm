---
name: shipping
description: Ship code changes safely. Use when building features, fixing bugs, or making any code changes.
---

# Shipping Skill

## The Shipping Protocol
1. Understand the current code (Read before Edit)
2. Make the minimal change that works
3. Test it (syntax check, quick validation)
4. Commit with a clear message
5. Log what was shipped

## Git Workflow
```bash
# Stage specific files (never git add -A blindly)
git add core/controller.py web/index.html

# Commit with descriptive message
git commit -m "Add feature X: brief description of what and why"

# Never force-push, never amend published commits
```

## Testing Checklist
- Python syntax: `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"`
- JSON validity: `python3 -c "import json; json.load(open('file.json'))"`
- Controller still works: `python3 -c "from core.controller import load_state, check_health; print('OK')"`
- Web server imports: `python3 -c "from web.server import VSMHandler; print('OK')"`

## What NOT to Do
- Don't over-engineer. Minimal viable change.
- Don't add features nobody asked for.
- Don't refactor code you're not changing.
- Don't add comments/docs unless the logic is non-obvious.
- Don't break the controller — it's the heartbeat.

## Logging Changes
After committing, log to `state/logs/`:
```python
log = {
    "timestamp": "ISO-8601",
    "mode": "autonomous|beta|cycle",
    "reason": "What task prompted this",
    "success": True,
    "summary": "What was shipped in 1-2 sentences"
}
```
