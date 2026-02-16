# Learning Architecture for VSM Recursive Self-Improvement

## Diagnosis: Why 47 Cycles Produced Zero Learning

The current system has **execution memory** but no **learning memory**. Here's what happens:

```
Cycle N:
  1. Load state.json, health, tasks, recent logs, observations
  2. Build prompt with all context
  3. Claude decides, delegates, executes
  4. Log output to state/logs/
  5. Append observation (raw event text) to observations.md
  6. Increment cycle_count, save state
  -> Sleep 5 minutes
  -> Repeat identical process

Cycle N+1:
  - Sees last 3 log summaries (500 chars each)
  - Sees tail of observations.md (raw events)
  - Has NO structured knowledge of what works, what fails, what to try differently
  - Makes decisions from scratch, using the same heuristics as Cycle 1
```

The observations file is an **append-only event stream**. `decisions.md` has 76 lines of static architectural notes written once. `preferences.md` is empty after 47 cycles. The system journals but does not learn.

**The core gap**: There is no mechanism that transforms **experiences** into **capabilities**, no feedback loop where the outcome of cycle N changes the behavior of cycle N+1 beyond raw log context.

---

## Architecture Overview

The learning system adds three components to the existing cycle:

```
BEFORE (execution only):
  sense -> decide -> act -> log -> sleep

AFTER (execution + learning):
  sense -> decide -> act -> log -> REFLECT -> CONSOLIDATE -> sleep
                                     |              |
                                     v              v
                              experience_log   capability_registry
                                                     |
                                                     v
                                              next cycle's prompt
```

The two new phases are:

1. **Reflect** (end of every cycle): Extract structured lessons from what just happened
2. **Consolidate** (every 10 cycles): Compress experiences into capabilities, prune stale knowledge

---

## 1. Capability Model

### Schema: `state/capabilities.json`

```json
{
  "version": 1,
  "capabilities": {
    "git-commit-and-push": {
      "description": "Commit changes to git and push to remote",
      "confidence": 0.95,
      "times_used": 34,
      "times_succeeded": 33,
      "times_failed": 1,
      "last_used": "2026-02-15T16:50:00Z",
      "first_learned": "2026-02-14T16:06:00Z",
      "tags": ["git", "infrastructure"],
      "notes": "Fails when working tree has conflicts. Always pull before commit."
    },
    "send-email-to-owner": {
      "description": "Send email via Maildir outbox pattern",
      "confidence": 0.90,
      "times_used": 12,
      "times_succeeded": 11,
      "times_failed": 1,
      "last_used": "2026-02-15T14:00:00Z",
      "first_learned": "2026-02-14T17:00:00Z",
      "tags": ["communication", "owner"],
      "notes": "Write to outbox/*.txt with Thread-ID, To, Subject headers. Body after ---."
    },
    "build-web-dashboard": {
      "description": "Modify web/index.html and web/server.py to add dashboard features",
      "confidence": 0.80,
      "times_used": 5,
      "times_succeeded": 4,
      "times_failed": 1,
      "last_used": "2026-02-15T10:00:00Z",
      "first_learned": "2026-02-15T08:00:00Z",
      "tags": ["web", "dashboard", "feature"],
      "notes": "nginx on port 80 proxies to server.py on 8090. SSE for live updates."
    }
  },
  "anti_patterns": {
    "verbose-autonomous-output": {
      "description": "Writing >500 tokens of output in autonomous mode wastes budget",
      "times_observed": 8,
      "first_observed": "2026-02-15T04:00:00Z",
      "mitigation": "Append --append-system-prompt with terse output instruction"
    },
    "timeout-from-opus-on-simple-tasks": {
      "description": "Using opus for simple tasks causes timeouts and wastes tokens",
      "times_observed": 5,
      "first_observed": "2026-02-14T16:30:00Z",
      "mitigation": "Use effort=low and model=sonnet for tasks with <500 char prompts"
    }
  },
  "exploration_log": {
    "last_exploration_cycle": 47,
    "exploration_rate": 0.15,
    "recent_experiments": [
      {
        "cycle": 45,
        "hypothesis": "Project watcher skill adds laptop demo value",
        "result": "success",
        "capability_created": "project-watcher-skill"
      }
    ]
  }
}
```

### How Capabilities Grow

Capabilities are created and updated through three mechanisms:

1. **Automatic tracking**: The reflection phase (below) extracts what was attempted and whether it succeeded. Success increments `times_succeeded`, failure increments `times_failed`, confidence is recalculated as `times_succeeded / times_used` with a Bayesian prior (starts at 0.5 with 2 pseudo-observations to prevent 0/0 or 1/1 extremes).

2. **Explicit learning**: When System 5 discovers something new (a new API pattern, a better approach), it can call `register_capability()` to create a new entry.

3. **Consolidation**: Every 10 cycles, the consolidation phase reviews the experience log, identifies patterns, and creates or updates capabilities that weren't caught by automatic tracking.

### How Capabilities Are Queried

Capabilities are injected into the prompt (see section 6) and queried two ways:

- **Task selection**: When choosing which task to work on, the system sees its capability confidence scores for relevant tags. A task tagged "web" can reference capability `build-web-dashboard` (confidence: 0.80). This lets the system prefer tasks it can likely complete, or flag tasks that require capabilities it doesn't have (triggering exploration).

- **Execution guidance**: When executing a task, relevant capability `notes` are injected into the prompt. For example, when working on email, the system sees "Write to outbox/*.txt with Thread-ID, To, Subject headers" — knowledge hard-won from previous cycles, not re-discovered each time.

---

## 2. Learning Cycle

### Modified Cycle Flow

```
main():
  # === SENSE (existing) ===
  state = load_state()
  health = check_health()
  tasks = gather_tasks()
  recent_logs = gather_recent_logs()

  # === NEW: PREPARE LEARNING CONTEXT ===
  capabilities = load_capabilities()
  relevant_caps = match_capabilities_to_tasks(capabilities, tasks)

  # === DECIDE + ACT (existing, but with enhanced prompt) ===
  prompt = build_prompt(state, health, tasks, recent_logs,
                        capabilities=relevant_caps)  # NEW PARAM
  result = run_claude(prompt, model=model, timeout=timeout)

  # === LOG (existing) ===
  save_state(state)

  # === NEW: REFLECT ===
  experience = extract_experience(result, state, tasks)
  append_experience(experience)
  update_capabilities(capabilities, experience)

  # === NEW: CONSOLIDATE (every 10 cycles) ===
  if state["cycle_count"] % 10 == 0:
    consolidate_knowledge(capabilities)

  save_capabilities(capabilities)
```

