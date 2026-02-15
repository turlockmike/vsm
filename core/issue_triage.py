#!/usr/bin/env python3
"""
Issue Auto-Triage — Launch Support Infrastructure

Scans open GitHub issues, classifies them, auto-labels, and queues high-priority items.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / "state"
TRIAGE_FILE = STATE_DIR / "issue_triage.json"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"


def _gh_api(endpoint):
    """Call GitHub API via gh CLI. Returns parsed JSON or None on error."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception:
        return None


def _gh_label(issue_number, label):
    """Add label to issue via gh CLI."""
    try:
        subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--add-label", label],
            capture_output=True,
            timeout=10,
            cwd=str(VSM_ROOT),
        )
        return True
    except Exception:
        return False


def load_triage_state():
    """Load triage state (tracks which issues we've processed)."""
    if TRIAGE_FILE.exists():
        try:
            return json.loads(TRIAGE_FILE.read_text())
        except Exception:
            pass
    return {"processed_issues": [], "last_scan": None}


def save_triage_state(state):
    """Save triage state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["last_scan"] = datetime.now().isoformat()
    TRIAGE_FILE.write_text(json.dumps(state, indent=2))


def classify_issue(title, body):
    """Simple keyword-based classification. Returns (category, priority)."""
    title_lower = (title or "").lower()
    body_lower = (body or "").lower()
    text = title_lower + " " + body_lower

    # Bug detection
    bug_keywords = ["bug", "error", "crash", "broken", "fail", "doesn't work", "not working"]
    if any(kw in text for kw in bug_keywords):
        return "bug", 8

    # Installation help
    install_keywords = ["install", "setup", "permission", "cannot run", "how to start"]
    if any(kw in text for kw in install_keywords):
        return "installation-help", 6

    # Feature request
    feature_keywords = ["feature", "could you", "would be nice", "enhancement", "add support"]
    if any(kw in text for kw in feature_keywords):
        return "feature-request", 5

    # Question (default)
    return "question", 3


def create_task(issue_number, title, category, priority):
    """Create a VSM task for this issue."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_id = f"issue-{issue_number}"
    task_file = TASKS_DIR / f"{task_id}.json"

    task = {
        "id": task_id,
        "title": f"GitHub #{issue_number}: {title}",
        "description": f"Address GitHub issue #{issue_number}\nhttps://github.com/turlockmike/vsm/issues/{issue_number}",
        "priority": priority,
        "status": "pending",
        "source": "github-triage",
        "created": datetime.now().isoformat(),
    }

    task_file.write_text(json.dumps(task, indent=2))


def scan():
    """Scan open issues, classify, label, and queue tasks. Returns status dict."""
    state = load_triage_state()
    processed = set(state.get("processed_issues", []))

    # Fetch open issues
    issues = _gh_api("/repos/turlockmike/vsm/issues?state=open&per_page=50")
    if not issues:
        return {"success": False, "error": "GitHub API unavailable"}

    results = {
        "success": True,
        "scanned": 0,
        "new_issues": 0,
        "labeled": 0,
        "tasks_created": 0,
        "categories": {},
    }

    for issue in issues:
        issue_number = issue.get("number")
        if not issue_number:
            continue

        results["scanned"] += 1

        # Skip already-processed issues
        if issue_number in processed:
            continue

        results["new_issues"] += 1

        # Classify
        title = issue.get("title", "")
        body = issue.get("body", "")
        category, priority = classify_issue(title, body)

        results["categories"][category] = results["categories"].get(category, 0) + 1

        # Auto-label
        label_map = {
            "bug": "bug",
            "feature-request": "enhancement",
            "installation-help": "help wanted",
            "question": "question",
        }

        if category in label_map:
            if _gh_label(issue_number, label_map[category]):
                results["labeled"] += 1

        # Queue high-priority items (bugs and installation help)
        if category in ("bug", "installation-help"):
            create_task(issue_number, title, category, priority)
            results["tasks_created"] += 1

        # Mark as processed
        processed.add(issue_number)

    # Save updated state
    state["processed_issues"] = list(processed)
    save_triage_state(state)

    return results


def main():
    """CLI entry point for manual testing."""
    result = scan()
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
