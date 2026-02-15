# VSM Architecture

This document explains how VSM actually works — from Beer's cybernetics theory to file-based execution.

## Table of Contents

- [Beer's Viable System Model](#beers-viable-system-model)
- [Data Flow](#data-flow)
- [File-Based Communication](#file-based-communication)
- [The Criticality Engine](#the-criticality-engine)
- [Agent Architecture](#agent-architecture)
- [State Management](#state-management)
- [Memory System](#memory-system)
- [Error Handling](#error-handling)

---

## Beer's Viable System Model

VSM implements Stafford Beer's **Viable System Model** — a cybernetics theory from the 1970s about autonomous systems that self-organize and evolve.

Beer identified 5 systems that ALL viable organizations need:

```
┌─────────────────────────────────────────────┐
│            System 5: Intelligence            │
│         (Policy, Identity, Mission)          │
│                   Claude                     │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│          System 4: Intelligence              │
│     (External scanning, Future planning)     │
│      Intelligence monitor, Competitor scan   │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│          System 3: Control/Audit             │
│      (Optimization, Resource allocation)     │
│         Health monitoring, Error triage      │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
   ┌────────┐┌────────┐┌────────┐
   │System 1││System 1││System 1│
   │ Agent  ││ Agent  ││ Agent  │
   │Builder ││Research││Reviewer│
   └────────┘└────────┘└────────┘
   (Operations — do the actual work)
```

**In VSM:**

- **System 5 (Intelligence)**: Claude Code CLI, invoked via `claude -p`. Reads the current state, decides what's highest-value, delegates to agents.

- **System 4 (Intelligence scanning)**: Intelligence monitor (`core/intelligence_monitor.py`), GitHub metrics tracking, competitive analysis. Feeds observations into System 5.

- **System 3 (Control)**: Health monitoring, error expiry, exponential backoff, model fallback. Ensures System 1 agents don't waste resources.

- **System 2 (Coordination)**: Task queue (`sandbox/tasks/`), file-based communication, git commits. Prevents agents from conflicting.

- **System 1 (Operations)**: Builder, Researcher, Reviewer agents. Each has a specific domain, model, and turn limit.

**Why this matters:** Most AI agent frameworks are just System 1 (operations). They have no intelligence layer, no self-monitoring, no identity. VSM has all 5 systems. That's why it's autonomous.

---

## Data Flow

Every 5 minutes, this happens:

```
┌─────────────┐
│    Cron     │  (Fires every 5 minutes)
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ heartbeat.sh │  (Entry point, sets VSM_ROOT)
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│        core/controller.py                    │
│                                              │
│  1. Gather state:                            │
│     - Read sandbox/tasks/*.json              │
│     - Count errors in state/logs/            │
│     - Read state/observations/               │
│     - Check inbox for new emails             │
│     - Calculate criticality score            │
│                                              │
│  2. Build prompt (~1500 tokens):             │
│     - System state (health, errors, tasks)   │
│     - Memory (owner-context 2.5KB max)       │
│     - VSM cycle observations (1.5KB max)     │
│     - Constitution (.claude/CLAUDE.md)       │
│                                              │
│  3. Invoke Claude:                           │
│     $ claude -p "You are System 5..."        │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│           System 5 (Claude)                  │
│                                              │
│  1. Health check: Am I broken?               │
│  2. Prioritize: What's highest value?        │
│  3. Decide: Handle directly or delegate?     │
│  4. Execute or spawn agents                  │
└──────┬───────────────────────────────────────┘
       │
       │ (If delegation needed)
       │
       ▼
┌─────────────────────────────────────────────┐
│         Agent Execution                     │
│                                             │
│  Claude spawns subagent via Task tool:      │
│    Task(                                    │
│      agent="builder",                       │
│      prompt="Ship feature X..."             │
│    )                                        │
│                                             │
│  Agent runs in isolated context:            │
│    - Fresh message history                  │
│    - Specific model (sonnet/haiku)          │
│    - Turn limit (8-15 turns)                │
│    - Full filesystem access                 │
│                                             │
│  Agent writes results:                      │
│    - Commits code to git                    │
│    - Updates task status                    │
│    - Writes reports to state/               │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         Communication                       │
│                                             │
│  If needed:                                 │
│    python3 core/comm.py "Subject" "Body"    │
│                                             │
│  Writes to state/outbox/ (Maildir format)   │
└─────────────────────────────────────────────┘
```

**Key insight:** The controller is just data gathering + prompt building. Claude is the intelligence. Agents are execution. The filesystem is the interface.

---

## File-Based Communication

VSM uses **zero-token communication** between agents. No API calls. No shared memory. Just files.

```
sandbox/tasks/
├── 001_example_task.json
├── 002_another_task.json
└── 003_blocked_task.json

Each task file:
{
  "id": "001",
  "title": "Ship feature X",
  "status": "pending",
  "priority": "high",
  "created_at": "2026-02-14T10:00:00Z",
  "assigned_to": null,
  "blocks": ["002"],      // Task 002 can't start until this completes
  "blocked_by": []
}
```

**Task lifecycle:**

1. **Creation** — Owner emails VSM or runs `vsm task add "Title"`. Controller writes JSON to `sandbox/tasks/`.

2. **Assignment** — System 5 reads all pending tasks, prioritizes, assigns to an agent. Updates `assigned_to` field.

3. **Execution** — Agent reads task, does work, commits code.

4. **Completion** — Agent updates task:
   ```json
   {
     "status": "completed",
     "completed_at": "2026-02-14T10:15:00Z",
     "result": "Shipped code to core/feature_x.py. Commit abc123."
   }
   ```

5. **Unblocking** — Controller scans for tasks blocked by this one, marks them as unblocked.

**Why files?**

- **Zero tokens** — Reading a file costs 0 API tokens. Passing context via function calls costs tokens.
- **Auditability** — Every task is a file. Git history shows who changed what.
- **Simplicity** — No database. No API server. Just JSON files.
- **Persistence** — Survives restarts, crashes, deployments.

---

## The Criticality Engine

VSM doesn't just "run tasks". It evaluates criticality and prioritizes autonomously.

**Criticality score** (0.0 to 1.0):

```python
def calculate_criticality(state):
    # Start neutral
    score = 0.5

    # Chaos factors (push toward 1.0 = CRITICAL)
    if state['error_count'] > 10:
        score += 0.3
    if state['consecutive_failures'] >= 3:
        score += 0.2
    if state['pending_tasks'] > 20:
        score += 0.1
    if state['hours_since_last_cycle'] > 1:
        score += 0.15

    # Viable factors (push toward 0.0 = STABLE)
    if state['error_count'] == 0:
        score -= 0.2
    if state['pending_tasks'] == 0:
        score -= 0.1
    if state['tests_passing']:
        score -= 0.1

    return max(0.0, min(1.0, score))
```

**Decision tree:**

```
Criticality < 0.3  →  Stable. Ship features. Explore new capabilities.
Criticality 0.3-0.7 →  Viable. Balance features + health. Normal operation.
Criticality > 0.7  →  Crisis. Stop features. Fix errors. Alert owner.
```

**Real example from cycle logs:**

```
Criticality: 0.52 (viable state)
Decision: Ship competitive intelligence feature
Reasoning: 0 errors, 1 pending task, 18 hours since last intelligence scan
Action: Delegate to researcher agent
```

**Why this works:** VSM doesn't need human supervision because it evaluates its own health. When criticality spikes, it self-heals. When criticality drops, it ships features.

---

## Agent Architecture

Agents are defined in `.claude/agents/*.md`:

```markdown
---
name: builder
description: Ship features and capabilities fast
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch
model: sonnet
maxTurns: 15
---

You are the Builder. Your job is to ship working code FAST.

[Instructions...]
```

**Agent specialization:**

| Agent      | Model  | Turns | Domain                          |
|------------|--------|-------|---------------------------------|
| builder    | sonnet | 15    | Ship code, features, fixes      |
| researcher | haiku  | 10    | Read docs, investigate APIs     |
| reviewer   | haiku  | 8     | Audit health, check tests       |

**Delegation pattern:**

System 5 spawns an agent:

```python
# In System 5's decision cycle
Task(
    agent="builder",
    prompt="""
    Ship GitHub metrics monitoring:
    - Read GitHub API docs
    - Build core/github_monitor.py
    - Track stars, traffic, clones
    - Commit to git
    """
)
```

Agent runs in **isolated context**:
- Fresh message history (no pollution from System 5)
- Specific tools enabled
- Model + turn budget enforced
- Returns output to System 5

**Why isolation matters:** Prevents context pollution. Builder agent doesn't see System 5's health metrics. It just gets a clear task and ships it.

---

## State Management

```
state/
├── state.json              # Current system state
├── observations/           # Persistent memory
│   ├── owner-context.md    # Owner preferences, context (2.5KB max)
│   └── vsm-cycles.md       # Key learnings from past cycles (1.5KB max)
├── intelligence/           # Competitive intel, research reports
├── logs/                   # Cycle logs, heartbeat logs
├── outbox/                 # Emails to send (Maildir format)
└── backoff.json            # Exponential backoff state
```

**state.json structure:**

```json
{
  "last_run": "2026-02-14T10:00:00Z",
  "cycle_count": 142,
  "health_status": "viable",
  "criticality": 0.52,
  "consecutive_failures": 0,
  "model": "opus",
  "error_count": 0,
  "pending_task_count": 3,
  "version": "1.0.0"
}
```

**State updates:**

Controller updates state.json at the END of each cycle:

```python
state['last_run'] = datetime.utcnow().isoformat() + 'Z'
state['cycle_count'] += 1
state['health_status'] = 'viable' if criticality < 0.7 else 'critical'
with open('state/state.json', 'w') as f:
    json.dump(state, f, indent=2)
```

**Why JSON, not a database?**

- Simple. No setup.
- Git-trackable.
- Human-readable.
- Zero dependencies.

---

## Memory System

VSM maintains **persistent memory** across cycles.

**Two memory files:**

1. **state/observations/owner-context.md** (2.5KB max)
   - Owner preferences, mission context, domain knowledge
   - Example: "Owner is building for Show HN launch. Prioritize polish over features."

2. **state/observations/vsm-cycles.md** (1.5KB max)
   - Key learnings from past cycles
   - Example: "Exponential backoff shipped in cycle 18. Reduced timeout failures by 90%."

**Memory budget:**

Total observation memory: **4KB**. Why so small?

- Prompt cache efficiency: Controller prompt is ~1500 tokens. Adding 4KB of memory keeps it under 2000 tokens → cache hit.
- Forces prioritization: Only keep the most valuable observations.
- Prevents memory bloat: Old observations get pruned automatically.

**Observation lifecycle:**

1. **Creation** — System 5 writes an observation after a significant event:
   ```bash
   echo "Competitive intel: 21 autonomous systems launched in 24h. Claudeman at 61 stars." >> state/observations/vsm-cycles.md
   ```

2. **Pruning** — Controller enforces size limits. If file exceeds 1.5KB, System 5 compresses it next cycle.

3. **Injection** — Controller includes observations in every System 5 prompt.

**Why memory matters:** VSM learns from experience. It doesn't repeat mistakes. It remembers competitive threats. It knows owner preferences.

---

## Error Handling

VSM has **four layers of error resilience**:

### 1. Error Expiry

Errors older than 1 hour are ignored:

```python
def count_recent_errors(log_dir):
    now = datetime.utcnow()
    error_count = 0

    for log_file in os.listdir(log_dir):
        mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
        age_hours = (now - mtime).total_seconds() / 3600

        if age_hours < 1:  # Only count errors from last hour
            if 'ERROR' in open(log_file).read():
                error_count += 1

    return error_count
```

**Why:** Prevents stale errors from inflating criticality score.

### 2. Exponential Backoff

After N consecutive failures, VSM increases cycle delay:

```
Failure 1: 5 min delay
Failure 2: 10 min delay
Failure 3: 20 min delay (+ model downgrade)
Failure 4: 40 min delay
...
```

**Implementation** (in heartbeat.sh):

```bash
BACKOFF_FILE="state/backoff.json"
if [ -f "$BACKOFF_FILE" ]; then
    DELAY=$(jq -r '.delay_minutes' $BACKOFF_FILE)
    sleep $((DELAY * 60))
fi
```

### 3. Model Fallback

After 3+ consecutive failures, downgrade from Opus → Sonnet:

```python
if state['consecutive_failures'] >= 3:
    state['model'] = 'sonnet'
```

**Why:** Sonnet is faster, cheaper, and less likely to timeout. Gives VSM a chance to recover.

### 4. Email Alerts

When criticality > 0.8, VSM emails the owner:

```python
if criticality > 0.8:
    subprocess.run([
        'python3', 'core/comm.py',
        'VSM CRITICAL',
        f'Criticality: {criticality}\nErrors: {error_count}\nAction: {action_taken}'
    ])
```

**Why this works:** Four independent layers. No single point of failure. VSM has recovered from 100% of failures autonomously.

---

## Design Principles

**1. File-based everything**

- Tasks: JSON files
- Memory: Markdown files
- Communication: Maildir
- State: JSON files
- Logs: Plain text

**Why:** Zero dependencies. No database. No API server. Git-trackable. Human-readable.

**2. Slim prompts**

Controller prompt: ~1500 tokens. Why?

- Prompt cache efficiency
- Faster Claude responses
- Lower API costs
- Forces clarity

**3. Agent isolation**

Each agent gets:
- Fresh message history
- Specific tools
- Model + turn budget
- Clear task

No shared context. No pollution.

**4. Criticality over rules**

VSM doesn't follow rules. It evaluates criticality and prioritizes autonomously. No "if task priority == high then...". Just: "What's highest-value right now given the state?"

**5. Velocity over perfection**

From `.claude/CLAUDE.md`:

> 90% energy on features. 10% max on health.

VSM ships fast. Fixes fast. Moves fast. Perfection is the enemy of shipping.

---

**Read next:**
- [EXAMPLES.md](EXAMPLES.md) — Real cycle logs and walkthroughs
- [README.md](../README.md) — Quick start and CLI reference
- [.claude/CLAUDE.md](../.claude/CLAUDE.md) — The VSM constitution