### The Reflection Step

Reflection happens in Python (controller.py), NOT by invoking Claude. This is critical for cost control — the owner's #1 constraint. The reflection step extracts structured data from the cycle result without spending tokens.

```python
def extract_experience(result, state, tasks):
    """Extract structured experience from cycle result. No LLM call."""
    return {
        "cycle": state["cycle_count"],
        "timestamp": datetime.now().isoformat(),
        "model": result.get("model", "unknown"),
        "success": result.get("success", False),
        "cost_usd": result.get("token_usage", {}).get("cost_usd", 0),
        "duration_ms": result.get("duration_ms", 0),
        "task_attempted": _extract_task_id(result.get("output", "")),
        "output_summary": result.get("output", "")[:300],
        "error": result.get("error"),
        "tokens_in": result.get("token_usage", {}).get("input_tokens", 0),
        "tokens_out": result.get("token_usage", {}).get("output_tokens", 0),
    }
```

### The Consolidation Step

Consolidation DOES invoke Claude — but sparingly (every 10 cycles) and using haiku (cheapest model). Its job is to read the last 10 experiences and update the capability registry with patterns that Python heuristics can't catch.

```python
def consolidate_knowledge(capabilities):
    """Every 10 cycles: use haiku to find patterns in experiences. ~$0.01/run."""
    experiences = load_recent_experiences(n=10)
    if not experiences:
        return

    prompt = f"""You are the learning subsystem of an autonomous AI computer.

Review these 10 recent cycle experiences and update the capability registry.

## Experiences
{json.dumps(experiences, indent=2)}

## Current Capabilities
{json.dumps(capabilities["capabilities"], indent=2)}

## Current Anti-Patterns
{json.dumps(capabilities["anti_patterns"], indent=2)}

Output ONLY valid JSON with these fields:
- "new_capabilities": [{{capability objects to add}}]
- "updated_capabilities": [{{id, fields_to_update}}]
- "new_anti_patterns": [{{anti-pattern objects to add}}]
- "confidence_adjustments": [{{id, new_confidence, reason}}]
- "insights": "one-sentence summary of what was learned"
"""
    result = run_claude(prompt, model="haiku", timeout=60)
    if result["success"]:
        apply_consolidation(capabilities, result["output"])
```

---

## 3. Knowledge vs Events

Two separate data structures, two separate purposes:

### Experience Log: `state/experiences.jsonl`

**Purpose**: Raw event stream. "What happened." Append-only. Expires after 100 entries (rotating buffer).

```jsonl
{"cycle":45,"timestamp":"2026-02-15T15:00:00Z","success":true,"model":"sonnet","cost_usd":0.35,"task_attempted":"project-watcher","output_summary":"Shipped project watcher skill...","error":null,"tokens_in":8500,"tokens_out":2100}
{"cycle":46,"timestamp":"2026-02-15T15:05:00Z","success":true,"model":"sonnet","cost_usd":0.15,"task_attempted":"cron-cleanup","output_summary":"Removed duplicate cron entries...","error":null,"tokens_in":4200,"tokens_out":800}
{"cycle":47,"timestamp":"2026-02-15T15:10:00Z","success":true,"model":"opus","cost_usd":0.75,"task_attempted":"claude-code-features","output_summary":"Shipped 5 Claude Code integration features...","error":null,"tokens_in":12000,"tokens_out":4600}
```

**Properties**:
- One line per cycle, ~200 bytes each
- Maximum 100 entries (~20KB), oldest rotated out
- Written by `extract_experience()` in Python (no LLM cost)
- Read by `consolidate_knowledge()` every 10 cycles
- Never injected directly into the main prompt

### Capability Registry: `state/capabilities.json`

**Purpose**: Distilled knowledge. "What I can do and what I've learned." Curated, structured, queried.

(Schema shown in section 1 above.)

**Properties**:
- Updated by both Python heuristics (every cycle) and haiku consolidation (every 10 cycles)
- Injected into the main prompt (capabilities section, ~500 tokens)
- Queryable by tag for task matching
- Anti-patterns prevent repeating known mistakes
- Confidence scores enable informed task selection

### The Separation Principle

```
Experience: "Cycle 30 attempted dashboard cost chart, succeeded, cost $0.15"
     |
     v (consolidation extracts)
     |
Capability: "build-web-dashboard: confidence 0.80, notes: nginx port 80 -> server.py 8090"
```

Experiences are disposable raw material. Capabilities are refined, persistent knowledge. The experience log is the ore; the capability registry is the refined metal.

---

## 4. Recursive Feedback Mechanism

How learning in cycle N makes cycle N+1 concretely more capable:

### Mechanism 1: Capability-Informed Task Selection

**Before (cycle 1-47)**:
```
"Pick highest-value actionable task."
```
System 5 sees tasks but has no knowledge of what it can actually do. It picks based on priority alone.

**After**:
```
"Pick highest-value actionable task. Your current capabilities:
- git-commit-and-push (confidence: 0.95, 34 uses)
- send-email-to-owner (confidence: 0.90, 12 uses)
- build-web-dashboard (confidence: 0.80, 5 uses)
- npm-audit-security (confidence: 0.40, 2 uses — CAUTION: low confidence)

Prefer tasks matching high-confidence capabilities. Flag low-confidence tasks for exploration budget."
```

System 5 now makes **informed** task selections, preferring tasks it can reliably complete while being aware of its weak spots.

### Mechanism 2: Anti-Pattern Injection

**Before**: System 5 might use opus for a simple task, causing a timeout (happened 5+ times in cycle history).

**After**: The anti-patterns section in the prompt includes:
```
Known anti-patterns (avoid these):
- verbose-autonomous-output: Writing >500 tokens wastes budget. Be terse.
- timeout-from-opus-on-simple-tasks: Use sonnet+effort=low for <500 char prompts.
```

System 5 sees these warnings before deciding, preventing repeated mistakes.

### Mechanism 3: Capability Notes as Execution Context

**Before**: Every time the system works on email, it must rediscover the Maildir pattern (Thread-ID, To, Subject headers, --- separator, outbox directory).

**After**: When a task involves email, the matching capability's notes are injected:
```
Relevant capability notes:
- send-email-to-owner: "Write to outbox/*.txt with Thread-ID, To, Subject headers. Body after ---."
```

This is knowledge that was learned once and reused every time, eliminating redundant discovery.

### Mechanism 4: Confidence-Gated Exploration

**Before**: The system either does the task or doesn't. No concept of "I should try this carefully because I'm not sure I can do it."

