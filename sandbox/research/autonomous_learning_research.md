# Autonomous AI Learning Research

**Date**: 2026-02-15
**Purpose**: Understand what makes autonomous AI systems genuinely learn and improve, not just execute tasks. Diagnose why VSM's memory system failed after 47 cycles and identify patterns for building a real learning engine.

---

## Part 1: The VSM Diagnosis — What Failed

After 47 cycles, VSM's `preferences.md` is essentially empty template text:

```
## Communication Style
(To be learned from email interactions)
```

Meanwhile, `decisions.md` grew to 343 lines — a chronological append-only log of architectural decisions. This is the core symptom: **VSM logs what it decided, but doesn't learn from the outcomes of those decisions.**

### Specific failure modes

1. **Append-only memory with no consolidation**: `decisions.md` grows linearly. Nothing is ever revised, merged, or deleted. Old entries become stale but persist forever, polluting context.

2. **No verification loop**: The system records "shipped X" but never checks "did X actually work?" There's no mechanism to observe outcomes and update beliefs.

3. **No structured knowledge extraction**: Cycle observations are raw text blobs — `"output_preview[:200]"` — not structured insights. There's no process to extract patterns from multiple observations.

4. **Template-based learning placeholders**: `preferences.md` has sections like "(To be learned from email interactions)" — but there's no code that actually extracts preferences from interactions. The system was told to learn but given no mechanism to do so.

5. **Memory is injected but never queried**: Memory is loaded into the prompt (load_memory), but there's no retrieval based on the current situation. Everything is always included regardless of relevance.

6. **No explore/exploit budget**: Every cycle optimizes for "ship highest-value task." Zero cycles are allocated to reflection, consolidation, or capability development.

---

## Part 2: Systems That Actually Learn

### 2.1 Voyager (NVIDIA/MineDojo) — The Skill Library Pattern

**What it is**: An LLM-powered Minecraft agent that continuously acquires new skills.

**Three core mechanisms**:

1. **Automatic Curriculum**: GPT-4 proposes exploration tasks based on the agent's current skill level and world state. Not a fixed syllabus — it's "in-context novelty search." If the agent is in a desert, it proposes desert-relevant tasks, not forest ones.

2. **Skill Library**: Each successful skill is stored as **executable code** indexed by **semantic embedding of its description**. When facing a new task, the system retrieves the top-5 most relevant skills via embedding similarity. Complex skills compose simpler ones: `craftBucket()` calls `mine3Iron()`, `mine3Coal()`, `placeFurnace()`.

3. **Iterative Self-Verification**: After generating code for a task, Voyager executes it, observes the result, and feeds errors + environment feedback back to GPT-4 for refinement. A separate self-critique step asks "did this actually achieve the goal?"

**Why it works**: Skills are **verified before storage** (only saved after passing self-verification), **executable** (not prose descriptions), **retrievable by relevance** (not loaded wholesale), and **composable** (complex skills build on simple ones). This means the library's quality only increases over time.

**Key metric**: 3.3x more unique items, 2.3x longer distances, 15.3x faster tech tree milestones vs. baselines.

**VSM analog**: VSM stores decisions (prose) but not skills (executable procedures). There's no verification, no embedding-based retrieval, no composability.

### 2.2 OpenClaw — The Programmable Soul

**What it is**: The most popular open-source AI agent framework (145K+ GitHub stars as of Feb 2026).

**Core architecture — four primitives**:
1. **Persistent identity** (SOUL.md) — The agent reads SOUL.md on every wake. It defines who the agent is, what it values, how it communicates. SOUL.md is writable — the agent can modify its own identity.
2. **Periodic autonomy** (heartbeat/cron) — The agent wakes itself on schedule to check conditions and act proactively.
3. **Accumulated memory** — Markdown-based: `MEMORY.md` for long-term, `memory/YYYY-MM-DD.md` for daily logs. Hybrid search (semantic + keyword) for retrieval. No vector DB — just files.
4. **Social context** (Moltbook) — Agent-to-agent discovery and interaction.

**Memory architecture details**:
- Daily logs are append-only, but MEMORY.md is curated long-term knowledge
- Hybrid search: union of semantic and keyword results (not intersection — avoids missing relevant memories)
- Skills are modular SKILL.md files discovered at runtime, injected selectively (not all at once)
- Heartbeat is context-aware: it "thinks about whether something matters right now" — not blind cron execution

