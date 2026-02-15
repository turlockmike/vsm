# watch-project

Monitor a code project for issues and opportunities that need attention.

## Purpose

Provides tangible value for laptop installations by automatically detecting common developer pain points that slip through the cracks during active development.

## Usage

VSM automatically scans configured projects every 4 hours. Manual trigger:

```bash
python3 sandbox/tools/project_watcher.py ~/path/to/project
```

## What It Watches

**Uncommitted Work** — Changes sitting staged or unstaged for >1 hour signal interrupted work or forgotten commits.

**Test Failures** — Recent commits with failing tests that weren't caught in pre-commit hooks.

**Security Issues** — Dependencies with known vulnerabilities (npm audit, pip-audit).

**Large Files** — Files >10MB accidentally staged (common mistake before gitignore).

**Stale TODOs** — TODO/FIXME comments added in recent commits but not yet resolved.

**Branch Divergence** — Local branches significantly ahead/behind remote.

## Output

Creates actionable tasks in VSM queue:
- Priority: low (passive observation) to high (security vulnerabilities)
- Clear suggested action (commit, run tests, update dependency, etc.)
- Context: which files, what changed, when detected

## Laptop Value Proposition

Unlike cloud-based linters or CI tools, this runs locally on YOUR machine:
- Zero latency (filesystem scan, not network API)
- Privacy-first (no code uploaded to third-party services)
- Context-aware (sees your working directory state, not just commits)
- Proactive (catches issues before you push, not after)

## Example Output

```
TASK: Uncommitted work in ~/projects/myapp (2h 15m old)
Priority: medium
Suggested action: Review and commit 3 modified files (src/api.js, tests/api.test.js, README.md)
```

## Configuration

Add to cron (optional):
```bash
0 */4 * * * python3 ~/projects/vsm/main/sandbox/tools/project_watcher.py ~/projects
```

Or rely on VSM's heartbeat to run periodically.