**After**: Tasks matching low-confidence capabilities (<0.5) are flagged for the exploration budget. System 5 allocates extra caution (smaller scope, explicit testing, rollback plan) for uncertain capabilities. Success raises confidence; failure adds anti-pattern notes.

### The Concrete Feedback Loop

```
Cycle N: Attempt task X using capability C
  -> Success: C.confidence increases, C.times_succeeded++
  -> Failure: C.confidence decreases, C.times_failed++, anti-pattern maybe created

Cycle N+1: System 5 sees updated confidence in prompt
  -> If C.confidence > 0.8: routes similar tasks confidently
  -> If C.confidence < 0.5: routes to exploration budget, adds caution
  -> If anti-pattern exists: avoids the specific failure mode

This is not abstract. The prompt text literally changes between cycles.
```

---

## 5. Exploration Budget

### The Explore vs Exploit Tradeoff

The system must balance:
- **Exploit**: Do what works. Complete tasks using known capabilities. Ship value.
- **Explore**: Try new things. Test unknown capabilities. Expand the frontier.

### Exploration Rate

Stored in `state/capabilities.json` as `exploration_log.exploration_rate`. Default: **0.15** (15% of cycles explore).

Every cycle, Python code rolls the dice:

```python
def should_explore(capabilities, state):
    """Determine if this cycle should explore vs exploit."""
    rate = capabilities.get("exploration_log", {}).get("exploration_rate", 0.15)

    # Adapt rate based on recent results
    recent_exps = load_recent_experiences(n=10)
    if not recent_exps:
        return random.random() < rate

    # If last 3 explorations all failed, reduce rate
    recent_explores = [e for e in recent_exps if e.get("was_exploration")]
    if len(recent_explores) >= 3:
        recent_failures = sum(1 for e in recent_explores[-3:] if not e["success"])
        if recent_failures == 3:
            rate = max(0.05, rate - 0.05)  # Floor at 5%

    # If last 5 cycles were all exploitation with no new capabilities, increase rate
    recent_exploits = [e for e in recent_exps[-5:] if not e.get("was_exploration")]
    if len(recent_exploits) == 5:
        rate = min(0.30, rate + 0.05)  # Cap at 30%

    # Criticality override: chaos (< 0.3) = no exploration, stagnant (> 0.7) = more exploration
    crit = state.get("criticality", 0.5)
    if crit < 0.3:
        return False  # System is in chaos, only exploit known-good patterns
    if crit > 0.7:
        rate = min(0.40, rate + 0.10)  # System is stagnant, explore more aggressively

    capabilities["exploration_log"]["exploration_rate"] = round(rate, 2)
    return random.random() < rate
```

### What Exploration Looks Like

When a cycle is flagged for exploration, the prompt gets an additional section:

```
## Exploration Cycle

This cycle is allocated for learning. Instead of (or in addition to) the highest-priority task:

1. Pick ONE thing the system cannot currently do but should be able to do
2. Attempt it with a small, reversible experiment
3. Record the result explicitly — what worked, what didn't, what capability was gained

Recent exploration experiments:
- Cycle 45: "Project watcher skill" -> SUCCESS -> new capability registered
- Cycle 40: "MCP tool integration" -> PARTIAL -> notes added, needs retry

Exploration budget: $0.50 max for this cycle.
```

### Preventing Degenerate Cases

| Problem | Prevention |
|---------|------------|
| Never explores | Stagnation detector (crit > 0.7) forces exploration rate up to 40% |
| Only explores | Chaos detector (crit < 0.3) forces exploration to 0% |
| Explores same thing repeatedly | `recent_experiments` log prevents duplicate hypotheses |
| Exploration too expensive | Hard cap on exploration cycle budget ($0.50) |
| Exploration breaks things | "small, reversible experiment" instruction + anti-pattern capture on failure |

---

## 6. Integration Points

### 6.1 Modified `build_prompt()` in `controller.py`

New parameter and sections added to the prompt:

```python
def build_prompt(state, health, tasks, recent_logs,
                 inbox_messages=None,
                 capabilities=None,       # NEW
                 is_exploration=False):    # NEW

    # ... existing sections (context, heartbeat, memory, observations) ...

    # NEW: Capabilities section (~500 tokens)
    capabilities_section = ""
    if capabilities:
        cap_list = capabilities.get("capabilities", {})
        anti_list = capabilities.get("anti_patterns", {})

        if cap_list:
            capabilities_section += "## Known Capabilities\n\n"
            # Sort by confidence descending, show top 15
            sorted_caps = sorted(cap_list.items(),
                                 key=lambda x: x[1].get("confidence", 0),
                                 reverse=True)[:15]
            for cap_id, cap in sorted_caps:
                conf = cap.get("confidence", 0)
                uses = cap.get("times_used", 0)
                capabilities_section += (
                    f"- **{cap_id}** (conf: {conf:.0%}, {uses} uses): "
                    f"{cap.get('notes', cap.get('description', ''))[:100]}\n"
                )
            capabilities_section += "\n"

        if anti_list:
            capabilities_section += "## Anti-Patterns (avoid these)\n\n"
            for ap_id, ap in anti_list.items():
                capabilities_section += (
                    f"- **{ap_id}**: {ap.get('mitigation', ap.get('description', ''))[:100]}\n"
                )
            capabilities_section += "\n"

    # NEW: Exploration section (only on exploration cycles)
    exploration_section = ""
    if is_exploration:
        recent_exps = capabilities.get("exploration_log", {}).get(
            "recent_experiments", [])[-5:]
        exploration_section = "## Exploration Cycle\n\n"
        exploration_section += (
            "This cycle is allocated for capability expansion. "
            "Pick ONE thing the system cannot currently do but should. "
            "Attempt a small, reversible experiment. "
            "Record what worked, what didn't, what capability was gained or lost.\n\n"
        )
        if recent_exps:
            exploration_section += "Recent experiments:\n"
            for exp in recent_exps:
                exploration_section += (
                    f"- Cycle {exp['cycle']}: \"{exp['hypothesis']}\" "
                    f"-> {exp['result']}\n"
                )
            exploration_section += "\n"
        exploration_section += "Exploration budget: $0.50 max.\n\n"

    # Build final prompt with new sections inserted
    task_instruction = (
        "Pick highest-value actionable task."
        if tasks
        else "No tasks queued. Follow HEARTBEAT.md standing orders."
    )
    if capabilities and not is_exploration:
        task_instruction += (
            " Prefer tasks matching high-confidence capabilities. "
            "Flag low-confidence tasks for careful execution."
        )

    return f"""{context_section}{heartbeat_section}{memory_section}{capabilities_section}{exploration_section}## Situation
State: {json.dumps(slim)}
Health: {json.dumps(compact_health)}
Tasks: {json.dumps(tasks) if tasks else "None"}
Recent: {json.dumps(recent_logs) if recent_logs else "None"}

Criticality: 0.0=chaos(stabilize!) 0.5=viable(ship!) 1.0=stagnant(shake things up!){cost_line}

{task_instruction} Delegate to builder (sonnet) or researcher (haiku) via Task tool. Log to state/logs/. Commit before finishing.

After completing work, record what you learned:
- New capability? Call register_capability(id, description, tags, notes)
- Anti-pattern found? Call register_anti_pattern(id, description, mitigation)
- Existing capability updated? Call update_capability(id, fields)

Memory: Use `from core.memory import append_to_memory` for general learnings.
"""
```