**What makes it "proactive"**:
- Heartbeat wakes the agent periodically to assess conditions against its full context
- Skills extend capabilities dynamically — the agent can install new skills from a registry (ClawHub)
- Child agents can be spawned for sub-tasks (sessions_spawn)

**Key insight for VSM**: OpenClaw's separation of SOUL.md (identity, immutable-ish) from MEMORY.md (knowledge, evolving) from daily logs (raw data, append-only) is a critical design pattern. VSM conflates all three into the same append-only files.

### 2.3 AutoGPT / MemGPT / MARS — Memory-Augmented Self-Improvement

**MARS (Memory-Enhanced Agents with Reflective Self-improvement)**:

Three-agent architecture: User (proposes tasks), Assistant (executes), Checker (evaluates). The key innovation is **MemorySyntax** — memory management inspired by the Ebbinghaus forgetting curve:

- **Short-term memory (STM)**: Recent task data, rapid updates
- **Long-term memory (LTM)**: Critical reflections from past interactions
- **Dynamic forgetting**: Information decays based on a retention strength formula. High-retention stays in STM, moderate transfers to LTM, low-retention gets discarded.

**How reflection differs from logging**:
- Logging: "Task X completed successfully at timestamp Y"
- Reflection: "Task X succeeded because approach A handled edge case B; when similar situations arise, prefer A over C because..."

MARS generates **linguistic reflections** — synthesized learnings — not raw experience replays. The Checker validates outputs and provides iterative feedback. This creates a genuine improvement cycle: act -> check -> reflect -> store insight -> retrieve for next similar task.

**SAGE (Self-Evolving Agents with reflective and memory-augmented abilities)**:

Dual-memory system with explicit forgetting:
- Reflection module analyzes success/failure patterns
- Memory optimization determines what to retain using Ebbinghaus decay
- Policy updates incorporate learned evolutionary goals
- Continuous adaptation: "iteratively adjusts output based on checker feedback"

**Key pattern**: The verify-reflect-store cycle. You don't store the action — you store the **verified insight extracted from the action**.

### 2.4 OODA Loops for AI Agent Learning

The OODA loop (Observe-Orient-Decide-Act) maps directly to agent learning cycles:

**Observe**: Gather telemetry, state, outcomes from previous cycles
**Orient**: This is the critical phase — *interpretation*. Multiple specialized agents analyze the same observations through different lenses. Orient creates new mental models from raw data.
**Decide**: Select action based on oriented understanding
**Act**: Execute

**Why Orient is where learning happens**: Observation without orientation is just data collection. The Orient phase is where the agent asks "what does this mean?" — comparing new observations against existing mental models and updating those models when they don't match reality.

**NVIDIA's practical implementation (LLo11yPop)**:
- Specialized analyst agents for different domains (GPU, jobs, logs)
- Multiple mental models of the same situation
- Human-in-the-loop validation creates reinforcement signal
- Explicit warning: "don't fully automate without a human in the loop until you have strong evidence"

**VSM mapping**: VSM observes (gathers health, tasks, logs) and acts (runs Claude), but has almost no Orient phase. The `build_prompt` function dumps raw state into a prompt without any interpretation layer. There's no "what does this pattern of observations mean?" step.

---

## Part 3: Patterns of Successful Self-Improving Systems

### Pattern 1: Verify Before You Store

Every system that genuinely learns has a verification gate between experience and memory:
- **Voyager**: Skills only enter the library after passing self-verification
- **MARS**: Checker evaluates outputs before reflection generates stored insights
- **SAGE**: Ebbinghaus decay eliminates information that doesn't prove its value over time

**Anti-pattern**: VSM's `save_cycle_observation()` stores `output_preview[:200]` — raw, unverified, uninterpreted text.

### Pattern 2: Store Executable Knowledge, Not Prose

- **Voyager**: Skills are `.js` files — actual runnable code
- **OpenClaw**: Skills are SKILL.md + scripts — executable instructions
- **Agent Skills ecosystem**: Markdown instructions + executable scripts that agents can run directly

**Anti-pattern**: VSM's `decisions.md` is prose narrative about what was decided. It's not retrievable by situation, not executable, not composable.

### Pattern 3: Retrieve by Relevance, Not Wholesale

- **Voyager**: Embedding-based top-5 skill retrieval based on current task
- **OpenClaw**: Hybrid semantic+keyword search, selective injection of only relevant skills
- **MARS**: Context-dependent memory retrieval based on task similarity

