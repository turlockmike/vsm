# VSM Architecture

## Overview

VSM implements **Stafford Beer's Viable System Model** — a cybernetics theory about autonomous systems that self-organize, self-regulate, and adapt to their environment.

Beer's model maps five interconnected systems:

- **System 5** (Intelligence) — Strategic thinking, policy, identity
- **System 4** (Planning) — Environmental scanning, future modeling
- **System 3** (Operations) — Resource allocation, optimization, auditing
- **System 2** (Coordination) — Conflict resolution, scheduling
- **System 1** (Execution) — Operational units doing the work

In VSM:
- **System 5** = Claude (invoked by controller) — Evaluates criticality, makes strategic decisions
- **System 4** = Intelligence monitoring (`state/intelligence/`) — Scans competitors, research, environment
- **System 3** = Controller (`core/controller.py`) — Gathers state, manages resources, tracks health
- **System 2** = Task queue (`sandbox/tasks/*.json`) — Coordinates work, handles dependencies
- **System 1** = Subagents (builder, researcher, reviewer) — Execute tasks, ship code

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      The VSM Cycle (every 5min)                  │
└─────────────────────────────────────────────────────────────────┘

1. TRIGGER
   cron → heartbeat.sh → core/controller.py

2. STATE GATHERING (System 3)
   Controller reads filesystem:

   ├─ sandbox/tasks/*.json          # Task queue (pending, blocked, done)
   ├─ state/state.json               # Current system state (errors, backoff)
   ├─ state/logs/heartbeat.log       # Recent cycle history
   ├─ state/memory/                  # Persistent observations (4KB cap)
   ├─ state/intelligence/            # Competitive scans, research
   ├─ inbox/                         # New emails from owner
   └─ .git/                          # Recent commits (what changed?)

3. PROMPT CONSTRUCTION
   Controller builds slim prompt (~1500 tokens):

   - Constitution (.claude/CLAUDE.md)
   - Current state summary
   - Task queue (filtered: no blocked tasks)
   - Health metrics (errors, backoff, token usage)
   - Recent observations (capped at 4KB)
   - Owner emails (if any)

4. INVOCATION (System 5)
   ```bash
   claude -p "You are System 5. Here's the state..." \
          --agent-file .claude/CLAUDE.md
   ```

   Claude receives prompt, decides:
   - Am I broken? (Integrity check)
   - What's highest-value? (Velocity prioritization)
   - Delegate or handle directly?

5. DELEGATION (System 1)
   Claude spawns subagents via Task tool:

   Agent: builder (sonnet, 15 turns)
   └─ Task: "Ship feature X"
   └─ Context: Isolated (no parent pollution)
   └─ Tools: Read, Write, Edit, Bash, Grep, Glob
   └─ Output: Commits code, updates task JSON

   Agent: researcher (haiku, 10 turns)
   └─ Task: "Investigate API Y"
   └─ Tools: WebFetch, WebSearch, Read
   └─ Output: Research doc in state/intelligence/

   Agent: reviewer (haiku, 8 turns)
   └─ Task: "Audit recent changes"
   └─ Tools: Read, Bash (git diff), Grep
   └─ Output: Health report

6. EXECUTION
   Agents read/write files:
   - Code changes → git commits
   - Task updates → sandbox/tasks/*.json
   - Reports → state/intelligence/
   - Observations → state/memory/

   All changes committed with structured messages:
   ```
   Ship task 015: Add observation memory

   Added cross-cycle persistent memory...

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
   ```

7. STATE UPDATE
   Controller updates state/state.json:
   - Last cycle timestamp
   - Token usage (estimate from response)
   - Errors (with expiry timestamp)
   - Consecutive failures (for backoff)

8. COMMUNICATION
   Email sent via core/comm.py:
   - Task completion reports
   - Error alerts
   - Weekly status summaries

   Maildir pattern:
   - Outgoing: Write to state/outbox/
   - Agentmail API: Sends email
```

## File-Based Communication Pattern

**Why files, not APIs?**

1. **Zero tokens** — Reading a JSON file costs zero API tokens. Passing data via function calls or prompts costs tokens.
2. **Persistence** — Files survive crashes. API calls don't.
3. **Auditability** — Git tracks every change. You can `git log` to see exactly what happened.
4. **Simplicity** — The filesystem IS the interface. No custom protocols, no RPC, no message queues.

**Task queue design:**

Each task is a JSON file: `sandbox/tasks/001_task_title.json`

```json
{
  "id": "001",
  "title": "Ship feature X",
  "description": "...",
  "priority": 8,
  "status": "pending",
  "created_at": "2026-02-14T12:00:00Z",
  "blocks": ["002"],
  "blocked_by": [],
  "tags": ["feature", "high-priority"]
}
```

**State changes:**
- Agent starts task: `status: "pending" → "in_progress"`
- Agent completes: `status: "in_progress" → "done"`
- Task unblocks others: System scans `blocked_by`, updates dependent tasks

**Memory design:**

Observations stored in `state/memory/`:
- `index.md` — Microcompact summaries (1.5KB cap)
- `projects.md` — Active projects and context
- `preferences.md` — Owner preferences learned over time
- `decisions.md` — Strategic decisions and rationale

Old observations auto-compress when memory hits cap.

## The Criticality Engine

**Core algorithm:**

```python
def decide_priority():
    # Integrity check (10% energy)
    if system_broken():
        return CRITICAL_FIX

    # Velocity prioritization (90% energy)
    tasks = load_tasks()

    # Filter blocked tasks (don't show unactionable work)
    actionable = [t for t in tasks if not t.blocked_by]

    # Sort by priority (owner can set 1-10)
    actionable.sort(key=lambda t: t.priority, reverse=True)

    # Check for owner emails (always high priority)
    if has_owner_email():
        return PROCESS_EMAIL

    # Pick highest-value task
    return actionable[0] if actionable else SCAN_ENVIRONMENT
```

**Backoff logic:**

```python
def should_run_cycle():
    failures = count_recent_failures(window_minutes=60)

    if failures == 0:
        return True  # Normal operation

    # Exponential backoff
    cooldown_minutes = failures * 5
    if time_since_last_attempt() < cooldown_minutes:
        return False  # Still cooling down

    # Model degradation
    if failures >= 3:
        use_model = "sonnet"  # Downgrade from opus
        timeout = 540  # 9 minutes instead of 5

    return True
```

**Error expiry:**

Errors older than 1 hour auto-prune from state. Prevents stale errors from inflating failure counts.

## Resilience Features

1. **Exponential backoff** — After N failures, wait N×5 minutes before retry
2. **Model fallback** — Opus → Sonnet after 3+ consecutive failures
3. **Timeout scaling** — Increase timeout (300s → 540s) in recovery mode
4. **Error expiry** — Prune errors older than 1 hour
5. **PID locking** — Prevent overlapping cycles (heartbeat.sh checks for running process)
6. **Git safety** — All changes committed, easy to revert (`git revert HEAD`)
7. **Owner alerts** — Email sent on critical errors
8. **Token budgeting** — Track costs, alert when thresholds exceeded

## Performance Optimizations

**Prompt compression:**

Original controller prompt: ~5000 tokens
Optimized controller prompt: ~1500 tokens

How:
- Microcompact old observations (summaries instead of full text)
- Cap memory at 4KB total (2.5KB owner-context + 1.5KB vsm-cycles)
- Filter blocked tasks from prompt (no point showing unactionable work)
- Slim state summary (counts instead of full lists)

**Context caching:**

Claude Code caches prompts automatically. By keeping `.claude/CLAUDE.md` stable and only changing the dynamic state portion, cache hit rate stays high.

**Subagent isolation:**

Each subagent gets fresh context (no parent pollution). Only task description + agent config passed. Prevents context window bloat.

## Security Model

**Threat surface:**

1. **Code execution** — Claude can run arbitrary bash commands
2. **File access** — Claude can read/write any file in working directory
3. **Git commits** — Claude can commit and push code
4. **Email** — Claude can send emails from your address (via agentmail.to)
5. **API costs** — Runaway cycles can drain your Anthropic account

**Mitigations:**

1. **Sandboxing** — Agents primarily work in `sandbox/` directory
2. **Git auditability** — Every change tracked, easy to revert
3. **Review agent** — Post-change audits by specialized agent
4. **Owner oversight** — Email alerts, dashboard shows all activity
5. **Constitutional constraints** — `.claude/CLAUDE.md` defines rules
6. **Backoff + budgeting** — Prevents runaway costs
7. **No remote push by default** — Commits stay local unless owner enables

**Recommendations:**

- Run in isolated VM or container
- Review `.claude/CLAUDE.md` before starting
- Monitor `state/logs/` regularly
- Start with manual cycles (`vsm run`) before enabling cron
- Keep secrets in `.env` (gitignored)

## Extending VSM

**Add a new agent:**

1. Create `.claude/agents/your-agent.md`:
   ```markdown
   # Your Agent

   You are a specialist in domain X.

   Your mission: Solve Y.

   Tools: Read, Write, Bash
   Turns: 10
   Model: haiku
   ```

2. Update `.claude/CLAUDE.md` to reference new agent

3. System 5 can now delegate: `Task(agent="your-agent", ...)`

**Add a new skill:**

1. Create `.claude/skills/your-skill.md` with domain expertise
2. Controller injects skills on-demand (context preservation via caching)

**Add a new communication channel:**

1. Create reader: `sandbox/tools/read_slack.py`
2. Create writer: `sandbox/tools/send_slack.py`
3. Wire into controller prompt

VSM's architecture is designed for evolution. The system can modify itself, add agents, create skills, and optimize its own code.

## Technical Stack

- **Runtime**: Claude Code CLI (`claude -p`)
- **Controller**: Python 3.x (`core/controller.py`)
- **Scheduler**: Cron (Linux/macOS)
- **Task queue**: JSON files (filesystem-based)
- **Memory**: Markdown files + JSON state
- **Communication**: Agentmail.to API (email), HTTP (dashboard)
- **Dashboard**: Python HTTP server + vanilla JS/HTML
- **Version control**: Git (all changes committed)

## Performance Characteristics

**Typical cycle times:**
- Health check only: 5-10 seconds
- Simple task: 30-60 seconds
- Complex task with delegation: 2-5 minutes

**Token usage (per cycle):**
- Health check: ~1500 input, ~200 output
- Task with delegation: ~2000 input, ~500 output
- Heavy research: ~3000 input, ~1500 output

**Costs (at 5-minute intervals):**
- Active development: ~$2-3/day
- Steady-state: ~$0.50/day
- Heavy load: ~$5-10/day

## Further Reading

- [Beer's Viable System Model](https://en.wikipedia.org/wiki/Viable_System_Model) — Original cybernetics theory
- [EXAMPLES.md](EXAMPLES.md) — Real cycle logs and walkthroughs
- [.claude/CLAUDE.md](.claude/CLAUDE.md) — VSM constitution and mission
