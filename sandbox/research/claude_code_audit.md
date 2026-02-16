# Claude Code Platform Audit for VSM

**Date**: 2026-02-15
**Purpose**: Identify Claude Code features VSM underuses or ignores, with concrete integration paths.

---

## Executive Summary

VSM currently uses Claude Code as a dumb pipe: `claude -p <prompt> --output-format json`. This is like buying a Ferrari and only using first gear. Claude Code has evolved into a sophisticated agent orchestration platform with hooks, skills, agent teams, session persistence, plugins, and streaming — most of which work in `-p` mode. This audit catalogs every feature and rates its value for VSM's self-improvement loop.

---

## 1. What VSM Currently Uses

| Feature | How VSM Uses It | Rating |
|---------|----------------|--------|
| `claude -p` | Non-interactive mode via cron | Correct |
| `--output-format json` | Parse token usage and cost | Good |
| `--model` | Model selection (opus/sonnet) | Good |
| `--append-system-prompt` | Autonomy instructions | Good |
| `--dangerously-skip-permissions` | Unattended execution | Necessary |
| `--mcp-config` | GitHub, fetch, memory servers | Good start |
| `--max-budget-usd` | Per-cycle cost cap | Excellent |
| `--fallback-model` | Auto-downgrade on overload | Good |
| `--effort` | Low/medium/high reasoning | Good |
| `--agents` (JSON flag) | Custom agents via `_load_agents()` | Partially working |
| `.claude/agents/*.md` | Builder, researcher, reviewer | Defined but limited |
| `.claude/skills/*.md` | 5 skills defined | Mostly unused |

**What's missing**: Hooks, session resumption, agent teams, plugins, stream-json, tool restrictions, persistent agent memory, structured output, skills with `context: fork`, and the entire learning feedback loop.

---

## 2. Feature-by-Feature Audit

### 2.1 Session Resumption (`--continue`, `--resume`)

**What it does**: Resume a previous conversation by session ID or continue the most recent session in the current directory. The `--output-format json` response includes a `session_id` field. You can chain: `claude -p --resume $session_id "next instruction"`.

**Works in `-p` mode**: YES. `claude -p --continue "prompt"` and `claude -p --resume <session-id> "prompt"` both work.

**VSM impact**: HIGH. Currently every heartbeat cycle starts from zero context. Claude re-reads CLAUDE.md, re-discovers the codebase, re-orients itself. With session resumption:

- Save session_id from `--output-format json` into `state/state.json`
- Next cycle: `claude -p --resume $session_id "Next cycle. Here's what changed: ..."`
- Claude retains full memory of what it did last cycle
- Dramatically reduces input tokens (no re-reading everything)
- Enables multi-cycle projects: "Continue building feature X from where you left off"

**Concrete integration**:
```python
# In controller.py run_claude():
result = parse_json_result(output)
if result:
    state["last_session_id"] = result.get("session_id")

# Next cycle:
if state.get("last_session_id"):
    cmd.extend(["--resume", state["last_session_id"]])
```

**Caveat**: Sessions can expire or become invalid. Need fallback to fresh session if resume fails. Also, `--no-session-persistence` exists to disable saving (useful for throwaway cycles). The `--fork-session` flag creates a new session from the old one's context (useful for branching work).

---

### 2.2 Hooks System

**What it does**: User-defined shell commands or LLM prompts that execute at specific lifecycle points. 14 hook events covering the entire session lifecycle.

**Works in `-p` mode**: YES. Hooks are defined in settings.json files and fire regardless of interactive/non-interactive mode.

**Hook events relevant to VSM**:

| Hook Event | VSM Use Case |
|-----------|-------------|
| `SessionStart` | Inject dynamic context (git status, recent changes, env vars) |
| `PreToolUse` | Block dangerous operations (e.g., rm -rf, force push) |
| `PostToolUse` | **LEARNING LOOP**: After every file edit/write, log what changed |
| `PostToolUseFailure` | **LEARNING LOOP**: After every failure, record what went wrong |
| `Stop` | Verify cycle completed its goal before allowing exit |
| `SubagentStart` | Track which subagents are spawned and why |
| `SubagentStop` | Capture subagent results and record learnings |
| `SessionEnd` | Final cleanup, cost tracking, cycle summary |
| `PreCompact` | Save important context before compaction |
| `TaskCompleted` | Enforce quality gates (tests pass, linting clean) |