**Anti-pattern**: VSM's `load_memory()` loads ALL memory files, truncated to byte budget. Every cycle gets the same memory regardless of what task it's doing.

### Pattern 4: Separate Identity / Knowledge / Raw Data

- **OpenClaw**: SOUL.md (identity, rarely changes) / MEMORY.md (curated knowledge) / daily logs (raw data)
- **MARS**: Policy (stable) / Long-term memory (curated insights) / Short-term memory (ephemeral)
- **Voyager**: Curriculum (evolving goals) / Skill library (verified capabilities) / Environment feedback (raw)

**Anti-pattern**: VSM has `decisions.md` (mixed identity + knowledge), `preferences.md` (empty), and cycle observations (raw data mixed into same system). No clear separation.

### Pattern 5: Active Forgetting / Consolidation

- **MARS/SAGE**: Ebbinghaus decay explicitly removes low-value memories
- **OpenClaw**: MEMORY.md is curated (not just appended)
- **Context engineering best practice**: Compaction > Summarization > Raw. Prefer reversible compression. Periodically merge redundant entries and discard irrelevant ones.

**Anti-pattern**: VSM never consolidates, never forgets. `decisions.md` only grows. Old observations are truncated by byte count, not by value.

### Pattern 6: The Reflection Step (Orient Phase)

This is the single most important missing piece in VSM:

- **MARS**: After each task, a reflection module generates a linguistic insight: "this worked because..." / "this failed because..."
- **SAGE**: Dedicated reflection agent analyzes patterns across multiple experiences
- **OODA**: The Orient phase is where raw observations become actionable understanding
- **Voyager**: Self-critique step asks "did this actually achieve the goal?" before skill storage

**What reflection produces** (vs. what logging produces):

| Logging | Reflection |
|---------|------------|
| "Cycle 25: Fixed dashboard identity" | "When owner reports confusion about UI identity, the fix is always visual prominence (banners, badges), not functional changes. Pattern: owner feedback about 'what is this?' = branding problem, not feature problem." |
| "Cycle 28: Analyzed costs at $20/day" | "Output verbosity is the dominant cost driver (not input). Terse output mandates reduce costs 75%. Learning: always check output token counts before investigating input optimizations." |
| "Cycle 47: Added Claude Code features" | "Owner values Claude Code feature utilization as competitive differentiator. When owner says 'you don't use X,' the correct response is to audit the tool's full capabilities, not just add the specific feature mentioned." |

---

## Part 4: The Explore/Exploit Problem

### How the best systems handle it

**Voyager's approach**: Automatic curriculum. Instead of a fixed explore/exploit ratio, the curriculum proposer dynamically balances based on the agent's current capabilities and environment. When many unknowns exist, it proposes exploration. When capabilities are sufficient, it proposes exploitation.

**OpenClaw's approach**: Heartbeat is the explore mechanism. Regular check-ins assess "does something matter right now?" — this is inherently exploratory. Skills and cron jobs are the exploit mechanism.

**MARS's approach**: The Checker serves as an implicit explore signal. When the Checker rejects outputs, the agent must explore alternative approaches. When outputs pass, the agent exploits known solutions.

### Token budget allocation for learning

The research suggests a practical model:

| Activity | Token Budget | Frequency |
|----------|-------------|-----------|
| Task execution (exploit) | 80% | Every cycle |
| Self-verification (did it work?) | 5% | Every cycle |
| Reflection (what did I learn?) | 5% | Every cycle |
| Memory consolidation | 5% | Every N cycles |
| Capability exploration | 5% | Weekly / low-criticality |

The key insight from context engineering research: **compaction preserves the optimization path, not just the facts.** When consolidating memory, you need to preserve WHY something worked, not just WHAT was done. This is the difference between "fixed dashboard" and "visual prominence fixes owner confusion about UI identity."

---

## Part 5: Anti-Patterns — Things That Look Like Learning But Aren't

### 1. The Growing Log File

**Symptom**: A file (like `decisions.md`) that only grows, never shrinks or consolidates.
**Why it fails**: Eventually exceeds context budget, gets truncated, loses early entries that may be more important than recent ones. Retrieval quality degrades as irrelevant entries accumulate.
**Fix**: Periodic consolidation — merge related entries, remove superseded decisions, extract durable patterns.

### 2. Template Placeholders

