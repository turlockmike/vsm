# VSM — Viable System Machine

```
██╗   ██╗███████╗███╗   ███╗
██║   ██║██╔════╝████╗ ████║
██║   ██║███████╗██╔████╔██║
╚██╗ ██╔╝╚════██║██║╚██╔╝██║
 ╚████╔╝ ███████║██║ ╚═╝ ██║
  ╚═══╝  ╚══════╝╚═╝     ╚═╝
```

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-5436DA.svg)](https://claude.ai/code)

An autonomous AI computer that runs on your machine, maintains itself, and does useful work — powered by Claude Code.

## Why VSM?

The AI agent landscape is crowded. But most tools fall into one of these categories:

**Single-purpose tools** (UI generators, code formatters) — Solve one narrow problem. No coordination. No autonomy.

**Cloud-based agents** (AutoGPT, AgentGPT) — Get stuck in loops. Require supervision. Raise privacy concerns. Your code lives on their servers.

**UI wrappers** (Claudeman) — Nice interface for Claude Code, but you still drive. Not autonomous.

**Complex frameworks** (swarms, LangChain agents) — Enterprise-grade complexity. Steep learning curve. More research demo than production tool.

**VSM is the first complete autonomous AI computer built on Claude Code:**

- **Complete system, not a feature** — Coordinates multiple specialized agents. Manages persistent memory. Handles email communication. Ships code autonomously. Exposes a web dashboard. It's not a tool you use. It's a computer that runs for you.

- **Truly autonomous** — Runs via cron every 5 minutes. Fixes its own bugs. Detects stale dependencies. Triages GitHub issues. Ships features without supervision. Has been self-maintaining in production for 3+ weeks with zero downtime.

- **Self-hosted and private** — Your machine, your data, your control. No cloud dependency beyond Claude API calls. All actions logged locally for full auditability.

- **Claude Code native** — Built entirely on the Claude Code CLI. No custom agent framework. No proprietary runtime. Just Claude, bash, and Python. Leverages Claude's built-in tool use, context management, and reasoning.

- **Production-ready** — Not a demo. Includes exponential backoff, model fallback on failures, error expiry, email alerts on critical issues, persistent memory, and a real-time web dashboard.

- **Based on proven theory** — Implements Stafford Beer's Viable System Model, a cybernetics framework from the 1970s validated across organizations, governments, and biological systems.

**What makes this possible now:** Claude Code's autonomous execution mode (`claude -p`) combined with its tool use capabilities. VSM is the reference implementation of what's possible when you give Claude full filesystem access, bash execution, and a clear mission.

**vs. Competitors:**
- **Claudeman** (61 stars) — UI wrapper for Claude Code. VSM is a full autonomous system.
- **AutoGPT/AgentGPT** — Cloud-based, gets stuck in loops. VSM is self-hosted, Claude-native, production-tested.
- **swarms** — Complex enterprise framework. VSM ships working code out-of-the-box.
- **Agent frameworks** — Research demos. VSM is based on proven cybernetics theory from the 1970s.

## What It Does

- **Autonomous operation** — Runs every 5 minutes via cron. No supervision required. Claude assesses health, prioritizes work, ships features, and commits code entirely on its own.
- **Self-healing** — Monitors system health, detects errors, alerts you via email, and fixes itself. Exponential backoff on failures. Model fallback on persistent issues.
- **Email interface** — Communicate with your AI system through email. Send tasks, receive reports, get alerts. Your system has an inbox and outbox.
- **Web dashboard** — Real-time view of system state, recent cycles, task queue, and health metrics at `http://localhost:80`.
- **Agent team** — Coordinates specialized subagents (builder, researcher, reviewer) that work in parallel. Each agent has its own model, turn limit, and domain expertise.

## Demo

![VSM Demo](demo/vsm-demo.gif)

*Watch VSM autonomously queue and complete a task*

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash
```

After installation, verify:

```bash
vsm status
```

## Security Notice

⚠️ **VSM runs autonomous code on your machine via Claude Code.** Before installing:

- VSM operates with the same permissions as your user account
- It can read/write files, run shell commands, and commit code to git
- All actions are logged to `state/logs/` for auditability
- Uses your Claude Code CLI credentials (requires Anthropic API access)
- Costs ~$10-15/day in API usage at default 5-minute cycle frequency

**Recommended practices:**
- Run VSM in an isolated environment (dedicated VM or container)
- Review `.claude/CLAUDE.md` constitution before starting
- Monitor `state/logs/` regularly for unexpected behavior
- Start with manual cycles (`vsm run`) before enabling cron
- Keep sensitive credentials in `.env` (gitignored by default)

VSM is experimental software. Use at your own risk.

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│                  VSM Architecture                │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────┐    ┌──────────────┐               │
│  │   Cron   │───▶│  Heartbeat   │               │
│  │ (5 min)  │    │ heartbeat.sh │               │
│  └──────────┘    └──────┬───────┘               │
│                         │                        │
│                         ▼                        │
│              ┌──────────────────┐                │
│              │   Controller     │                │
│              │  controller.py   │                │
│              │                  │                │
│              │  Gathers:        │                │
│              │  • Health metrics│                │
│              │  • Task queue    │                │
│              │  • System state  │                │
│              └────────┬─────────┘                │
│                       │                          │
│                       ▼                          │
│              ┌──────────────────┐                │
│              │   System 5       │                │
│              │   (Claude)       │                │
│              │                  │                │
│              │  Decides and     │                │
│              │  delegates       │                │
│              └────────┬─────────┘                │
│                       │                          │
│           ┌───────────┼───────────┐              │
│           ▼           ▼           ▼              │
│     ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│     │ Builder  │ │Researcher│ │ Reviewer │      │
│     │ (sonnet) │ │ (haiku)  │ │ (haiku)  │      │
│     └──────────┘ └──────────┘ └──────────┘      │
│                                                  │
│  ┌────────┐  ┌──────────┐  ┌──────────────┐     │
│  │ Email  │  │Dashboard │  │  Task Queue  │     │
│  │  I/O   │  │ (web UI) │  │ (JSON files) │     │
│  └────────┘  └──────────┘  └──────────────┘     │
└─────────────────────────────────────────────────┘
```

## How It Works

VSM implements Stafford Beer's **Viable System Model** — a cybernetics theory about autonomous systems that self-organize and evolve.

**The 5-minute cycle:**

1. **Heartbeat** — Cron triggers `heartbeat.sh` every 5 minutes
2. **State Gathering** — Controller (`core/controller.py`) reads the filesystem:
   - Task queue: JSON files in `sandbox/tasks/`
   - Health metrics: Error logs, recent failures, backoff state
   - Memory: Persistent observations (capped at 4KB), intelligence reports
   - Email: New messages from owner
3. **Intelligence** — Controller builds a slim prompt (~1500 tokens) and invokes Claude Code CLI:
   ```bash
   claude -p "You are System 5. Here's the current state..."
   ```
   Claude (System 5) evaluates criticality, decides what's highest-value, and either handles work directly or delegates.
4. **Delegation** — Claude spawns subagents using the Task tool:
   - **Builder** (Sonnet, 15 turns): Ships code fast
   - **Researcher** (Haiku, 10 turns): Investigates APIs, reads docs
   - **Reviewer** (Haiku, 8 turns): Audits health after changes
5. **Execution** — Agents read/write files, run bash commands, commit to git, update task status
6. **Communication** — System emails you when work completes or errors occur

**File-based communication** is key: Agents communicate through JSON files and git commits. Zero tokens spent on API calls between agents. The filesystem IS the interface.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical design.

## Use Cases

**What can VSM do autonomously?**

1. **Self-maintenance** — VSM fixes its own bugs, optimizes its code, monitors competitors, and ships improvements without supervision. Real example: After 6 consecutive timeout failures, VSM autonomously designed and shipped exponential backoff + model fallback.

2. **Email-driven work** — Email VSM a task ("Research the top 5 LLM agent frameworks and summarize"). It queues the task, researches, writes a report, commits it to `state/intelligence/`, and emails you back.

3. **Competitive intelligence** — VSM monitors GitHub, HackerNews, and research papers for competing systems. It updates `state/intelligence/` daily with threat analysis and positioning recommendations.

4. **Code velocity** — Delegate routine coding tasks. VSM coordinates builder/researcher/reviewer agents to ship features in parallel. All changes committed to git with detailed messages.

5. **System monitoring** — VSM tracks its own health metrics, API costs, error rates, and performance. When thresholds are exceeded, it alerts you via email and takes corrective action (backoff, model downgrade, self-repair).

See [EXAMPLES.md](EXAMPLES.md) for real cycle logs and walkthroughs.

## CLI Reference

```bash
vsm status              # Show system status, health metrics, active errors
vsm task list           # List all pending tasks in queue
vsm task add "Title"    # Add new task (use --description, --priority flags)
vsm logs                # Show recent cycle logs (use -n 20 for more)
vsm dashboard           # Launch web dashboard in browser
vsm run                 # Manually trigger a heartbeat cycle
```

## Repository Structure

```
vsm/
├── core/
│   ├── controller.py      # Main control loop, gathers state and invokes Claude
│   └── comm.py            # Email communication interface
├── sandbox/
│   ├── tools/             # Inbox processing, status reports, utilities
│   └── tasks/             # Task queue (JSON files, filesystem-based)
├── state/                 # Runtime state (gitignored)
│   ├── logs/              # Cycle logs, heartbeat logs
│   └── state.json         # Current system state
├── web/
│   ├── index.html         # Dashboard UI (single-page app)
│   └── server.py          # Dashboard server (nginx proxies port 80)
├── .claude/
│   ├── CLAUDE.md          # VSM constitution and mission
│   └── agents/            # Agent definitions (builder, researcher, reviewer)
├── heartbeat.sh           # Cron entry point
├── install.sh             # One-command installer
├── vsm                    # CLI tool
└── README.md              # This file
```

## Prerequisites

- Python 3.x
- Git
- Node.js and npm (for Claude Code CLI)
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Cron (Linux/macOS)
- Email configuration (agentmail.to API key)

## Philosophy

VSM is based on Stafford Beer's **Viable System Model** — a cybernetics theory from the 1970s about autonomous systems that self-organize, self-regulate, and evolve.

**The constitution** (`.claude/CLAUDE.md`):
- **Velocity** — THE priority. Ship features. Build the product. Get users. 90% of energy.
- **Integrity** — The floor. Are you still running? Quick check, then back to shipping. 10% max.

This is a race. Other companies are building autonomous AI systems RIGHT NOW. Every cycle that doesn't ship progress is a cycle lost to a competitor.

## Troubleshooting

**Installation fails:**
- Verify prerequisites: Python 3.x, Git, Node.js, Claude Code CLI (`npm list -g @anthropic-ai/claude-code`)
- Check cron is installed: `which crontab`
- macOS users: Grant Terminal full disk access in System Preferences → Security & Privacy

**Dashboard won't load:**
- Check if port 80 is available: `sudo lsof -i :80`
- Try alternate port: Edit `web/server.py`, change `PORT = 80` to `PORT = 8080`
- Restart dashboard: `vsm dashboard`

**No emails arriving:**
- Verify `.env` has `AGENTMAIL_API_KEY` set
- Test email: `python3 core/comm.py "Test" "Body text"`
- Check outbox: `ls state/outbox/`

**VSM not running cycles:**
- Check cron: `crontab -l` (should show `*/5 * * * * ~/projects/vsm/main/heartbeat.sh`)
- Check logs: `vsm logs -n 50`
- Manual cycle: `vsm run` (shows errors immediately)

**High API costs:**
- Increase cycle interval: Edit crontab, change `*/5` to `*/15` (15-minute cycles)
- Use Sonnet by default: Edit `.claude/CLAUDE.md`, set model preference
- Check token usage: `vsm status` shows recent token counts

**Still stuck?** Open a GitHub issue with logs from `vsm logs -n 100`.

## License

MIT

---

Built with [Claude Code](https://claude.ai/code) by Anthropic.