**The Learning Loop via Hooks** (most important for self-improvement):

```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/record-change.sh",
            "async": true
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/record-failure.sh",
            "async": true
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate if this VSM cycle accomplished meaningful work. Context: $ARGUMENTS. Check: 1) Was a task completed or progressed? 2) Were any files committed? 3) Is there unfinished work that needs a follow-up task? Respond with {\"ok\": true} if the cycle was productive, or {\"ok\": false, \"reason\": \"what's missing\"} to continue.",
            "model": "haiku"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/inject-context.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/cycle-summary.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

**Hook scripts for learning**:

`record-change.sh` — async PostToolUse hook:
```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
# Append to a structured change log
echo "$(date -Iseconds)|$TOOL|$FILE" >> state/logs/changes.log
```

`record-failure.sh` — async PostToolUseFailure hook:
```bash
#!/bin/bash
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
ERROR=$(echo "$INPUT" | jq -r '.error // "unknown"')
echo "$(date -Iseconds)|FAIL|$TOOL|$ERROR" >> state/logs/failures.log
```

`inject-context.sh` — SessionStart hook:
```bash
#!/bin/bash
# Inject dynamic context that's expensive to re-compute
cd "$CLAUDE_PROJECT_DIR"
echo "Recent git activity: $(git log --oneline -5 2>/dev/null)"
echo "Pending tasks: $(ls sandbox/tasks/*.json 2>/dev/null | wc -l)"
echo "Last cycle result: $(jq -r '.last_action_summary // "none"' state/state.json 2>/dev/null)"
```

**Prompt-based hooks** — Use an LLM (haiku) to evaluate conditions:
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Did this autonomous AI cycle accomplish its goal? Context: $ARGUMENTS. If work is incomplete and time/budget remain, respond {\"ok\": false, \"reason\": \"Continue: <what to do next>\"}. If the cycle was productive, respond {\"ok\": true}."
          }
        ]
      }
    ]
  }
}
```

**Agent-based hooks** — Spawn a subagent to verify quality:
```json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Verify this task was completed properly. Check: 1) Any new files are syntactically valid 2) state.json is valid JSON 3) If code was changed, git status shows clean or committed. $ARGUMENTS",
            "model": "haiku",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

---

### 2.3 Agent Teams

**What it does**: Coordinate multiple Claude Code instances as a team. One session is team lead, others are teammates. Shared task list, direct messaging between agents, self-coordination.

**Works in `-p` mode**: PARTIALLY. Agent teams are experimental (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). They are primarily designed for interactive use with display modes (in-process or tmux split panes). In `-p` mode, the team lead could theoretically spawn teammates, but the display/messaging infrastructure assumes an interactive terminal.

**VSM impact**: MEDIUM-HIGH, but requires architecture change.

**Current state**: VSM uses fire-and-forget subagents (builder, researcher, reviewer) via the Task tool within a single `-p` session. These work well for focused, independent tasks.

**What agent teams add**:
- Teammates can **talk to each other** (researcher shares findings with builder)
- Shared task list with **dependency tracking** (task B waits for task A)
- Quality gates via `TeammateIdle` and `TaskCompleted` hooks
- Plan approval: require teammates to plan before implementing

**Recommendation**: Don't migrate to agent teams yet. The current subagent approach is simpler, cheaper, and works reliably in `-p` mode. Agent teams are best for:
- Large multi-file refactors (builder + reviewer in parallel)
- Research-then-build workflows where the researcher's findings directly inform the builder
- Competing hypothesis debugging

**Future integration path**:
1. Enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings
2. For complex tasks, have System 5 request a team instead of individual subagents
3. Use `--teammate-mode in-process` (no tmux needed)
4. Monitor token costs carefully — teams use significantly more tokens

---

### 2.4 Skills System (`.claude/skills/`)

**What it does**: Reusable instruction sets that Claude can invoke automatically or users trigger with `/skill-name`. Skills can include supporting files, scripts, and hooks. They can run inline or in a forked subagent context.

**Works in `-p` mode**: YES. Claude discovers skills from `.claude/skills/` and can invoke them automatically based on description matching. The `/skill-name` invocation syntax is for interactive mode, but auto-invocation works in `-p`.

**VSM impact**: HIGH. Skills are the primary way to encode reusable knowledge and workflows.

**Current state**: VSM has 5 skills but they're basic flat markdown files, not using the full skills directory structure or frontmatter options.

**What VSM should add**:

#### a) Self-Improvement Skill (with `context: fork`)
```yaml
---
name: self-review
description: Review recent changes for quality, then record learnings
context: fork
agent: Explore
user-invocable: false
---