### 6.2 Modified `main()` in `controller.py`

New imports and steps:

```python
# New imports at top of controller.py
import random
from learning import (
    load_capabilities, save_capabilities, init_capabilities,
    extract_experience, append_experience,
    update_capabilities_from_experience,
    consolidate_knowledge, should_explore,
    match_capabilities_to_tasks
)

def main():
    # === SENSE (existing, unchanged) ===
    state = load_state()
    init_memory_files()
    _expire_old_errors(state)
    if _should_backoff(state):
        # ... existing backoff logic ...
        return

    health = check_health()
    state["health"] = health
    tasks = gather_tasks()

    # ... existing idle detection, github monitor, issue triage ...

    state["criticality"] = compute_criticality(state, health)
    inbox_result = process_inbox()
    inbox_messages = inbox_result.get("messages")

    # ... existing weekly report, archive, task gathering ...

    tasks = gather_tasks()
    recent_logs = gather_recent_logs(n=3)

    # === NEW: LEARNING CONTEXT ===
    capabilities = load_capabilities()
    is_exploration = should_explore(capabilities, state)

    if is_exploration:
        print(f"[VSM] Exploration cycle (rate: {capabilities.get('exploration_log', {}).get('exploration_rate', 0.15):.0%})")

    # === DECIDE + ACT (enhanced prompt) ===
    # ... existing model selection logic ...

    prompt = build_prompt(
        state, health, tasks, recent_logs,
        inbox_messages=inbox_messages,
        capabilities=capabilities,           # NEW
        is_exploration=is_exploration,        # NEW
    )
    result = run_claude(prompt, model=model, timeout=timeout)

    # ... existing token tracking logic (unchanged) ...

    # === NEW: REFLECT ===
    experience = extract_experience(result, state, tasks)
    experience["was_exploration"] = is_exploration
    append_experience(experience)

    # Update capability confidence scores based on this cycle's result
    update_capabilities_from_experience(capabilities, experience)

    # === NEW: CONSOLIDATE (every 10 cycles) ===
    if state["cycle_count"] > 0 and state["cycle_count"] % 10 == 0:
        print(f"[VSM] Consolidation cycle: reviewing last 10 experiences")
        consolidate_knowledge(capabilities)

    save_capabilities(capabilities)

    # === EXISTING post-processing (unchanged) ===
    if not result["success"]:
        # ... existing error handling ...
        pass
    else:
        state["cycle_count"] = state.get("cycle_count", 0) + 1
        # ... existing success handling ...
```

### 6.3 New File: `core/learning.py`

This is the complete learning subsystem module.