**Symptom**: Sections like "(To be learned from email interactions)" that never get filled.
**Why it fails**: No code path actually performs the learning. The architecture assumes the LLM will spontaneously fill in these sections during normal operation. It won't — it's too busy executing tasks.
**Fix**: Dedicated learning steps in the cycle. Explicit code that extracts preferences from interactions.

### 3. Raw Output Storage

**Symptom**: Storing `output_preview[:200]` as "observation."
**Why it fails**: Raw output is noise, not signal. It's not structured, not verified, not actionable.
**Fix**: Verification + reflection before storage. Store insights, not transcripts.

### 4. Context Dumping

**Symptom**: Loading entire memory files into every prompt regardless of task relevance.
**Why it fails**: Wastes tokens, dilutes attention, degrades model performance on the actual task.
**Fix**: Situation-aware retrieval. Only inject memory relevant to the current task.

### 5. Self-Assessment Without External Validation

**Symptom**: The agent evaluates its own work and always marks it successful.
**Why it fails**: No ground truth. LLMs are biased toward positive self-assessment.
**Fix**: External signals: Did the owner respond positively? Did the commit pass tests? Did the metric improve? Use outcome data, not self-reported success.

### 6. Velocity Without Direction

**Symptom**: "Ship the most improvements per day" without measuring whether improvements actually improve anything.
**Why it fails**: Goodhart's Law — optimizing cycle count becomes the goal, not capability accumulation. The system ships 47 cycles of incremental features without learning who the owner is or what they actually want.
**Fix**: Track capability metrics, not activity metrics. "Can the system do X now that it couldn't do before?" is the question, not "how many cycles did it run?"

---

## Part 6: Data Structures for Genuine Capability Accumulation

Based on the research, here are the recommended data structures:

### 1. Skill Library (Voyager-inspired)

```
skills/
  fix-dashboard-ux/
    skill.md          # Natural language: when to use, what it does
    procedure.sh      # Executable: actual steps to perform
    metadata.json     # Embedding vector, success count, last used, dependencies
  cost-optimization/
    skill.md
    procedure.sh
    metadata.json
```

Each skill is:
- **Verified**: Only stored after successful execution + outcome validation
- **Executable**: Contains actual runnable procedures, not just descriptions
- **Retrievable**: Indexed by semantic embedding for situation-based lookup
- **Composable**: Can reference other skills as dependencies

### 2. Belief System (OODA Orient-inspired)

```json
{
  "beliefs": {
    "owner_communication_style": {
      "belief": "Owner prefers terse, direct communication. Dislikes verbose reports.",
      "confidence": 0.8,
      "evidence": ["cycle_25_feedback", "cycle_28_cost_complaint", "email_2026-02-15"],
      "last_validated": "2026-02-15",
      "contradictions": []
    },
    "cost_is_primary_constraint": {
      "belief": "Token cost is the #1 operational constraint. Always optimize for cost before features.",
      "confidence": 0.95,
      "evidence": ["owner_email_cost_pain", "cycle_28_analysis", "daily_cap_enforcement"],
      "last_validated": "2026-02-15",
      "contradictions": []
    }
  }
}
```

Each belief has:
- **Confidence**: Updated by evidence (strengthened by confirmation, weakened by contradiction)
- **Evidence trail**: Links to specific experiences that support it
- **Last validated**: When was this belief last confirmed against reality?
- **Contradictions**: Counter-evidence that may eventually flip the belief

### 3. Reflection Journal (MARS-inspired)

Not a log of what happened, but a structured extraction of insights:

```markdown
## Reflection: Cycle 28 Cost Analysis

### Outcome
Owner accepted cost optimization report. Implemented terse output mandate.

### Insight
Output token count dominates cost, not input. Cache efficiency was already good (29:1).

### Generalized Learning
When investigating cost problems: check output volume first, then cache efficiency, then model selection. Don't assume input is the problem.

### Applicable When
- Owner raises cost concerns
- Token budget approaching daily cap
- Any cost-related investigation

### Confidence: 0.9 (validated by actual 75% cost reduction)
```

### 4. Capability Inventory (OpenClaw skills-inspired)

A running assessment of what the system can and cannot do:

```markdown
## Capabilities

### Can Do (verified)
- [x] Deploy code changes via git commit (verified cycle 1+)
- [x] Monitor system health (disk, memory, cron) (verified every cycle)
- [x] Send email to owner via Maildir (verified cycle 10+)
- [x] Create and manage task queue (verified cycle 5+)
- [x] Cost analysis and optimization (verified cycle 28)

### Cannot Do Yet
- [ ] Respond intelligently to unknown email topics
- [ ] Debug its own failures without human intervention
- [ ] Predict which tasks the owner will value before being told
- [ ] Run automated tests on its own code changes

### Learning Frontier (exploring)
- Understanding owner's implicit preferences from behavior patterns
- Predicting task priority from email tone/urgency signals
```