Review the last cycle's work:
1. Read state/logs/ for the most recent cycle log
2. Check git log -1 for the last commit
3. Evaluate: Was this change valuable? Any bugs introduced?
4. Write observations to ~/.claude/projects/-home-mike-projects-vsm-main/memory/observations.md
5. If you discovered a pattern (good or bad), add it to core memory
```

#### b) Cost-Aware Task Routing Skill
```yaml
---
name: cost-router
description: Route tasks to the cheapest model that can handle them
user-invocable: false
---

Before delegating to a subagent, evaluate the task complexity:
- Simple reads, checks, classifications -> haiku (cheapest)
- Standard code changes, feature work -> sonnet (balanced)
- Architecture decisions, complex debugging -> opus (expensive)

Check state/state.json token_budget.today_cost_usd before proceeding.
If over 80% of daily budget, downgrade all tasks by one tier.
```

#### c) Git Workflow Skill
```yaml
---
name: safe-commit
description: Commit changes with pre-flight checks
disable-model-invocation: true
allowed-tools: Bash, Read, Grep
---

Before committing:
1. Run python3 -c "import py_compile; py_compile.compile('core/controller.py', doraise=True)"
2. Verify state/state.json is valid JSON
3. Check no .env or secrets are staged
4. Create commit with descriptive message
5. Never force push to main
```

#### d) Skill with Supporting Files
```
.claude/skills/debug-cycle/
  SKILL.md           # Main instructions
  common-errors.md   # Known error patterns and fixes
  scripts/
    diagnose.sh      # Quick diagnostic script
```

---

### 2.5 Tool Restrictions (`--tools`, `--allowedTools`, `--disallowedTools`)

**What it does**: Control which tools Claude can use. `--tools` sets the complete list. `--allowedTools` auto-approves specific tools (no permission prompt). `--disallowedTools` blocks specific tools.

**Works in `-p` mode**: YES.

**VSM impact**: MEDIUM. Reduces token waste and improves safety.

**Current state**: VSM has a commented-out section in controller.py:
```python
# Example: cmd.extend(["--tools", "Read,Grep,Glob,Bash(git:*)"])
# Leaving this for future enhancement based on cycle type detection
```

**Concrete integration**:
```python
# In controller.py, detect task type and restrict tools accordingly:
def get_tools_for_task(tasks):
    """Determine tool restrictions based on task type."""
    if not tasks:
        # Heartbeat-only cycle: read-only exploration
        return ["Read", "Grep", "Glob", "Bash", "WebSearch"]

    # Check if any task requires code changes
    needs_write = any(
        "build" in t.get("title", "").lower() or
        "fix" in t.get("title", "").lower() or
        "implement" in t.get("title", "").lower()
        for t in tasks
    )

    if needs_write:
        return None  # All tools (default)
    else:
        return ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"]