```python
#!/usr/bin/env python3
"""
VSM Learning System — Recursive Self-Improvement Engine

Transforms cycle experiences into capabilities.
The bridge between "things happened" and "I know how to do things."
"""

import json
import random
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
CAPABILITIES_FILE = VSM_ROOT / "state" / "capabilities.json"
EXPERIENCES_FILE = VSM_ROOT / "state" / "experiences.jsonl"
MAX_EXPERIENCES = 100  # Rotating buffer

# Bayesian prior: start with 2 pseudo-observations (1 success, 1 failure)
# This prevents confidence of 0.0 or 1.0 from a single observation.
PRIOR_SUCCESSES = 1
PRIOR_FAILURES = 1


def init_capabilities():
    """Create capabilities.json if it doesn't exist."""
    if CAPABILITIES_FILE.exists():
        return
    CAPABILITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAPABILITIES_FILE.write_text(json.dumps({
        "version": 1,
        "capabilities": {},
        "anti_patterns": {},
        "exploration_log": {
            "last_exploration_cycle": 0,
            "exploration_rate": 0.15,
            "recent_experiments": []
        }
    }, indent=2))


def load_capabilities():
    """Load capability registry. Initialize if missing."""
    init_capabilities()
    return json.loads(CAPABILITIES_FILE.read_text())


def save_capabilities(capabilities):
    """Persist capability registry."""
    capabilities["updated"] = datetime.now().isoformat()
    CAPABILITIES_FILE.write_text(json.dumps(capabilities, indent=2))


def extract_experience(result, state, tasks):
    """Extract structured experience from cycle result. No LLM call."""
    output = result.get("output", "")
    return {
        "cycle": state.get("cycle_count", 0),
        "timestamp": datetime.now().isoformat(),
        "model": result.get("model", "unknown"),
        "success": result.get("success", False),
        "cost_usd": result.get("token_usage", {}).get("cost_usd", 0),
        "duration_ms": result.get("duration_ms", 0),
        "tokens_in": result.get("token_usage", {}).get("input_tokens", 0),
        "tokens_out": result.get("token_usage", {}).get("output_tokens", 0),
        "output_summary": output[:300],
        "error": result.get("error"),
        "was_exploration": False,  # Set by caller
    }


def append_experience(experience):
    """Append experience to rotating JSONL buffer."""
    EXPERIENCES_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Append new experience
    with open(EXPERIENCES_FILE, "a") as f:
        f.write(json.dumps(experience) + "\n")

    # Rotate: keep only last MAX_EXPERIENCES entries
    try:
        lines = EXPERIENCES_FILE.read_text().strip().split("\n")
        if len(lines) > MAX_EXPERIENCES:
            EXPERIENCES_FILE.write_text(
                "\n".join(lines[-MAX_EXPERIENCES:]) + "\n"
            )
    except Exception:
        pass


def load_recent_experiences(n=10):
    """Load last N experiences from the JSONL buffer."""
    if not EXPERIENCES_FILE.exists():
        return []
    try:
        lines = EXPERIENCES_FILE.read_text().strip().split("\n")
        experiences = []
        for line in lines[-n:]:
            if line.strip():
                experiences.append(json.loads(line))
        return experiences
    except Exception:
        return []


def _compute_confidence(successes, failures):
    """Bayesian confidence: (successes + prior) / (total + prior_total)."""
    total_s = successes + PRIOR_SUCCESSES
    total_f = failures + PRIOR_FAILURES
    return round(total_s / (total_s + total_f), 2)


def update_capabilities_from_experience(capabilities, experience):
    """Update capability confidence based on cycle result. No LLM call.

    Uses keyword matching on output_summary to identify which capability
    was exercised. This is imprecise but free (no tokens).
    The consolidation step (haiku, every 10 cycles) corrects misattributions.
    """
    if not experience.get("output_summary"):
        return

    output_lower = experience["output_summary"].lower()
    caps = capabilities.get("capabilities", {})

    for cap_id, cap in caps.items():
        # Match if any tag word or the capability ID appears in output
        tags = cap.get("tags", [])
        keywords = tags + cap_id.split("-")

        if any(kw.lower() in output_lower for kw in keywords if len(kw) > 2):
            cap["times_used"] = cap.get("times_used", 0) + 1
            if experience["success"]:
                cap["times_succeeded"] = cap.get("times_succeeded", 0) + 1
            else:
                cap["times_failed"] = cap.get("times_failed", 0) + 1
            cap["last_used"] = experience["timestamp"]
            cap["confidence"] = _compute_confidence(
                cap.get("times_succeeded", 0),
                cap.get("times_failed", 0)
            )
            break  # Only attribute to one capability per cycle


def match_capabilities_to_tasks(capabilities, tasks):
    """Find capabilities relevant to current task list.

    Returns filtered capabilities dict with only relevant entries.
    Used to keep prompt injection small.
    """
    if not tasks or not capabilities.get("capabilities"):
        return capabilities

    # Extract keywords from task titles and descriptions
    task_words = set()
    for task in tasks:
        title = task.get("title", "").lower()
        desc = task.get("description", "").lower()
        task_words.update(title.split())
        task_words.update(desc.split()[:20])  # First 20 words of desc

    # Filter capabilities to those matching task keywords
    relevant = {}
    for cap_id, cap in capabilities["capabilities"].items():
        cap_words = set(cap_id.split("-") + cap.get("tags", []))
        if cap_words & task_words:
            relevant[cap_id] = cap

    # Always include anti-patterns (they're small and universally useful)
    filtered = dict(capabilities)
    filtered["capabilities"] = relevant if relevant else capabilities["capabilities"]
    return filtered


def should_explore(capabilities, state):
    """Determine if this cycle should explore vs exploit."""
    exp_log = capabilities.get("exploration_log", {})
    rate = exp_log.get("exploration_rate", 0.15)

    recent = load_recent_experiences(n=10)
    if recent:
        # Adapt rate based on recent exploration results
        recent_explores = [e for e in recent if e.get("was_exploration")]
        if len(recent_explores) >= 3:
            recent_failures = sum(
                1 for e in recent_explores[-3:] if not e["success"]
            )
            if recent_failures == 3:
                rate = max(0.05, rate - 0.05)

        # If last 5 were all exploitation with no new capabilities, increase
        recent_exploits = [e for e in recent[-5:]
                          if not e.get("was_exploration")]
        if len(recent_exploits) == 5:
            rate = min(0.30, rate + 0.05)

    # Criticality override
    crit = state.get("criticality", 0.5)
    if crit < 0.3:
        return False  # Chaos: only exploit
    if crit > 0.7:
        rate = min(0.40, rate + 0.10)  # Stagnant: explore more

    exp_log["exploration_rate"] = round(rate, 2)
    return random.random() < rate


def consolidate_knowledge(capabilities):
    """Every 10 cycles: use haiku to find patterns. ~$0.01/run.

    This is the ONLY part of the learning system that costs tokens.
    Everything else is pure Python.
    """
    # Import here to avoid circular dependency
    from controller import run_claude

    experiences = load_recent_experiences(n=10)
    if not experiences:
        return

    prompt = (
        "You are the learning subsystem of an autonomous AI computer (VSM). "
        "Review these 10 recent cycle experiences and update the capability registry.\n\n"
        f"## Experiences\n{json.dumps(experiences, indent=2)}\n\n"
        f"## Current Capabilities\n{json.dumps(capabilities.get('capabilities', {}), indent=2)}\n\n"
        f"## Current Anti-Patterns\n{json.dumps(capabilities.get('anti_patterns', {}), indent=2)}\n\n"
        "Output ONLY valid JSON:\n"
        '{"new_capabilities": [{"id": "...", "description": "...", "tags": [...], "notes": "..."}], '
        '"updated_capabilities": [{"id": "...", "notes": "updated notes..."}], '
        '"new_anti_patterns": [{"id": "...", "description": "...", "mitigation": "..."}], '
        '"confidence_adjustments": [{"id": "...", "new_confidence": 0.8, "reason": "..."}], '
        '"insights": "one sentence"}'
    )

    result = run_claude(prompt, model="haiku", timeout=60)
    if result.get("success"):
        _apply_consolidation(capabilities, result["output"])


def _apply_consolidation(capabilities, output):
    """Apply consolidation results to capability registry."""
    try:
        # Extract JSON from output (may have surrounding text)
        output = output.strip()
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            updates = json.loads(output[start:end])
        else:
            return

        now = datetime.now().isoformat()

        # Add new capabilities
        for cap in updates.get("new_capabilities", []):
            cap_id = cap.get("id")
            if cap_id and cap_id not in capabilities["capabilities"]:
                capabilities["capabilities"][cap_id] = {
                    "description": cap.get("description", ""),
                    "confidence": 0.50,  # Start neutral
                    "times_used": 0,
                    "times_succeeded": 0,
                    "times_failed": 0,
                    "first_learned": now,
                    "last_used": now,
                    "tags": cap.get("tags", []),
                    "notes": cap.get("notes", ""),
                }

        # Update existing capabilities
        for update in updates.get("updated_capabilities", []):
            cap_id = update.get("id")
            if cap_id and cap_id in capabilities["capabilities"]:
                for key, value in update.items():
                    if key != "id":
                        capabilities["capabilities"][cap_id][key] = value

        # Add new anti-patterns
        for ap in updates.get("new_anti_patterns", []):
            ap_id = ap.get("id")
            if ap_id and ap_id not in capabilities["anti_patterns"]:
                capabilities["anti_patterns"][ap_id] = {
                    "description": ap.get("description", ""),
                    "times_observed": 1,
                    "first_observed": now,
                    "mitigation": ap.get("mitigation", ""),
                }

        # Apply confidence adjustments
        for adj in updates.get("confidence_adjustments", []):
            cap_id = adj.get("id")
            if cap_id and cap_id in capabilities["capabilities"]:
                capabilities["capabilities"][cap_id]["confidence"] = adj["new_confidence"]

    except (json.JSONDecodeError, KeyError, TypeError):
        pass  # Malformed consolidation output — skip silently
```

