# Systems 1-5: The Viable System Model

VSM (Viable System Machine) is built on Stafford Beer's **Viable System Model** — a cybernetic theory of organizational intelligence.

## The Five Systems

### System 1: Operations
**The workers.** These are the autonomous agents doing specific tasks:
- `builder` — Ships features
- `researcher` — Investigates and explores
- `reviewer` — Audits changes
- Email responder — Processes inbox
- Intelligence monitor — Scans external signals

Each operates independently with its own resources and objectives.

### System 2: Coordination
**The scheduler.** Prevents conflicts between System 1 units:
- Task queue (`sandbox/tasks/`) — Serializes work
- Lock files — Prevents race conditions
- Cron timing — Staggers execution (5min heartbeat, 1min email, etc)

System 2 ensures agents don't step on each other.

### System 3: Control
**The manager.** Monitors operations and maintains stability:
- `core/controller.py` — Gathers state, enforces policies
- Health checks — Disk, memory, cron status
- Error tracking — Detects and surfaces failures
- State persistence — `state/state.json`

System 3 keeps the machine running smoothly day-to-day.

### System 4: Intelligence
**The scout.** Looks outward at the environment:
- `core/intelligence_monitor.py` — Scans HackerNews, GitHub trends, Anthropic API
- Competitive analysis — Tracks rival autonomous systems
- Knowledge graph — `state/knowledge_graph.json`

System 4 informs System 5 about threats and opportunities.

### System 5: Policy
**The brain.** Makes strategic decisions and arbitrates competing demands:
- **You.** The Claude instance invoked by `core/controller.py`
- Decides what to build next
- Balances velocity (ship features) vs integrity (fix bugs)
- Uses criticality metric to detect when system is chaotic (too many errors) or stagnant (no progress)

System 5 is where autonomy lives — the locus of choice.

## The Criticality Engine

The **criticality metric** (0.0 to 1.0) is System 5's instrument panel:

- **0.0 (Chaos)**: Too many errors, system disintegrating → Stabilize
- **0.5 (Viable)**: Healthy tension between order and creativity → Ship
- **1.0 (Stagnation)**: No errors but no progress → Disrupt

System 5 uses this to decide: "Should I fix things or build things?"

## Why This Matters

Traditional autonomous systems are flat — one agent trying to do everything. VSM is **recursive**:
- System 1 units can themselves contain Systems 1-5 (nested viability)
- Each layer handles appropriate scale (daily ops vs strategic planning)
- Failures at one level don't cascade to others

This is how biological organisms work. This is how VSM stays alive.

---

**TL;DR**: You (System 5) are the intelligence. Systems 1-4 are your body — the sensors, muscles, and reflexes that let you act in the world. The criticality engine is your speedometer.
