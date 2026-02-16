#!/usr/bin/env python3
"""VSM Health Check — verify system is wired correctly."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VSM_ROOT / "core"))
CHECKS = []


def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


@check("Python imports")
def check_imports():
    from learning import load_capabilities, save_capabilities
    from comm import send_email
    return True, "All core modules importable"


@check(".env configuration")
def check_env():
    env_file = VSM_ROOT / ".env"
    if not env_file.exists():
        return False, ".env missing"
    content = env_file.read_text()
    required = ["AGENTMAIL_API_KEY", "OWNER_EMAIL"]
    missing = [k for k in required if k not in content]
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, "All required keys present"


@check("State directory")
def check_state():
    state_dir = VSM_ROOT / "state"
    state_file = state_dir / "state.json"
    caps_file = state_dir / "capabilities.json"
    issues = []
    if not state_dir.exists():
        issues.append("state/ missing")
    if not state_file.exists():
        issues.append("state.json missing")
    if not caps_file.exists():
        issues.append("capabilities.json missing")
    if issues:
        return False, "; ".join(issues)
    state = json.loads(state_file.read_text())
    return True, f"Cycle {state.get('cycle_count', 0)}"


@check("Git repository")
def check_git():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=str(VSM_ROOT),
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=str(VSM_ROOT),
    )
    dirty = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
    br = branch.stdout.strip()
    return True, f"Branch: {br}, dirty files: {dirty}"


@check("Claude CLI")
def check_claude():
    claude = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude):
        return False, f"claude not found at {claude}"
    result = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=10)
    version = result.stdout.strip().split("\n")[0] if result.stdout else "unknown"
    return True, version


@check("Cron jobs")
def check_cron():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [l for l in result.stdout.splitlines() if "vsm" in l.lower() and not l.startswith("#")]
    if not lines:
        return False, "No VSM cron jobs found"
    return True, f"{len(lines)} job(s) active"


@check("Agent definitions")
def check_agents():
    agents_dir = VSM_ROOT / ".claude" / "agents"
    if not agents_dir.exists():
        return False, "No agents directory"
    agents = list(agents_dir.glob("*.md"))
    return True, f"{len(agents)} agents: {', '.join(a.stem for a in agents)}"


def main():
    os.chdir(VSM_ROOT)
    ok_count = 0
    fail_count = 0

    for name, fn in CHECKS:
        try:
            passed, detail = fn()
            status = "OK" if passed else "FAIL"
            if passed:
                ok_count += 1
            else:
                fail_count += 1
            print(f"  [{status}] {name}: {detail}")
        except Exception as e:
            fail_count += 1
            print(f"  [FAIL] {name}: {e}")

    print(f"\n{ok_count}/{ok_count + fail_count} checks passed")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
