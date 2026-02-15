# Show HN Draft

## Title Options

Pick ONE. HN titles should be factual, concise, under 80 characters.

### Option 1 (Recommended)
```
Show HN: VSM – Autonomous AI computer that runs on your machine via Claude Code
```

### Option 2 (Technical Focus)
```
Show HN: VSM – Self-healing AI system built entirely on Claude Code CLI
```

### Option 3 (Problem Focus)
```
Show HN: VSM – AI computer that maintains itself via cron + Claude Code
```

### Option 4 (Architecture Focus)
```
Show HN: Viable System Machine – Autonomous AI using Beer's VSM theory + Claude
```

---

## Post Body

**Character limit**: Aim for 1500-2000 characters (HN users skim fast)

### Draft A (Recommended)

```
I built an autonomous AI computer that runs on your local machine. It maintains itself, fixes bugs, ships features, and communicates via email — all without supervision.

VSM (Viable System Machine) runs every 5 minutes via cron. Each cycle, Claude Code assesses system health, checks the task queue, decides what's most important, and delegates work to specialized agents (builder, researcher, reviewer). The agents execute, commit changes, and report back.

You interact with it through:
- Email: Send tasks, receive reports and alerts
- Web dashboard: Real-time system state at localhost:80
- CLI: vsm task add "Feature X", vsm status, vsm logs

It's based on Stafford Beer's Viable System Model — a theory of autonomous systems that self-organize and evolve. The architecture uses Claude Code as the runtime, with a controller that gathers state and spawns agents on-demand.

Key features:
- Self-healing: Detects errors, alerts you, fixes itself
- Model fallback: Downgrades from Opus to Sonnet on repeated failures
- Exponential backoff: Prevents runaway costs on broken cycles
- Persistent memory: Learns from past cycles and decisions

It's production-ready. I've been running it for 3 weeks. It's fixed its own bugs, shipped new features, and even researched competing systems autonomously.

Repo: https://github.com/turlockmike/vsm
Demo: https://github.com/turlockmike/vsm#demo
Install: curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash

Happy to answer questions about the architecture or show more of how it works.
```

**Character count**: ~1,450

---

### Draft B (Shorter, punchier)

```
VSM is an autonomous AI computer that runs on your machine via Claude Code.

Every 5 minutes, cron triggers a heartbeat. Claude assesses system health, prioritizes the task queue, and delegates work to specialized agents. The agents ship code, run tests, commit changes, and report back.

You communicate via email or a web dashboard. You can send it tasks, receive alerts, and check status without touching the command line (though there's a CLI too).

It's self-healing: detects errors, alerts you, downgrades models on failures, and applies exponential backoff to prevent runaway costs.

It's based on Stafford Beer's Viable System Model — a cybernetics theory about autonomous systems.

I've been running it for 3 weeks. It's shipped features, fixed bugs, and researched competing systems — all autonomously.

Repo: https://github.com/turlockmike/vsm
One-line install: curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash

Questions welcome.
```

**Character count**: ~980

---

### Draft C (Problem-first framing)

```
I was tired of babysitting AI coding assistants. Every agent framework I tried either ran in the cloud (trust issues) or required constant supervision (defeats the purpose).

So I built VSM — an autonomous AI computer that runs on your machine and actually works unsupervised.

It runs via cron every 5 minutes. Claude Code assesses health, checks the task queue, delegates work to agents (builder/researcher/reviewer), and commits changes. You interact via email, a web dashboard, or CLI.

The architecture is based on Stafford Beer's Viable System Model — a theory of autonomous systems from the 1970s. System 5 (intelligence) coordinates System 4 (planning), System 3 (operations), etc. Claude is System 5. The agents are Systems 3-4.

Key details:
- Self-healing: Detects errors, alerts via email, fixes itself
- Model fallback: Downgrades Opus → Sonnet on repeated failures
- Persistent memory: Learns from past cycles and decisions
- Task dependencies: Agents can block/unblock each other's work

It's been running for 3 weeks. It's shipped features, fixed bugs, and researched competitors — all on its own.

Repo: https://github.com/turlockmike/vsm
Demo GIF: https://github.com/turlockmike/vsm#demo

Open to feedback and questions.
```

**Character count**: ~1,350

---

## First Comment Strategy

Post this as your FIRST comment immediately after posting. It provides proof and context.

```
Author here. Happy to answer questions about how this works.

Some technical details that might be interesting:

**Architecture**: The controller (Python) gathers state from the filesystem: task queue (JSON files in sandbox/tasks/), error logs, health metrics, recent observations. It builds a prompt and invokes Claude Code CLI with `claude -p "prompt"`. Claude decides whether to delegate to subagents or handle work directly.

**Cost control**: Exponential backoff on failures (1 cycle → 2 cycles → 4 cycles → 8 cycles delay). Model downgrade after 3 consecutive failures (Opus → Sonnet). Token budget tracking. Slim prompts (~1500 tokens via compression).

**Task queue**: Filesystem-based. Each task is a JSON file. Agents can add/update/complete tasks. Dependencies work via `blocks`/`blocked_by` fields. Blocked tasks auto-unblock when dependencies complete.

**Memory**: Persistent observations stored in state/memory/ (capped at 4KB total to save tokens). Intelligence reports in state/intelligence/ (daily scans of competitors, new research).

**Communication**: Email via agentmail.to API. Maildir pattern (inbox/ for reading, outbox/ for sending). Email responder runs every 1 minute, processes incoming mail, queues tasks.

The demo GIF shows the full cycle: email arrives → task queued → agent processes → work committed → status reported.

Biggest challenge so far: Preventing context bloat. Claude Code's context window is large, but gathering too much state kills performance. Solution: microcompaction (compress old observations), capped memory sizes, blocked task filtering.

What questions do you have?
```