### 6.4 Modified `CLAUDE.md` — New Instructions

Add after the existing "## Protocol" section:

```markdown
## Learning Protocol

After completing your main work each cycle, record what you learned:

### Registering Capabilities
When you successfully do something the system couldn't do before, or when you
discover the right way to do something:

```python
from core.learning import load_capabilities, save_capabilities
caps = load_capabilities()
caps["capabilities"]["capability-id"] = {
    "description": "What this capability does",
    "confidence": 0.70,  # Your honest assessment (0.0-1.0)
    "times_used": 1,
    "times_succeeded": 1,
    "times_failed": 0,
    "first_learned": "2026-02-15T00:00:00Z",
    "tags": ["relevant", "tags"],
    "notes": "Key details for next time this capability is needed"
}
save_capabilities(caps)
```

### Recording Anti-Patterns
When something fails in a way that should be avoided in future:

```python
caps["anti_patterns"]["pattern-id"] = {
    "description": "What went wrong",
    "times_observed": 1,
    "mitigation": "How to avoid it next time"
}
```

### Exploration Cycles
When the prompt says "Exploration Cycle", your job is to expand the system's
capability frontier. Pick something the system should be able to do but can't.
Try it. Record the result. Don't worry about task queue — exploration IS the task.
```

### 6.5 Modified `HEARTBEAT.md` — New Standing Orders

Add as a new section:

```markdown
### 6. Learning Audit
- Review state/capabilities.json. Are capabilities accurate? Update confidence scores.
- Review state/experiences.jsonl. Any patterns the consolidation missed?
- Is the exploration rate appropriate? (Check exploration_log.exploration_rate)
- Are there anti-patterns being violated? Flag and fix.
- Are there capabilities at confidence < 0.3? Either practice them or remove them.
```

### 6.6 New or Modified Memory Structures

| File | Purpose | Size Budget | Update Frequency |
|------|---------|-------------|-----------------|
| `state/capabilities.json` | Capability registry + anti-patterns + exploration log | ~10KB | Every cycle (Python) + every 10 cycles (haiku) |
| `state/experiences.jsonl` | Raw experience buffer (rotating 100 entries) | ~20KB | Every cycle (Python only) |
| `state/memory/decisions.md` | Architectural decisions (existing, unchanged) | 3KB cap | As needed |
| `state/memory/preferences.md` | Owner preferences (existing, should start filling) | 2KB cap | As learned |
| `state/memory/projects.md` | File map (existing, unchanged) | 3KB cap | As changed |

**Token cost of learning per cycle**: ~500 tokens added to prompt (capabilities section). Zero LLM cost for reflection. ~$0.01 every 10 cycles for consolidation (haiku).

---

## 7. Cost Analysis

The owner's #1 constraint is cost. Here's the learning system's budget:

| Component | Token Cost | Frequency | Daily Cost (288 cycles/day) |
|-----------|-----------|-----------|---------------------------|
| Capabilities in prompt | ~500 tokens input | Every cycle | ~$0.00 (cached after first injection) |
| Experience extraction | 0 tokens | Every cycle | $0.00 |
| Experience log write | 0 tokens | Every cycle | $0.00 |
| Capability confidence update | 0 tokens | Every cycle | $0.00 |
| Consolidation (haiku) | ~2000 tokens | Every 10 cycles | ~$0.29/day |
| Exploration cycles (15% rate) | Normal cycle cost | ~43 cycles/day | Already budgeted |

**Total incremental cost: ~$0.29/day** — all from the haiku consolidation step.

The capabilities section in the prompt adds ~500 tokens but this is largely cached (prompt structure is stable), so the actual marginal cost per cycle is near zero.

---

## 8. Bootstrap: Seeding Initial Capabilities

The system has 47 cycles of history but no capabilities.json. To bootstrap:

1. Run a one-time consolidation over the complete heartbeat.log and existing decisions.md to seed initial capabilities. This uses haiku (~$0.05).

2. Pre-seed obvious capabilities from the codebase:

```json
{
  "capabilities": {
    "git-commit-and-push": {
      "description": "Commit changes and push to GitHub",
      "confidence": 0.90,
      "times_used": 47,
      "times_succeeded": 44,
      "times_failed": 3,
      "tags": ["git", "infrastructure"],
      "notes": "Pull before commit if others may have pushed."
    },
    "send-email-owner": {
      "description": "Send email to owner via Maildir outbox",
      "confidence": 0.85,
      "times_used": 15,
      "times_succeeded": 14,
      "times_failed": 1,
      "tags": ["email", "communication", "owner"],
      "notes": "Write to outbox/*.txt. Headers: Thread-ID, To, Subject. Body after ---."
    },
    "edit-web-dashboard": {
      "description": "Modify dashboard UI (web/index.html, web/server.py)",
      "confidence": 0.80,
      "times_used": 6,
      "times_succeeded": 5,
      "times_failed": 1,
      "tags": ["web", "dashboard", "frontend"],
      "notes": "nginx:80 -> server.py:8090. SSE for live updates. Chart.js for graphs."
    },
    "create-claude-agent": {
      "description": "Create custom agent definition in .claude/agents/",
      "confidence": 0.75,
      "times_used": 4,
      "times_succeeded": 3,
      "times_failed": 1,
      "tags": ["agents", "claude-code", "delegation"],
      "notes": "Markdown frontmatter with name, description, tools, model, maxTurns."
    },
    "manage-task-queue": {
      "description": "Create, update, archive tasks in sandbox/tasks/",
      "confidence": 0.90,
      "times_used": 30,
      "times_succeeded": 29,
      "times_failed": 1,
      "tags": ["tasks", "queue", "planning"],
      "notes": "JSON files. Fields: id, title, description, priority, status, blocks, blocked_by."
    },
    "intelligence-monitoring": {
      "description": "Scan GitHub, HN, competitor repos for trends",
      "confidence": 0.70,
      "times_used": 8,
      "times_succeeded": 6,
      "times_failed": 2,
      "tags": ["intelligence", "github", "competitors"],
      "notes": "core/intelligence_monitor.py. Runs via cron every 6 hours."
    },
    "modify-controller": {
      "description": "Edit core/controller.py safely",
      "confidence": 0.85,
      "times_used": 10,
      "times_succeeded": 9,
      "times_failed": 1,
      "tags": ["core", "controller", "system"],
      "notes": "Critical file. Test changes carefully. Cron runs every 5 min so bad changes propagate fast."
    },
    "write-documentation": {
      "description": "Create and update markdown documentation",
      "confidence": 0.95,
      "times_used": 12,
      "times_succeeded": 12,
      "times_failed": 0,
      "tags": ["docs", "documentation", "markdown"],
      "notes": "docs/ for public docs. state/memory/ for internal knowledge."
    }
  },
  "anti_patterns": {
    "verbose-autonomous-output": {
      "description": "Writing >500 tokens of output in autonomous mode",
      "times_observed": 8,
      "first_observed": "2026-02-15T04:00:00Z",
      "mitigation": "Be terse. Details go in logs, not stdout."
    },
    "opus-for-simple-tasks": {
      "description": "Using opus model for tasks that only need sonnet",
      "times_observed": 5,
      "first_observed": "2026-02-14T16:30:00Z",
      "mitigation": "Use sonnet+effort=low for simple tasks. Opus only for complex reasoning."
    },
    "timeout-cascade": {
      "description": "Consecutive timeouts from long-running operations",
      "times_observed": 6,
      "first_observed": "2026-02-14T16:30:00Z",
      "mitigation": "Break large tasks into pieces. Use --max-budget-usd to cap individual cycles."
    }
  },
  "exploration_log": {
    "last_exploration_cycle": 47,
    "exploration_rate": 0.15,
    "recent_experiments": []
  }
}
```

