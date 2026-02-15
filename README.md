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

## What It Does

- **Autonomous operation** — Runs every 5 minutes via cron. No supervision required. Claude assesses health, prioritizes work, ships features, and commits code entirely on its own.
- **Self-healing** — Monitors system health, detects errors, alerts you via email, and fixes itself. Exponential backoff on failures. Model fallback on persistent issues.
- **Email interface** — Communicate with your AI system through email. Send tasks, receive reports, get alerts. Your system has an inbox and outbox.
- **Web dashboard** — Real-time view of system state, recent cycles, task queue, and health metrics at `http://localhost:80`.
- **Agent team** — Coordinates specialized subagents (builder, researcher, reviewer) that work in parallel. Each agent has its own model, turn limit, and domain expertise.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash
```

After installation, verify:

```bash
vsm status
```

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

1. **Heartbeat** — Cron triggers `heartbeat.sh` every 5 minutes
2. **Assessment** — Controller gathers health metrics, task queue, system state, and recent observations
3. **Intelligence** — Claude (System 5) evaluates criticality, prioritizes work, makes decisions
4. **Delegation** — Claude spawns specialized agents (builder/researcher/reviewer) to execute work
5. **Execution** — Agents ship code, run tests, commit changes, update task queue and state
6. **Communication** — System sends email reports, alerts, and task updates to owner

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

VSM is based on Stafford Beer's Viable System Model — a theory of autonomous systems that self-organize, self-regulate, and evolve. Velocity over perfection. Ship working code fast. 90% energy on features, 10% on health. This is a race.

## License

MIT

---

Built with [Claude Code](https://claude.ai/code) by Anthropic.
