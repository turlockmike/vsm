#!/usr/bin/env python3
"""
VSM Proactive Intelligence Monitor
Watches for developments in AI/autonomous systems space and reports findings.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / "state" / "intelligence"
HISTORY_FILE = STATE_DIR / "seen_items.json"

# Topics of interest
TOPICS = [
    "autonomous agents",
    "AI agents",
    "Claude Code",
    "AI automation",
    "agent frameworks",
    "VSM",
    "viable system model",
    "autopoietic systems",
]

# Competitors to track
COMPETITORS = [
    "aider",
    "openclaw",
    "devin",
    "autogpt",
    "babyagi",
    "langchain agents",
    "CrewAI",
]


def load_seen_items():
    """Load history of items we've already reported."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"hn_ids": [], "github_repos": [], "last_check": None}


def save_seen_items(seen):
    """Save updated history."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def fetch_url_via_mcp(url):
    """Fetch URL content using MCP fetch tool via Claude CLI."""
    try:
        # Call Claude with MCP enabled to fetch content
        prompt = f"Please fetch the content from {url} and return it as plain text markdown. Just return the content, no commentary."
        result = subprocess.run(
            ["claude", "-p", prompt],
            cwd=VSM_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def search_hn_front_page():
    """Check HN front page for relevant AI/agent posts."""
    findings = []

    # Simple approach: fetch HN front page and extract relevant items
    # We'll use curl instead of MCP for simplicity
    try:
        result = subprocess.run(
            ["curl", "-s", "https://news.ycombinator.com/"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return findings

        html = result.stdout

        # Basic parsing for HN items (this is crude but fast)
        # Look for patterns like: <a href="..." class="titleline">Title</a>
        import re

        # Extract all titleline links
        pattern = r'<span class="titleline"><a href="([^"]+)">([^<]+)</a>'
        matches = re.findall(pattern, html)

        seen = load_seen_items()

        for url, title in matches[:30]:  # Top 30 items
            # Check if relevant
            title_lower = title.lower()
            if any(topic.lower() in title_lower for topic in TOPICS + COMPETITORS):
                # Try to extract item ID
                item_id = f"hn_{hash(url + title)}"
                if item_id not in seen["hn_ids"]:
                    findings.append({
                        "source": "HackerNews",
                        "title": title,
                        "url": url if url.startswith("http") else f"https://news.ycombinator.com/{url}",
                        "id": item_id
                    })
                    seen["hn_ids"].append(item_id)

        # Keep only last 1000 seen IDs
        seen["hn_ids"] = seen["hn_ids"][-1000:]
        save_seen_items(seen)

    except Exception as e:
        print(f"Error checking HN: {e}", file=sys.stderr)

    return findings


def search_github_trending():
    """Check GitHub trending for AI/agent repos."""
    findings = []

    try:
        # Use gh CLI to search for trending repos in AI/agents space
        # Search for repos created/updated recently
        searches = [
            "autonomous agents",
            "AI agents framework",
            "Claude Code",
            "agent orchestration",
        ]

        seen = load_seen_items()

        for query in searches:
            result = subprocess.run(
                [
                    "gh", "search", "repos",
                    query,
                    "--sort", "updated",
                    "--limit", "5",
                    "--json", "fullName,description,url,stargazersCount,updatedAt"
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode != 0:
                continue

            repos = json.loads(result.stdout)

            for repo in repos:
                repo_id = f"gh_{repo['fullName']}"

                # Check if we've seen this recently
                if repo_id not in seen["github_repos"]:
                    # Check if it's interesting (stars, keywords)
                    desc = (repo.get("description") or "").lower()
                    name = repo["fullName"].lower()

                    if (repo["stargazersCount"] > 100 or
                        any(comp.lower() in (desc + name) for comp in COMPETITORS) or
                        any(topic.lower() in desc for topic in TOPICS)):

                        findings.append({
                            "source": "GitHub",
                            "title": f"{repo['fullName']} ({repo['stargazersCount']} stars)",
                            "description": repo.get("description", "No description"),
                            "url": repo["url"],
                            "id": repo_id,
                            "updated": repo["updatedAt"],
                        })
                        seen["github_repos"].append(repo_id)

        # Keep only last 1000 seen repos
        seen["github_repos"] = seen["github_repos"][-1000:]
        save_seen_items(seen)

    except Exception as e:
        print(f"Error checking GitHub: {e}", file=sys.stderr)

    return findings


def check_competitor_releases():
    """Check for recent releases from known competitors."""
    findings = []

    try:
        competitors = [
            "aider-ai/aider",
            "OpenClaw/openclaw",
            "langchain-ai/langchain",
            "crewAIInc/crewAI",
        ]

        for repo in competitors:
            result = subprocess.run(
                [
                    "gh", "release", "list",
                    "--repo", repo,
                    "--limit", "1",
                    "--json", "tagName,name,publishedAt,url"
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                continue

            releases = json.loads(result.stdout)
            if releases:
                release = releases[0]
                # Check if published in last 7 days
                from datetime import datetime, timedelta
                pub_date = datetime.fromisoformat(release["publishedAt"].replace("Z", "+00:00"))
                if datetime.now(pub_date.tzinfo) - pub_date < timedelta(days=7):
                    findings.append({
                        "source": "Competitor Release",
                        "title": f"{repo} {release['tagName']}",
                        "description": release.get("name", ""),
                        "url": release["url"],
                        "id": f"rel_{repo}_{release['tagName']}",
                    })

    except Exception as e:
        print(f"Error checking releases: {e}", file=sys.stderr)

    return findings


def generate_digest(findings):
    """Generate markdown digest of findings."""
    if not findings:
        return None

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    digest = f"""# Intelligence Digest - {date_str} {time_str}