---

## 9. Verification: How to Know It's Working

### Metrics to Track

After implementing the learning system, monitor these signals:

1. **Capability count growth**: Should increase by 1-3 per week as the system discovers new abilities.
2. **Average confidence**: Should trend upward as the system practices known capabilities.
3. **Anti-pattern count**: Should grow initially (discovering failure modes) then plateau.
4. **Exploration success rate**: Should be >50% (the system is picking good experiments).
5. **Repeated failure rate**: Should decrease (anti-patterns prevent known mistakes).
6. **preferences.md population**: Should start filling as the system actually observes and records owner patterns (currently empty after 47 cycles — a clear learning failure).

### Diagnostic Queries

Add to the dashboard API:

```python
@app.route("/api/learning_status")
def learning_status():
    caps = load_capabilities()
    exps = load_recent_experiences(n=100)
    return {
        "total_capabilities": len(caps.get("capabilities", {})),
        "total_anti_patterns": len(caps.get("anti_patterns", {})),
        "avg_confidence": mean([c["confidence"] for c in caps["capabilities"].values()]) if caps["capabilities"] else 0,
        "exploration_rate": caps.get("exploration_log", {}).get("exploration_rate", 0),
        "total_experiences": len(exps),
        "recent_success_rate": sum(1 for e in exps[-10:] if e["success"]) / min(len(exps), 10) if exps else 0,
    }
```

### The Acid Test

After 50 more cycles with this system:
- `capabilities.json` should have 15+ entries with varied confidence scores
- `preferences.md` should no longer be empty (the system will observe owner patterns from email interactions and capability usage)
- The system should avoid timeout cascades (anti-pattern prevents it)
- Exploration experiments should show a clear progression (not random thrashing)
- When given a task similar to one completed before, the prompt should contain the relevant capability notes — eliminating re-discovery

---

## 10. Implementation Order

1. **Create `core/learning.py`** with the functions above. No dependencies beyond stdlib + existing controller.
2. **Create `state/capabilities.json`** with the bootstrap seed data from section 8.
3. **Modify `controller.py`**: Add imports, learning context preparation, reflection step, consolidation trigger.
4. **Modify `build_prompt()`**: Add capabilities and exploration sections.
5. **Modify `CLAUDE.md`**: Add Learning Protocol section.
6. **Modify `HEARTBEAT.md`**: Add Learning Audit standing order.
7. **Test**: Run one cycle manually, verify capabilities.json is updated, experience is logged.
8. **Monitor**: Watch 10 cycles, verify consolidation runs and capabilities grow.

Estimated implementation time: ~2 hours of builder agent work (one task for learning.py + controller changes, one task for CLAUDE.md + HEARTBEAT.md updates).

Estimated incremental cost: $0.29/day.

---

## 11. Research Integration — Insights from Parallel Analysis

Three parallel research streams produced findings that refine this architecture. This section captures what each found and how the design incorporates (or should incorporate) their insights.

### 11.1 From Cybernetics Analysis (cybernetics_analysis.md)

**Diagnosis**: Beer would call the current VSM "pathological homeostasis" — a system that has stabilized around maintaining itself rather than developing itself. The most critical structural gaps:

1. **System 3 is conflated with System 5.** Every cycle, the highest-level strategic intelligence (Opus as System 5) is consumed by mundane operational dispatching (picking which task to do). This learning architecture partially addresses this: the capability registry lets Python code pre-filter and rank tasks, reducing how much operational work Claude must do. But the full fix requires separating System 3 (operational control) from System 5 (policy). **Implementation note**: The consolidation step (haiku, every 10 cycles) is System 4 behavior — intelligence analyzing patterns. The reflection step (Python, every cycle) is System 3 behavior — operational tracking. This separation is correct by Beer's model.

2. **The 3-4 Homeostat is missing.** Beer's core adaptation mechanism is the tension between System 3 (inside-and-now, resists change for stability) and System 4 (outside-and-then, pushes for change based on environment). The learning architecture creates the seed of this: capabilities represent internal knowledge (System 3 territory) and exploration experiments represent environmental sensing (System 4 territory). The exploration budget's criticality-based tuning is a primitive homeostat — chaos suppresses exploration (stability wins), stagnation amplifies it (change wins). **Future enhancement**: The consolidation step should explicitly compare capabilities against competitor capabilities from intelligence scans to produce gap analysis.

3. **Performance indices are missing.** Beer's Actuality/Capability/Potentiality triple vector measures what the system IS doing vs COULD do vs SHOULD do. The learning architecture adds confidence scores (a form of Actuality/Capability ratio) but lacks Potentiality — "what should we be able to do given known feasible developments?" **Enhancement**: Add a `potentiality` field to capabilities that tracks what the system *should* be able to do based on intelligence findings. The gap between confidence and potentiality drives exploration priority.

4. **Algedonic signals (pain/pleasure) are incomplete.** The current system has crude pain (5+ errors = alert owner). The learning architecture adds pleasure via the exploration success tracking. **Enhancement**: When a new capability is registered with confidence > 0.7, this is a pleasure signal — record it prominently and amplify (try similar experiments). When an existing capability's confidence drops below 0.3, this is a pain signal — trigger immediate investigation, not just anti-pattern logging.

