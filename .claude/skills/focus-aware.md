# focus-aware

Context-aware task prioritization based on active window/app detection.

## Purpose

Laptop installations gain intelligence about what the user is actively working on. VSM can boost task priority when it detects you're working in a specific project, making suggestions timely and relevant rather than random.

## How It Works

**Window Detection:**
- Linux: Uses `xdotool` to detect active window (X11)
- macOS: Uses AppleScript to query frontmost application
- Extracts: app name, window title, project path (if IDE)

**Priority Boosting:**
- When you're actively editing a project in VS Code/editor
- And that project has uncommitted changes
- VSM creates a HIGH priority task instead of low/medium
- Context-aware nudge: "you're working on this right now, commit it before you switch"

**Privacy-First:**
- Only logs app names, not window content
- No screenshots, no keylogging
- Gracefully disables if tools unavailable (doesn't crash)
- Logs context changes to state/logs/window_context.log (last 100 entries)

## Usage

**Manual trigger with focus-aware mode:**
```bash
python3 sandbox/tools/project_watcher.py ~/projects --focus-aware
```

**Automatic (via cron):**
Add to crontab for periodic checks:
```bash
*/30 * * * * cd ~/projects/vsm/main && python3 sandbox/tools/project_watcher.py ~/projects --focus-aware
```

**Check if available:**
```bash
python3 core/window_monitor.py
# Outputs current active window context if available
```

## Prerequisites

**Linux (X11):**
```bash
sudo apt install xdotool
```

**macOS:**
No installation needed (osascript built-in).

**Wayland/WSL2:**
Window detection may not work. Falls back gracefully to non-focus-aware mode.

## Example

```
$ python3 sandbox/tools/project_watcher.py ~/projects --focus-aware

Focus-aware mode: active app = Code
  Active project: /home/user/projects/vsm

Watching /home/user/projects/vsm [ACTIVE]...
  [HIGH] Uncommitted work in vsm (2h 15m old) -> watch_uncommitted_work_20260215_083045 (focus-boosted)

Watching /home/user/projects/other-app...
  [LOW] Uncommitted work in other-app (3h 10m old) -> watch_uncommitted_work_20260215_083046

=== Summary ===
Total findings: 2
  HIGH: 1
  LOW: 1
```

## Configuration

**Enable by default:**
Edit `project_watcher.py` to use `--focus-aware` by default, or update cron job.

**Disable entirely:**
Remove `--focus-aware` flag. Script works without window detection.

**Change poll interval:**
Default: every 30 minutes (cron `*/30`). Adjust to taste. Too frequent (every minute) may drain laptop battery.

## Laptop Value

Unlike cloud-based CI or linters, this runs on YOUR laptop and sees what YOU'RE actively working on:

- Zero latency (local filesystem + window manager API)
- Privacy-first (no data leaves your machine)
- Context-aware (knows you're in VS Code editing that specific project)
- Timely nudges (suggests commit NOW while you're still in that context)

Perfect for developers who juggle multiple projects and forget to commit before switching context.
