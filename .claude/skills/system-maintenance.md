---
name: system-maintenance
description: Diagnose and fix VSM system issues. Use when the system is broken, unhealthy, or needs repair.
---

# System Maintenance Skill

## Quick Health Check
```bash
# Is controller syntactically valid?
python3 -c "import py_compile; py_compile.compile('core/controller.py', doraise=True)"

# Is state.json valid?
python3 -c "import json; json.load(open('state/state.json')); print('OK')"

# Is cron installed?
crontab -l | grep vsm

# Is web dashboard running?
curl -s http://localhost:80/api/state | python3 -c "import sys,json; json.load(sys.stdin); print('OK')"
```

## Common Failure Modes

### Timeout cascade
- Symptom: consecutive timeout errors in state.json
- Cause: large prompt, slow model, or API overload
- Fix: check prompt size, reduce context, controller has backoff built in

### State corruption
- Symptom: controller crashes on load_state()
- Fix: `echo '{}' > state/state.json` for clean reset, controller fills defaults

### Cron missing
- Fix: `(crontab -l 2>/dev/null; echo "*/5 * * * * cd ~/projects/vsm/main && python3 core/controller.py >> state/logs/heartbeat.log 2>&1") | crontab -`

### Email not sending
- Check: `ls outbox/` for queued emails
- Check: `.env` has AGENTMAIL_API_KEY and OWNER_EMAIL set

## File Locations
- Controller: `core/controller.py`
- State: `state/state.json`
- Logs: `state/logs/`
- Tasks: `sandbox/tasks/`
- Email inbox: `inbox/`
- Email outbox: `outbox/`
- Web dashboard: `web/server.py`, `web/index.html`