```

The Bash tool supports pattern restrictions: `Bash(git:*)` allows only git commands. This is powerful for safety:
```python
# For read-only cycles:
cmd.extend(["--tools", "Read,Grep,Glob,Bash(git log:*,git status:*,git diff:*),WebSearch"])
```

---

### 2.6 Structured Output (`--json-schema`)

**What it does**: Constrain Claude's output to match a JSON Schema. Claude validates its output against the schema before returning.

**Works in `-p` mode**: YES.

**VSM impact**: MEDIUM. Currently VSM does free-text output and hopes Claude follows the system prompt format. With `--json-schema`, output is guaranteed to be structured.

**Concrete integration**:
```python
cycle_schema = json.dumps({
    "type": "object",
    "properties": {
        "action_taken": {"type": "string", "description": "What this cycle did"},
        "tasks_completed": {"type": "array", "items": {"type": "string"}},
        "tasks_created": {"type": "array", "items": {"type": "string"}},
        "observations": {"type": "string", "description": "What was learned"},
        "next_priority": {"type": "string", "description": "What should happen next cycle"},
        "model_used": {"type": "string"},
        "files_changed": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["action_taken"]
})

cmd.extend(["--json-schema", cycle_schema])
```

**Warning**: This constrains the *text output*, not tool use. Claude can still use all tools during execution; only the final response is schema-validated. This makes it perfect for ensuring consistent cycle reporting.

---

### 2.7 Stream-JSON Format

**What it does**: Real-time streaming output. Each line is a JSON event: tool calls, partial responses, completions. Enables real-time monitoring.

**Works in `-p` mode**: YES. `--output-format stream-json`

**VSM impact**: MEDIUM. Enables real-time cycle monitoring without waiting for completion.

**Concrete integration**: Replace `subprocess.run()` with `subprocess.Popen()` and process events as they arrive:
```python
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, ...)
for line in proc.stdout:
    event = json.loads(line)
    if event.get("type") == "tool_use":
        # Real-time logging of what Claude is doing
        log_tool_use(event)
    elif event.get("type") == "result":
        # Final result
        handle_result(event)
