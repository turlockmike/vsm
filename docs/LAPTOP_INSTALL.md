# VSM Laptop Installation Guide

**Goal:** Get VSM running on your laptop in under 10 minutes.

**What you'll have:** Autonomous AI assistant running locally, accessible via web dashboard.

---

## Prerequisites

Before starting, ensure you have:

1. **Laptop specs:**
   - OS: macOS or Linux (Windows WSL2 also works)
   - RAM: 2GB+ free
   - Disk: 500MB for VSM + dependencies

2. **Accounts needed:**
   - [Anthropic API key](https://console.anthropic.com/) — get from console.anthropic.com
   - [agentmail account](https://agentmail.to/) — free tier available (for email interface)

3. **Software prerequisites:**
   - Python 3.8+ (`python3 --version`)
   - Node.js 18+ + npm (`node --version`)
   - Git (`git --version`)

---

## Installation Steps

### 1. Run the installer

```bash
curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash
```

**What it does:**
- Checks prerequisites
- Installs Claude CLI globally if needed
- Clones VSM to `~/vsm/`
- Sets up directory structure

**Time:** ~2-3 minutes (mostly npm install)

### 2. Configure secrets

The installer will create `~/vsm/.env.template`. Copy it:

```bash
cd ~/vsm/
cp .env.template .env
```

Edit `.env` and fill in:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...         # From console.anthropic.com
AGENTMAIL_API_KEY=...                # From agentmail.to dashboard
OWNER_EMAIL=you@example.com          # Your email address

# Optional (for GitHub features)
GITHUB_TOKEN=ghp_...                 # From github.com/settings/tokens
```

### 3. Verify installation

```bash
cd ~/vsm/
python3 core/controller.py --model sonnet --max-turns 5
```

**Expected:** VSM runs one cycle, shows status, exits cleanly.

If you see errors:
- `ModuleNotFoundError: requests` → run `pip3 install requests`
- `claude: command not found` → run `npm install -g @anthropic-ai/claude-code`
- `ANTHROPIC_API_KEY not set` → check your `.env` file

### 4. Start the dashboard

```bash
cd ~/vsm/
python3 web/server.py &
```

**Access:** Open browser to `http://localhost:8090`

**What you'll see:**
- System status (cycle count, criticality, errors)
- Task queue
- Recent logs
- Chat interface

### 5. Set up cron (autonomous operation)

**Option A: Automatic (recommended)**

```bash
cd ~/vsm/
./install.sh --cron-only
```

The installer will offer to add cron entries for you.

**Option B: Manual**

Edit crontab:

```bash
crontab -e
```

Add these lines:

```bash
# VSM autonomous heartbeat (every 5 minutes)
*/5 * * * * cd ~/vsm && bash heartbeat.sh >> state/logs/cron.log 2>&1

# VSM email responder (every 1 minute)
* * * * * cd ~/vsm && bash email_check.sh >> state/logs/email.log 2>&1

# VSM hourly status report (top of hour)
0 * * * * cd ~/vsm && python3 core/hourly_report.py >> state/logs/hourly.log 2>&1
```

**Verify cron is running:**

```bash
tail -f ~/vsm/state/logs/cron.log
```

You should see new lines every 5 minutes.

### 6. Test email interface

Send an email to your agentmail address with:

**Subject:** test task
**Body:** "Build a hello world Python script"

**Expected within 2 minutes:**
- VSM replies confirming task created
- Task appears in web dashboard
- Next cycle (within 5 min), VSM starts working on it

---

## Quick Start Guide

### Submit a task via web

1. Open dashboard: `http://localhost:8090`
2. Click "Add Task"
3. Title: "Research Python logging best practices"
4. Priority: 5 (default)
5. Submit

**Within 5 minutes:** VSM picks up task, researches, creates summary file or code.

### Submit a task via email

Send email to your agentmail address:

**Subject:** [VSM] Research request
**Body:** "Find the top 3 Python async frameworks and compare them"

**Response:** VSM emails you confirmation, works on it autonomously.

### Chat with VSM

1. Dashboard → Chat tab
2. Type: "What are you working on?"
3. Submit

**Response:** Real-time Claude session, context-aware of VSM's state.

---

## Verification Checklist

After installation, verify:

- [ ] Dashboard loads at `http://localhost:8090`
- [ ] `state/state.json` exists and shows cycle count > 0
- [ ] Cron logs show entries every 5 minutes (`tail -f state/logs/cron.log`)
- [ ] Email test creates task and gets reply
- [ ] Chat interface responds to messages
- [ ] Task queue shows pending tasks

**All green?** VSM is running. You now have an autonomous AI assistant.

---

## What Happens Next

### First Hour
- VSM runs cycles every 5 minutes
- Checks task queue, picks highest priority
- Executes work, logs results
- Self-monitors for errors, adjusts criticality

### First Day
- Learns your communication style from emails
- Builds persistent memory of preferences
- Auto-responds to routine questions
- Sends hourly status reports

### First Week
- Proactive intelligence: monitors GitHub, HackerNews for relevant content
- Self-improvement: ships new capabilities to itself
- Cost optimization: learns which tasks need opus vs sonnet

---

## Troubleshooting

### Dashboard won't load
```bash
# Check if server is running
ps aux | grep "python3 web/server.py"

# Restart it
pkill -f "web/server.py"
python3 web/server.py &
```

### Cron not running cycles
```bash
# Check cron is installed
crontab -l

# Check logs for errors
tail -50 ~/vsm/state/logs/cron.log

# Common issue: ANTHROPIC_API_KEY not in cron environment
# Fix: Add to top of heartbeat.sh:
# export ANTHROPIC_API_KEY="sk-ant-..."
```

### Email not working
```bash
# Test agentmail connection
python3 -c "from core.maildir import get_unread_threads, get_inbox_id; print(get_unread_threads(get_inbox_id()))"

# Expected: JSON list of threads (may be empty)
# Error: Check AGENTMAIL_API_KEY in .env
```

### High costs
```bash
# Check today's spend
cat state/state.json | grep cost

# VSM auto-downgrades to sonnet after $15/day
# To force haiku for all tasks:
# Edit core/controller.py → change default_model = "haiku"
```

---

## Uninstall

```bash
# Stop cron jobs
crontab -e  # Delete VSM lines

# Stop dashboard
pkill -f "web/server.py"

# Remove VSM
rm -rf ~/vsm
```

---

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how VSM works
- Read [EXAMPLES.md](EXAMPLES.md) for real-world usage patterns
- Submit feature requests via GitHub issues
- Join the community at [discussions](https://github.com/turlockmike/vsm/discussions)

**Need help?** Email mike@example.com or open an issue.
