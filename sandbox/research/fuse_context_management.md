# FUSE-Based Context Management Research

**Date**: 2026-02-14  
**Status**: Exploratory research for VSM context layer optimization  
**Conclusion**: NOT worth pursuing — current filesystem approach is optimal for this use case.

---

## 1. What is FUSE (Filesystem in Userspace)?

FUSE is a software interface that allows non-privileged users to create custom filesystems without writing kernel code. It consists of:

- **Kernel module**: Routes VFS (Virtual File System) calls to `/dev/fuse`
- **libfuse library**: Userspace daemon that implements filesystem operations (open, read, write, etc.)
- **User application**: Implements interfaces for actual file operations

Key benefits:
- Non-root mounting (secure)
- Rapid prototyping of filesystem-like interfaces
- Cross-platform support (Linux, macOS, BSD, Windows)

**Reference**: [FUSE on Wikipedia](https://en.wikipedia.org/wiki/Filesystem_in_Userspace), [Linux Kernel Docs](https://www.kernel.org/doc/html/next/filesystems/fuse.html)

---

## 2. FUSE for LLM Context: Two Patterns Exist

### Pattern A: FUSE as Agent Interface Layer
**Concept**: Expose backend systems (emails, databases, APIs) as a filesystem abstraction.

**How it works**:
- Agents use standard Bash tools (`ls`, `cat`, `grep`, etc.) instead of domain-specific tools
- `ls /workspace/inbox/` triggers FUSE → queries backend database → returns file listings
- Reduces tool complexity significantly

**Benefits**:
- Agents intuitively understand filesystem semantics
- Can organize thoughts into scratch files without token cost
- Natural chaining of operations (`find` → `grep` → `cat`)
- Eliminates sync issues between agent actions and live data

**Example**: Email platform where `.eml` files appear in folder hierarchies per sender/date.

**Reference**: [FUSE is All You Need - Jakob Emmerling](https://jakobemmerling.de/posts/fuse-is-all-you-need/)

### Pattern B: FUSE as LLM-Backed Filesystem
**Concept**: File operations themselves are handled by an LLM.

**How it works**:
- Read operation → LLM queries + history → returns content
- Write operation → appended to in-memory history log
- LLM reconstructs file state from operation history

**Limitations**:
- 100s of milliseconds latency per operation (impractical for real work)
- Proof-of-concept only; not production-ready
- In-memory storage only (no persistence)

**Reference**: [Filesystem Backed by an LLM - Andrew Healey](https://healeycodes.com/filesystem-backed-by-an-llm), [llmfs GitHub](https://github.com/healeycodes/llmfs)

---

## 3. FUSE for LLM Context Examples

### Existing Tools
- **llmfs**: FUSE filesystem where file operations call OpenAI's API. LLM maintains operation history.
- **llm-fuse**: Command-line tool that aggregates repository files for context injection (different approach—not FUSE-based).

### Use Cases in AI
- Exposing databases/APIs as files for agent exploration
- Virtualizing file hierarchies to reduce storage costs
- Security policies enforced by LLM evaluation of requests

---

## 4. What Would FUSE-Based VSM Context Layer Look Like?

### Theoretical Architecture
```
VSM Context Layer (FUSE)
    ↓
/vsm/tasks/          → JSON task queue ✓ (filesystem already)
/vsm/state/          → state.json ✓ (filesystem already)
/vsm/observations/   → memory files ✓ (filesystem already)
/vsm/health/         → metrics computed on-the-fly
/vsm/inbox/          → emails, filesystem already
/vsm/logs/           → cycle logs ✓ (filesystem already)
```

### Potential Benefits
1. Compute health metrics on-read (no disk I/O needed)
2. Virtual aggregation of logs without storing duplicates
3. Symlink-based task dependencies without custom JSON parsing

### Required Infrastructure
- libfuse Python bindings (fusepy or pyfuse3)
- FUSE daemon running as long-lived process
- Mount point in VSM workspace
- Additional error handling and timeouts

---

## 5. Evaluation: Is FUSE Worth Pursuing?

### Current VSM Approach (Status Quo)
- **State**: JSON files in `/state/`
- **Tasks**: JSON files in `/sandbox/tasks/`
- **Observations**: Markdown files in `~/.claude/projects/*/memory/`
- **Emails**: Maildir format in `inbox/` and `outbox/`
- **Health**: Computed on-demand in controller.py

**Characteristics**:
- Zero latency for reads (direct filesystem access)
- Zero marshaling overhead (native JSON parsing)
- No daemon process required
- Zero complexity in deployment
- Works on all platforms without additional dependencies
- Perfect for Claude's tool ecosystem (Read, Glob, Grep all native)

### FUSE Approach
- **Latency**: 10-50ms per operation (FUSE overhead + Python daemon)
- **Complexity**: Requires running long-lived daemon, mount management, error recovery
- **Deployment**: Additional dependency (libfuse), platform-specific issues
- **Benefit**: None for VSM use case

---

## 6. Why FUSE is NOT Right for VSM

| Aspect | Current | FUSE | Winner |
|--------|---------|------|--------|
| **Read latency** | <1ms (direct fs) | 10-50ms (daemon) | Current |
| **Deployment** | Zero deps | +libfuse, daemon mgmt | Current |
| **Cron safety** | No state (stateless) | Daemon can crash/hang | Current |
| **Token cost** | None (filesystem) | None (filesystem) | Tie |
| **Complexity** | ~1500 lines controller | +FUSE daemon + handlers | Current |
| **Tool support** | Native (Read/Glob/Grep) | Requires translation layer | Current |
| **Observability** | Direct file inspection | Black box daemon | Current |

### The Core Problem
**VSM already IS a filesystem-based system.** The current approach:
1. Tasks are JSON files (read via Read tool, zero token cost)
2. State is JSON files (read via Read tool, zero token cost)
3. Memory is markdown files (read via Read tool, zero token cost)
4. Emails are Maildir format (read via Bash/Glob, zero token cost)

FUSE would:
- Add latency where there is none
- Add complexity where there is none
- Add failure modes (daemon crash, mount unmount)
- Provide no token savings (still filesystem underneath)

### When FUSE Would Be Valuable
FUSE shines when:
- Backend is a database or remote API (not files)
- Agent needs transparent database queries without custom tools
- Latency of 10-50ms is acceptable
- Deployment overhead is justified by tool simplification

VSM doesn't have this problem. Its state IS the filesystem.

---

## 7. Recommendation

**ARCHIVE THIS TASK.**

### Rationale
1. Current filesystem approach is already optimal for VSM's architecture
2. Token audit (Cycle 6) shows controller is efficient at ~1500 tokens
3. All state is already accessible via native filesystem tools
4. FUSE would introduce latency, complexity, and failure modes with zero benefits
5. Energy better spent on shipping features than optimization that makes things worse

### What to Do Instead
- If cron response time becomes a blocker, optimize Python controller (faster state loading)
- If task queue becomes bottleneck, consider async task processing (not FUSE)
- If Claude context window fills, implement task summarization or archival (not FUSE)

Current architecture is already following the "filesystem is the interface" pattern that FUSE advocates for. We're just doing it directly—no daemon needed.

---

## References
- [FUSE Wikipedia](https://en.wikipedia.org/wiki/Filesystem_in_Userspace)
- [FUSE is All You Need - Jakob Emmerling](https://jakobemmerling.de/posts/fuse-is-all-you-need/)
- [Filesystem Backed by an LLM - Andrew Healey](https://healeycodes.com/filesystem-backed-by-an-llm)
- [llmfs GitHub](https://github.com/healeycodes/llmfs)
- [Linux Kernel FUSE Docs](https://www.kernel.org/doc/html/next/filesystems/fuse.html)
