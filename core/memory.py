#!/usr/bin/env python3
"""
VSM Persistent Memory System

Structured knowledge base that persists across days and projects.
Files are git-tracked, token-budgeted, and optimized for System 5 context.
"""

from pathlib import Path
from datetime import datetime

VSM_ROOT = Path(__file__).parent.parent
MEMORY_DIR = VSM_ROOT / "state" / "memory"

# Memory files and their token budgets
MEMORY_FILES = {
    "projects.md": 3000,      # ~750 tokens
    "decisions.md": 3000,     # ~750 tokens
    "preferences.md": 2000,   # ~500 tokens
}


def load_memory(max_bytes=8000):
    """Load persistent memory files within token budget.

    Returns formatted string ready for System 5 prompt injection.
    Total target: ~8KB (~2000 tokens).
    """
    if not MEMORY_DIR.exists():
        return ""

    sections = []
    total_bytes = 0

    for filename, byte_cap in MEMORY_FILES.items():
        filepath = MEMORY_DIR / filename
        if not filepath.exists():
            continue

        content = filepath.read_text().strip()
        if not content:
            continue

        # Truncate if over budget (tail only, most recent content)
        if len(content) > byte_cap:
            content = "[...truncated...]\n" + content[-byte_cap:]

        sections.append(f"### {filename}\n{content}")
        total_bytes += len(content)

        # Stop if we've exceeded total budget
        if total_bytes > max_bytes:
            break

    if not sections:
        return ""

    header = "## Persistent Memory\n"
    return header + "\n\n".join(sections)


def append_to_memory(filename, content):
    """Append content to a memory file.

    Args:
        filename: One of MEMORY_FILES keys (e.g., "decisions.md")
        content: String to append (should include timestamp/context)

    Example:
        append_to_memory("preferences.md",
            "2026-02-14: Owner prefers terse commit messages (from git log)")
    """
    if filename not in MEMORY_FILES:
        raise ValueError(f"Invalid memory file: {filename}. Must be one of {list(MEMORY_FILES.keys())}")

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    filepath = MEMORY_DIR / filename

    # Ensure content ends with newline
    if not content.endswith("\n"):
        content += "\n"

    with open(filepath, "a") as f:
        f.write(content)


def get_memory_stats():
    """Return memory system statistics for health checks."""
    if not MEMORY_DIR.exists():
        return {"files": 0, "total_bytes": 0}

    stats = {
        "files": 0,
        "total_bytes": 0,
        "by_file": {}
    }

    for filename in MEMORY_FILES.keys():
        filepath = MEMORY_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            stats["files"] += 1
            stats["total_bytes"] += size
            stats["by_file"][filename] = size

    return stats


def init_memory_files():
    """Initialize memory files if they don't exist.

    Called by controller on first run to ensure structure exists.
    Safe to call multiple times (won't overwrite existing files).
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # Create index if missing
    index_file = MEMORY_DIR / "index.md"
    if not index_file.exists():
        index_file.write_text("""# VSM Memory Index

Quick lookup for System 5's persistent knowledge base.

## Core Files
- `projects.md` — Codebase structure, file purposes, what exists
- `decisions.md` — Architectural decisions, why things are built this way
- `preferences.md` — Owner preferences learned over time

Last updated: """ + datetime.now().strftime("%Y-%m-%d") + "\n")

    # Ensure all memory files exist (create empty if missing)
    for filename in MEMORY_FILES.keys():
        filepath = MEMORY_DIR / filename
        if not filepath.exists():
            filepath.write_text(f"# {filename.replace('.md', '').title()}\n\n")


if __name__ == "__main__":
    # Test/demo
    init_memory_files()
    print("Memory system initialized")
    print(f"Stats: {get_memory_stats()}")
    print("\nMemory content preview:")
    print(load_memory()[:500])