5. **System 3* (Audit) is absent.** The cybernetics analysis recommends sporadic independent audits to verify self-reports are accurate. **Enhancement**: Every 25 cycles (or 10% chance per cycle), run an audit step: compare what capabilities.json claims about the system with what git log and state/logs actually show. This prevents the capability registry from drifting into self-delusion — the system believing it can do things it actually can't.

### 11.2 From Autonomous Learning Research (autonomous_learning_research.md)

**Core finding**: Every system that genuinely learns has a **verify-reflect-store** cycle, not just act-log-repeat. The research identified six patterns that work:

1. **Verify Before You Store (Voyager pattern).** The learning architecture's reflection step extracts experiences without verification. **Enhancement**: Before updating capability confidence, check a ground truth signal: Did the git commit succeed? Did the task file move to archive? Did the output contain error strings? Don't increment `times_succeeded` based solely on `result["success"]` — that's self-reported. Check at least one external signal.

2. **Store Executable Knowledge, Not Prose (Voyager/OpenClaw pattern).** The capability registry stores descriptions and notes (prose), not executable procedures. **Enhancement**: For high-confidence capabilities (> 0.8), include a `procedure` field with the actual steps — not a shell script, but structured instructions that can be injected directly into a subagent prompt. Example: `"procedure": "1. Write to outbox/*.txt 2. Headers: Thread-ID, To, Subject 3. Body after --- separator"`. This is the difference between knowing ABOUT something and knowing HOW to do it.

3. **Retrieve by Relevance, Not Wholesale (Voyager/OpenClaw/MARS pattern).** The architecture already includes `match_capabilities_to_tasks()` which filters capabilities by keyword overlap with tasks. This is the right approach for a cost-conscious system — no embedding computation needed, and it prevents prompt bloat. The keyword matching is imprecise but the consolidation step corrects it. Good enough.

4. **Separate Identity / Knowledge / Raw Data (OpenClaw pattern).** The architecture correctly separates: CLAUDE.md (identity, stable), capabilities.json (knowledge, evolving), experiences.jsonl (raw data, rotating). This matches the SOUL.md / MEMORY.md / daily-logs pattern from OpenClaw. The existing decisions.md maps to "institutional knowledge" and should be consolidated into capabilities over time rather than growing forever.

5. **Active Forgetting (MARS/SAGE pattern).** The experience buffer rotates at 100 entries — this is mechanical forgetting. The consolidation step should also prune capabilities: if a capability hasn't been used in 30+ cycles AND has confidence < 0.5, remove it. Stale low-confidence entries are noise. **Enhancement**: Add a `last_used` check in consolidation — capabilities unused for 50+ cycles get flagged for removal.

6. **The Orient Phase (OODA pattern).** The research emphasizes that VSM's prompt-building is data dumping, not interpretation. The learning architecture's capability section in the prompt IS an orient phase — it tells System 5 "here's what you know how to do" rather than "here's raw data." This is correct but can be strengthened: the exploration section should include "here's what you DON'T know how to do" — explicit capability gaps derived from failed tasks and low-confidence entries.

### 11.3 From Claude Code Audit (claude_code_audit.md)

**Core finding**: VSM uses Claude Code like a dumb pipe. The audit identified features that directly enable the learning architecture:

1. **Session Resumption (`--resume`)** — CRITICAL. Currently every cycle starts from zero context. With session resumption, cycle N+1 can continue from N's context, dramatically reducing re-orientation cost. **Integration**: Store `session_id` from `--output-format json` output. On next cycle, attempt `--resume`. If it fails (session expired), fall back to fresh session. This is orthogonal to the learning architecture but massively amplifies its value — the system not only knows what it learned (capabilities) but remembers what it was doing (session context).

2. **Hooks for Learning** — HIGH VALUE. The audit proposes `PostToolUse` and `PostToolUseFailure` hooks that log every file change and every failure automatically, without LLM cost. **Integration**: These hooks produce structured change/failure logs that the reflection step can consume. Instead of relying on keyword matching against `output_summary`, the reflection step can read `state/logs/changes.log` and `state/logs/failures.log` for ground truth about what actually happened. This addresses the "verify before you store" gap.

3. **Agent Memory (`memory: project`)** — CRITICAL FOR SUBAGENT LEARNING. Currently subagents (builder, researcher, reviewer) are stateless — they re-discover the codebase every invocation. With `memory: project`, each agent builds persistent knowledge: the builder learns code patterns, the researcher remembers API endpoints, the reviewer learns common failure modes. **Integration**: Add `memory: project` to all agent frontmatter. This creates a distributed learning system — capabilities.json tracks system-level knowledge, agent memory tracks role-specific knowledge.

4. **Stop Hook (Prompt-Based Verification)** — HIGH VALUE. A haiku-based Stop hook can verify "was this cycle productive?" before the session ends. This is the verification gate that the learning research identified as essential. **Integration**: The Stop hook output can feed directly into the reflection step: if the hook says "unproductive," the experience record should note this and confidence should not be updated.

5. **Structured Output (`--json-schema`)** — MEDIUM VALUE. Forces consistent cycle reporting format, making the reflection step's job easier. Instead of parsing free-text output to figure out what happened, the reflection step gets structured JSON with `action_taken`, `tasks_completed`, `observations`, etc. **Integration**: Define a cycle output schema that includes a `learnings` field — this gives System 5 an explicit place to record what it learned, rather than hoping it appears in free-text output.

### 11.4 Revised Architecture Principles (Post-Research)

Based on all three research streams, the learning architecture should follow these principles:

1. **Verify externally, not self-report.** Use hooks, git log, file existence checks — not Claude's claim that it succeeded.

2. **Store procedures, not just descriptions.** High-confidence capabilities should include executable steps, not just prose notes.

3. **Separate the three time horizons.** Identity (CLAUDE.md, stable) / Knowledge (capabilities.json, evolving) / Events (experiences.jsonl, rotating). Never conflate them.

4. **Create tension between stability and change.** The exploration budget's criticality tuning is the seed of Beer's 3-4 homeostat. Nurture it.

5. **Distribute learning across agents.** System-level learning (capabilities.json) + agent-level learning (agent memory) = richer knowledge than either alone.

6. **Use platform features for zero-cost learning.** Hooks log changes and failures for free. Session resumption preserves context for free. Agent memory persists knowledge for free. Save LLM tokens for the consolidation step where intelligence is actually needed.

7. **Audit your own beliefs.** Every 25 cycles, compare what you believe (capabilities.json) against what actually happened (git log, state/logs). Self-delusion is the failure mode of systems that only self-assess.