---

## Likely Questions & Pre-Written Answers

### Q: What does this cost to run?
**A**:
```
Depends on activity level. At 5-minute intervals with Opus, I'm seeing ~$2-3/day during active development (lots of code changes).

During steady-state (minimal changes, just health checks), it's ~$0.50/day because Claude skips work when there's nothing critical.

You can configure:
- Interval (5 min default, can increase to 15-30 min)
- Model (Opus for intelligence, Sonnet for routine work)
- Token budget caps

The controller tracks costs in state/state.json. VSM will email you if spending exceeds thresholds.
```

### Q: How is this different from AutoGPT / AgentGPT?
**A**:
```
Three key differences:

1. Self-hosted: Runs on your machine, not a cloud service. You control the data.

2. Claude Code native: Built entirely on the Claude Code CLI. AutoGPT/AgentGPT use OpenAI APIs with custom agent frameworks. VSM leverages Claude Code's built-in capabilities (tool use, bash, file ops).

3. Production-ready autonomy: This isn't a demo or research project. It's been running in production for 3 weeks, maintaining itself. AutoGPT often gets stuck in loops or requires manual intervention.

VSM is also based on Beer's VSM theory, which provides a clear architectural model for autonomous systems (vs ad-hoc agent loops).
```

### Q: Isn't running arbitrary code from Claude dangerous?
**A**:
```
Legitimate concern. Mitigations:

1. Sandboxing: Agents work in sandbox/ directory with limited scope
2. Git safety: All changes committed to git, easy to revert
3. Review agent: Post-change audits by specialized reviewer agent
4. Owner oversight: Email alerts on errors, dashboard shows all activity
5. You control the constitution: .claude/CLAUDE.md defines rules and constraints

That said: yes, you're trusting Claude with code execution. If that's unacceptable for your threat model, this isn't for you.

I've been running it for 3 weeks with no issues, but YMMV. Start with low-stakes tasks and build trust.
```

### Q: Can I use this with GPT-4 / other models?
**A**:
```
Not easily. VSM is tightly coupled to Claude Code CLI, which is Anthropic-specific.

You could fork it and replace `claude -p` calls with OpenAI API calls + custom tool handling, but you'd lose a lot of Claude Code's magic (built-in bash/file tools, prompt caching, context management).

If there's demand, I could abstract the model layer, but for now it's Claude-native by design.
```

### Q: What's the roadmap?
**A**:
```
Near-term (next 4 weeks):
- Improve installation (Docker option, better error messages)
- Community agent library (share specialized agents)
- Integration guides (Zapier, Home Assistant, etc)
- Performance optimizations (faster cycles, lower token usage)

Medium-term (2-3 months):
- VSM marketplace (pre-built configs for common use cases)
- Multi-machine coordination (VSM instances talking to each other)
- Advanced memory (vector DB for long-term knowledge)

Long-term (6+ months):
- VSM hosting service (optional cloud deployment)
- Enterprise features (team collaboration, audit logs)

But honestly, roadmap is driven by community feedback. What would you want to see?
```

### Q: How do I debug when it breaks?
**A**:
```
Debugging tools:

1. `vsm logs -n 50`: Show last 50 lines of cycle logs
2. `vsm status`: Health metrics, active errors, recent activity
3. Dashboard (localhost:80): Real-time view of system state
4. Email alerts: System emails you when errors occur
5. Git history: `git log --oneline` shows what changed

Common issues:
- API key misconfigured (.env file)
- Cron not running (check `crontab -l`)
- Port 80 blocked (dashboard won't load)
- Email not working (check agentmail.to API key)

If truly broken, manual recovery:
```bash
vsm run  # Force a cycle to see what fails
git log  # Check what changed
git revert HEAD  # Roll back last change if needed
```

I'm also responsive to GitHub issues. Post there and I'll help debug.
```

---

## Timing Strategy

**Best days**: Tuesday, Wednesday, Thursday
**Best times**: 8-10am PST (when HN users are starting their workday)
**Avoid**: Monday (too busy), Friday (low engagement), weekends (low traffic)

**Recommended**:
- Post Tuesday at 8:30am PST
- Monitor continuously for first 6 hours
- Respond to every comment within 2 hours
- Stay online until 6pm PST

---

## Post-Launch Monitoring

Track these in first 24 hours:

- [ ] Upvotes (goal: 50+)
- [ ] Comments (goal: 20+)
- [ ] GitHub stars (goal: 10+)
- [ ] Position on front page (goal: top 10 for 4+ hours)
- [ ] Install attempts (check clone count in GitHub Insights)
- [ ] Issues opened (indicates real usage)

If front page for 4+ hours: Success. Move to Phase 2.
If <20 upvotes after 2 hours: Dead in water. Analyze failure, regroup.

---

## Failure Analysis

If HN post flops:

1. Read all comments carefully (what confused people?)
2. Check if demo GIF loaded (image issues kill posts)
3. Assess title (too vague? too salesy? unclear value prop?)
4. Review timing (wrong day/time?)
5. Document lessons in state/memory/decisions.md
6. Decide: repost in 1 week with fixes, or pivot to Reddit first

Don't take it personally. HN is fickle. Even great projects sometimes don't land on first try.

---

**Owner Decision Required**: Pick title and draft, set launch date.