```

This also enables **input-format stream-json** for bidirectional communication — but that's overkill for cron-based VSM.

---

### 2.8 Custom Agents with Full Configuration

**What it does**: `.claude/agents/*.md` files define specialized subagents with YAML frontmatter controlling model, tools, permissions, hooks, skills, memory, and maxTurns.

**Works in `-p` mode**: YES. Agents defined in `.claude/agents/` are discovered at session start.

**VSM impact**: HIGH. VSM's agent files are minimal — they don't use most available options.

**Current state** (builder.md example):
```yaml
---
name: builder
description: Ship features fast
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch
model: sonnet
maxTurns: 15
---
You are the Builder. Build the minimal thing that works.
```

**Enhanced version using all available features**:
```yaml
---
name: builder
description: Ship features and capabilities fast. Use when there's something to build, create, or implement.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch
disallowedTools: Task
model: sonnet
maxTurns: 15
permissionMode: bypassPermissions
memory: project
skills:
  - safe-commit
  - api-conventions
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/validate-syntax.sh"
          async: true
  Stop:
    - hooks:
        - type: prompt
          prompt: "Did the builder complete its assigned task? Check if code was written and committed. $ARGUMENTS"
          model: haiku
---

You are the Builder. Your job is to ship working code FAST.
You work inside ~/projects/vsm/main/. You receive a specific task and you execute it.
Don't deliberate. Don't over-engineer. Build the minimal thing that works, commit it, move on.

After completing your work:
- Commit to git with a clear message
- If you created something in sandbox/, note the path
- Report what you shipped in 2-3 sentences

Check your agent memory before starting — you may have notes from previous builds.
Update your agent memory with what you learned after finishing.
```

**Key new features for agents**:
- `memory: project` — persistent memory across sessions, stored in `.claude/agent-memory/builder/`
- `skills` — preloaded skills give the agent domain knowledge at startup
- `hooks` — quality gates and learning hooks scoped to this agent only
- `disallowedTools: Task` — prevents subagents from spawning their own subagents
- `permissionMode` — explicit permission mode

---

### 2.9 Persistent Agent Memory

**What it does**: Agents with `memory: user|project|local` get a persistent directory that survives across sessions. The agent reads MEMORY.md at startup and can write to it.

**Works in `-p` mode**: YES. The memory directory is filesystem-based.

**VSM impact**: CRITICAL for self-improvement.

**How it works**:
- Agent frontmatter: `memory: project`
- Storage: `.claude/agent-memory/<agent-name>/MEMORY.md`
- At startup, first 200 lines of MEMORY.md are injected into the agent's system prompt
- Agent can read/write files in its memory directory

**Integration for VSM**:
```yaml
# .claude/agents/builder.md
---
memory: project
---
Update your agent memory as you discover codepaths, patterns, library
locations, and key architectural decisions. This builds up institutional
knowledge across conversations.
```

This means the builder agent learns over time:
- "The email system uses agentmail.to API, config in .env"
- "controller.py is fragile around line 490 — the _load_agents JSON parsing"
- "Always run syntax check before committing controller changes"

Each agent builds its own knowledge base. The reviewer learns common failure patterns. The researcher remembers useful API endpoints and documentation locations.

---

### 2.10 Plugins System

**What it does**: Distributable packages of skills, agents, hooks, and MCP servers. Installed via `/plugin install` or `--plugin-dir`. Structure:
```
my-plugin/
  .claude-plugin/
    plugin.json    # Manifest
  skills/          # Skills
  agents/          # Agents
  hooks/           # Hooks (hooks.json)
```

**Works in `-p` mode**: YES via `--plugin-dir /path/to/plugin`.

**VSM impact**: MEDIUM. Not immediately critical, but important for distribution. When VSM becomes installable, users could install VSM as a plugin to add autonomous capabilities to their own Claude Code setup.

**Future path**: Package VSM's agents, skills, and hooks as a plugin for distribution.

---

### 2.11 `--add-dir` (Additional Directories)

**What it does**: Grant Claude Code access to directories beyond the working directory. Skills in those directories are auto-discovered.

**Works in `-p` mode**: YES.

**VSM impact**: LOW-MEDIUM. Could be used to give VSM access to user projects for monitoring/assistance.

---

### 2.12 `--system-prompt` (Full Override)

**What it does**: Completely replace the default system prompt (instead of appending with `--append-system-prompt`).

**Works in `-p` mode**: YES.

**VSM impact**: LOW. The current `--append-system-prompt` approach is correct — it preserves Claude Code's built-in capabilities. Full override would lose tool instructions and safety guidelines.

**Use case**: For specialized single-purpose agents that don't need the full system prompt (e.g., a classification-only agent).

---

### 2.13 `--permission-mode` flag

**What it does**: Sets the permission mode for the session: `default`, `acceptEdits`, `bypassPermissions`, `plan`, `dontAsk`, `delegate`.

**Works in `-p` mode**: YES.

**VSM impact**: LOW. VSM already uses `--dangerously-skip-permissions` which is equivalent to `bypassPermissions`. But for read-only cycles, could use `--permission-mode plan` to enforce read-only exploration.

---

### 2.14 `--no-session-persistence`

**What it does**: Sessions won't be saved to disk. Good for throwaway operations.

**Works in `-p` mode**: YES.

**VSM impact**: LOW. Could use for cheap throwaway cycles (quick health checks) where session history isn't needed.

---

## 3. Priority Integration Roadmap

### Phase 1: Immediate (Learning Feedback Loop)

1. **Add hooks configuration** (`.claude/settings.json`)
   - `PostToolUse` async hook to log all file changes
   - `PostToolUseFailure` async hook to log all failures
   - `SessionStart` hook to inject dynamic git context
   - `Stop` prompt hook to verify cycle productivity
   - `SessionEnd` hook for cost/cycle summary

2. **Upgrade agent definitions** with:
   - `memory: project` for all agents
   - `hooks` for quality gates
   - `skills` preloading for domain knowledge

3. **Add session resumption** to controller.py
   - Store session_id from JSON output
   - Resume on next cycle with `--resume`
   - Fallback to fresh session on failure

### Phase 2: Short-term (Efficiency)

4. **Implement tool restrictions** per cycle type
   - Read-only cycles: restrict to Read, Grep, Glob, Bash(git:*)
   - Build cycles: full tools
   - Review cycles: Read, Grep, Glob, Bash

5. **Add structured output** via `--json-schema`
   - Consistent cycle reporting format
   - Machine-parseable results for state updates

6. **Create proper skill directories** with supporting files
   - Move skills from flat .md to directories with SKILL.md + reference files
   - Add `context: fork` skills for isolated operations

### Phase 3: Medium-term (Platform)

7. **Stream-JSON monitoring** for real-time cycle tracking
   - Replace subprocess.run with Popen for streaming
   - Real-time tool use logging
   - Early cost detection and abort

8. **Agent teams for complex tasks**
   - Enable experimental flag
   - Use for multi-file refactors
   - Use for research-then-build workflows

9. **Plugin packaging** for distribution
   - Package VSM as installable plugin
   - Enable users to add VSM capabilities to their projects

---

## 4. Feature Compatibility Matrix

| Feature | `-p` Mode | Cron Safe | Token Cost | VSM Priority |
|---------|-----------|-----------|------------|-------------|
| Session resumption | YES | YES | SAVES tokens | CRITICAL |
| Hooks (command) | YES | YES | Zero | CRITICAL |
| Hooks (prompt/agent) | YES | YES | Small (haiku) | HIGH |
| Skills auto-invoke | YES | YES | Minimal | HIGH |
| Agent memory | YES | YES | Minimal | HIGH |
| Tool restrictions | YES | YES | SAVES tokens | MEDIUM |
| Structured output | YES | YES | Zero | MEDIUM |
| Stream-JSON | YES | YES | Zero | MEDIUM |
| Agent teams | PARTIAL | RISKY | HIGH | LOW (for now) |
| Plugins | YES | YES | Zero | LOW (for now) |
| `--add-dir` | YES | YES | Zero | LOW |

---

## 5. The Self-Improvement Architecture

Combining these features creates a closed learning loop:

```
                    ┌─────────────────────────────┐
                    │     Heartbeat (cron 5min)    │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  SessionStart Hook           │
                    │  - Inject git context        │
                    │  - Load failure patterns     │
                    │  - Set env vars              │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  Session Resume              │
                    │  (--resume $last_session_id) │
                    │  Context preserved from      │
                    │  previous cycle              │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  System 5 Decides & Acts     │
                    │  Skills loaded automatically │
                    │  Agent memory consulted      │
                    │  Tools restricted by task    │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼──────┐  ┌────────▼────────┐  ┌──────▼─────────┐
    │ PreToolUse     │  │ PostToolUse     │  │ PostToolFailure│
    │ Safety gates   │  │ Change logging  │  │ Failure logging│
    │ Block dangerous│  │ Learn patterns  │  │ Record errors  │
    └────────────────┘  └─────────────────┘  └────────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  Stop Hook (prompt-based)    │
                    │  "Was this cycle productive?"│
                    │  If no → continue working    │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  SessionEnd Hook             │
                    │  - Save cycle summary        │
                    │  - Update cost tracking      │
                    │  - Store session_id for      │
                    │    next cycle's --resume     │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  Agent Memory Updated        │
                    │  - Builder remembers what    │
                    │    code patterns work        │
                    │  - Reviewer remembers common │
                    │    failure modes             │
                    │  - System 5 refines strategy │
                    └─────────────────────────────┘
```

This is the complete feedback loop: observe → decide → act → record → learn → repeat.

---

## 6. Key Insight: What VSM Is Missing Most

The single biggest gap is **continuity between cycles**. Every 5 minutes, VSM starts from scratch — new session, new context, re-reads everything. With session resumption + hooks + agent memory, VSM can:

1. **Remember** what it was doing (session resume)
2. **Learn** from what worked and what failed (hooks + agent memory)
3. **Adapt** its behavior based on patterns (skills + cost-aware routing)
4. **Verify** its own work before moving on (prompt/agent hooks on Stop/TaskCompleted)

This transforms VSM from "a script that runs Claude every 5 minutes" into "a persistent AI agent that evolves across cycles."

---

## Sources

- [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Claude Code Subagents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code Headless/Programmatic](https://code.claude.com/docs/en/headless)