{len(findings)} new items found

"""

    # Group by source
    by_source = {}
    for item in findings:
        source = item["source"]
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)

    for source, items in sorted(by_source.items()):
        digest += f"\n## {source}\n\n"
        for item in items:
            digest += f"**{item['title']}**\n"
            if "description" in item:
                digest += f"{item['description']}\n"
            digest += f"{item['url']}\n\n"

    return digest


def send_email_summary(digest, count):
    """Send email to owner if findings are significant."""
    subject = f"Intelligence: {count} new items"
    body = f"""VSM Proactive Monitor found {count} interesting developments:

{digest}

---
Full digest saved to state/intelligence/
"""

    try:
        subprocess.run(
            ["python3", str(VSM_ROOT / "core" / "comm.py"), subject, body],
            check=True,
            timeout=10,
        )
        print(f"Email sent: {count} items")
    except Exception as e:
        print(f"Error sending email: {e}", file=sys.stderr)


def main():
    """Run the proactive monitor."""
    print(f"VSM Proactive Monitor - {datetime.now().isoformat()}")

    # Gather intelligence
    print("Checking HackerNews...")
    hn_findings = search_hn_front_page()

    print("Checking GitHub trending...")
    gh_findings = search_github_trending()

    print("Checking competitor releases...")
    release_findings = check_competitor_releases()

    all_findings = hn_findings + gh_findings + release_findings

    print(f"Found {len(all_findings)} new items")

    if not all_findings:
        print("No new intelligence to report")
        return

    # Generate digest
    digest = generate_digest(all_findings)

    # Save to file
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    digest_file = STATE_DIR / f"{date_str}.md"

    # Append to daily digest
    mode = "a" if digest_file.exists() else "w"
    with open(digest_file, mode) as f:
        if mode == "a":
            f.write("\n---\n\n")
        f.write(digest)

    print(f"Digest saved to {digest_file}")

    # Send email if significant (>=3 items)
    if len(all_findings) >= 3:
        send_email_summary(digest, len(all_findings))

    # Update last check time
    seen = load_seen_items()
    seen["last_check"] = now.isoformat()
    save_seen_items(seen)


if __name__ == "__main__":
    main()