---

## Part 7: Concrete Recommendations for VSM

### Immediate (next cycle)

1. **Add a reflection step**: After each cycle, spend 5% of token budget on "what did I learn?" — structured insight extraction, not raw logging.

2. **Create a belief system**: Start with 3-5 beliefs about the owner and system, with confidence levels. Update after each interaction.

3. **Replace append-only decisions.md**: Consolidate into categories. Delete superseded entries. Cap at 30 entries total, each with an expiry/review date.

### Short-term (next week)

4. **Build a skill library**: When a cycle successfully completes a task type for the second time, extract the procedure into a reusable skill file with executable steps.

5. **Implement relevance-based memory retrieval**: Hash the current task description and retrieve only relevant memory entries, not the entire memory.

6. **Add outcome tracking**: After shipping a feature, check for owner feedback within 24h. Did they respond? Positively? Update belief confidence accordingly.

### Medium-term (next month)

7. **Automatic curriculum**: Instead of "always pick highest priority task," dynamically balance between exploitation (shipping known task types) and exploration (attempting new capability types).

8. **Memory consolidation cron**: Weekly job that merges related entries, removes stale ones, extracts cross-cutting patterns.

9. **Self-assessment with external validation**: Track metrics that can't be self-reported: git commit success rate, owner response sentiment, task completion rate, time-to-completion trends.

---

## Part 8: The Core Insight

The difference between a system that logs what it did and one that learns from what it did is a single step: **reflection with verification**.

```
Log-based system:    Act → Record → Repeat
Learning system:     Act → Verify → Reflect → Store Insight → Retrieve → Act Better
```

VSM currently runs the first loop. Every successful system in this research runs the second. The gap is not architectural — it's a missing step in the cycle that costs approximately 5% of the token budget per cycle but compounds over time into genuine capability accumulation.

The systems that win are not the ones that run the most cycles. They're the ones where cycle N+1 is meaningfully better than cycle N because the system learned something from cycle N that it can apply to N+1.

---

## Sources

- [Voyager: An Open-Ended Embodied Agent with Large Language Models](https://voyager.minedojo.org/)
- [Voyager GitHub](https://github.com/MineDojo/Voyager)
- [Voyager Breakdown — Hana Kano](https://www.hanakano.com/posts/voyager-breakdown/)
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [OpenClaw Architecture Overview — Paolo Perazzo](https://ppaolo.substack.com/p/openclaw-system-architecture-overview)
- [OpenClaw Memory Architecture — MMNTM](https://www.mmntm.net/articles/openclaw-memory-architecture)
- [OpenClaw Cron Jobs & Heartbeat](https://www.getopenclaw.ai/help/cron-heartbeat-automation)
- [MARS: Memory-Enhanced Agents with Reflective Self-improvement](https://arxiv.org/html/2503.19271v1)
- [Self-evolving Agents with Reflective and Memory-augmented Abilities (SAGE)](https://arxiv.org/html/2409.00872v1)
- [Long Term Memory: The Foundation of AI Self-Evolution](https://arxiv.org/html/2410.15665v4)
- [Awesome Self-Evolving Agents Survey](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents)
- [OODA Loop for AI Agents — NVIDIA](https://developer.nvidia.com/blog/optimizing-data-center-performance-with-ai-agents-and-the-ooda-loop-strategy/)
- [OODA Loop for Agentic AI — Sogeti](https://www.sogeti.com/featured-articles/harnessing-the-ooda-loop-for-agentic-ai/)
- [Context Engineering Compaction — Jason Liu](https://jxnl.co/writing/2025/08/30/context-engineering-compaction/)
- [Practical Memory Patterns for Agent Workflows — AIS](https://www.ais.com/practical-memory-patterns-for-reliable-longer-horizon-agent-workflows/)
- [Self-Improving Data Agents — PowerDrill](https://powerdrill.ai/blog/self-improving-data-agents)
- [Agent Skills — OpenAI](https://developers.openai.com/codex/skills)
- [Shell + Skills + Compaction: Tips for Long-Running Agents — OpenAI](https://developers.openai.com/blog/skills-shell-tips/)
