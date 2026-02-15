#!/usr/bin/env python3
"""
GitHub Metrics Monitor — Launch Support Infrastructure

Autonomously tracks repository metrics during Show HN launch.
Detects growth, traffic spikes, and notifies owner on milestones.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / "state"
METRICS_FILE = STATE_DIR / "github_metrics.json"


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


def load_metrics():
    """Load baseline metrics from state file."""
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text())
        except Exception:
            pass
    return {
        "stars": 0,
        "forks": 0,
        "watchers": 0,
        "views_total": 0,
        "views_unique": 0,
        "clones_total": 0,
        "clones_unique": 0,
        "last_check": None,
        "milestones_reached": [],
    }


def save_metrics(metrics):
    """Save metrics to state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    metrics["last_check"] = datetime.now().isoformat()
    METRICS_FILE.write_text(json.dumps(metrics, indent=2))


def _email_owner(subject, body):
    """Send email to owner via comm.py."""
    try:
        subprocess.run(
            ["python3", str(VSM_ROOT / "core" / "comm.py"), subject, body],
            timeout=10,
            cwd=str(VSM_ROOT),
        )
    except Exception:
        pass


def check():
    """Check GitHub metrics and detect significant changes. Returns status dict."""
    baseline = load_metrics()

    # Fetch current repo stats
    repo_data = _gh_api("/repos/turlockmike/vsm")
    if not repo_data:
        return {"success": False, "error": "GitHub API unavailable"}

    # Fetch traffic stats (views)
    traffic_data = _gh_api("/repos/turlockmike/vsm/traffic/views")

    # Fetch clone stats
    clone_data = _gh_api("/repos/turlockmike/vsm/traffic/clones")

    # Extract current metrics
    current = {
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "watchers": repo_data.get("subscribers_count", 0),
        "views_total": traffic_data.get("count", 0) if traffic_data else 0,
        "views_unique": traffic_data.get("uniques", 0) if traffic_data else 0,
        "clones_total": clone_data.get("count", 0) if clone_data else 0,
        "clones_unique": clone_data.get("uniques", 0) if clone_data else 0,
        "last_check": datetime.now().isoformat(),
        "milestones_reached": baseline.get("milestones_reached", []),
    }

    # Detect significant changes
    changes = {}
    star_delta = current["stars"] - baseline["stars"]
    if star_delta >= 10:
        changes["stars"] = star_delta

    view_delta = current["views_unique"] - baseline["views_unique"]
    if view_delta >= 50:
        changes["traffic_spike"] = view_delta

    # Check for milestone achievements
    milestones = [25, 50, 100, 200, 500]
    reached = baseline.get("milestones_reached", [])
    for milestone in milestones:
        if current["stars"] >= milestone and milestone not in reached:
            current["milestones_reached"].append(milestone)
            changes[f"milestone_{milestone}"] = True

            # Email owner on milestone
            _email_owner(
                f"VSM GitHub Milestone: {milestone} Stars!",
                f"VSM has reached {milestone} stars on GitHub!\n\n"
                f"Current stats:\n"
                f"- Stars: {current['stars']}\n"
                f"- Forks: {current['forks']}\n"
                f"- Unique views (14d): {current['views_unique']}\n"
                f"- Unique clones (14d): {current['clones_unique']}\n\n"
                f"Keep shipping!"
            )

    # Save updated metrics
    save_metrics(current)

    return {
        "success": True,
        "current": current,
        "changes": changes,
        "significant": len(changes) > 0,
    }


def main():
    """CLI entry point for manual testing."""
    result = check()
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
