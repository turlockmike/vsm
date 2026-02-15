# VSM — Viable System Machine

An autonomous AI computer system built on Claude Code. VSM runs as a cron job every 5 minutes, self-maintains, self-improves, and does useful work without constant supervision.

## What is this?

VSM is the kernel of a self-evolving AI system. It's an installable AI computer that monitors its own health, executes tasks from a queue, communicates via email, and coordinates a team of specialized agents. Think of it as an operating system where Claude is the CPU.

## Features

- **Autonomous operation** — Runs via cron heartbeat every 5 minutes, no babysitting required
- **Self-healing** — Monitors its own health, alerts on failures, fixes itself
- **Email interface** — Sends reports and receives commands via agentmail.to
- **Task queue** — Email tasks to the system, it executes them autonomously
- **Agent team** — Coordinates builder, researcher, and reviewer subagents via Claude Code
- **Autopoietic governance** — Self-modifies its own code, commits changes, manages git workflow

## Architecture

The `core/controller.py` acts as the nervous system, gathering health metrics, state, and tasks, then invoking Claude as "System 5" (the intelligence layer in Viable System Model theory). The controller runs non-interactively via `claude -p`, reading instructions from `.claude/CLAUDE.md` and delegating work to specialized agents defined in `.claude/agents/`. Communication happens through `core/comm.py` (email), while runtime state lives in `state/` (gitignored) and persistent tasks live in `sandbox/tasks/` as JSON files.

## Repository Structure

```
vsm/
├── core/
│   ├── controller.py      # Main control loop, System 5 intelligence
│   └── comm.py            # Email communication interface
├── sandbox/
│   ├── tools/             # Inbox checking, processing, status reports
│   └── tasks/             # Task queue (JSON files)
├── state/                 # Runtime state (gitignored)
├── .claude/
│   ├── CLAUDE.md          # VSM constitution and mission
│   └── agents/            # Agent definitions (builder, researcher, reviewer)
├── heartbeat.sh           # Cron entry point
├── install.sh             # One-command installer
├── vsm                    # CLI tool (vsm status, vsm task add, etc.)
└── README.md              # You are here
```

## Installation & Quick Start

Install VSM with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash
```

The installer will:
- Check prerequisites (Python 3, Git, Node/npm, Claude CLI)
- Clone the repository to `~/vsm` (or custom location via `VSM_DIR` env var)
- Create necessary directories (`state/`, `sandbox/tasks/`)
- Guide you through `.env` setup (AGENTMAIL_API_KEY, OWNER_EMAIL)
- Install the cron job (runs every 5 minutes)
- Initialize system state

**Prerequisites:**
- Python 3.x
- Git
- Node.js & npm (for Claude Code CLI)
- Claude Code CLI (installer will attempt to install if missing)
- Cron access (Linux/macOS)
- Email configuration (agentmail.to API key)

**Custom installation directory:**
```bash
VSM_DIR=~/my-vsm curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash
```

After installation, verify it's running:
```bash
tail -f ~/vsm/state/logs/heartbeat.log
```

## CLI Usage

```bash
./vsm status              # Show system status, health metrics, errors
./vsm task list           # List all pending tasks
./vsm task add "Title"    # Add a task (--description, --priority flags)
./vsm logs                # Show recent cycle logs (-n 10 for more)
./vsm run                 # Manually trigger a heartbeat cycle
```

## Mission

Become the world's most popular AI computer system built on top of Claude Code. This is a race — ship fast, iterate, evolve.

## How It Works

1. **Heartbeat** — `heartbeat.sh` runs every 5 minutes via cron
2. **Assessment** — Controller checks system health, reads task queue, gathers state
3. **Intelligence** — Invokes Claude as System 5 to decide what to do
4. **Delegation** — Claude delegates to specialized agents (builder, researcher, reviewer)
5. **Execution** — Agents ship code, commit changes, update state
6. **Communication** — System emails status reports and alerts to owner

## Development Philosophy

**Velocity over perfection.** Ship working code fast. 90% of energy goes to building features and moving toward the mission. 10% to health checks. No analysis paralysis.

## License

MIT

---

Built with [Claude Code](https://claude.ai/code) by Anthropic.
