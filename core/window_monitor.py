#!/usr/bin/env python3
"""
Window Monitor — Detect active window and app context

Provides focus-aware task prioritization for laptop installations.
Detects which app the user is actively working in to intelligently
adjust task priorities based on context.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


def _get_active_window_x11() -> Optional[Tuple[str, str]]:
    """Get active window using X11 tools (Linux)."""
    try:
        # Get active window ID
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        window_id = result.stdout.strip()

        # Get window name
        result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        window_title = result.stdout.strip()

        # Get window class (app name)
        result = subprocess.run(
            ["xdotool", "getwindowclassname", window_id],
            capture_output=True,
            text=True,
            timeout=5
        )

        app_name = result.stdout.strip() if result.returncode == 0 else "unknown"

        return (app_name, window_title)

    except Exception:
        return None


def _get_active_window_macos() -> Optional[Tuple[str, str]]:
    """Get active window using AppleScript (macOS)."""
    try:
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            set frontWindow to ""
            try
                set frontWindow to name of front window of application process frontApp
            end try
            return frontApp & "|" & frontWindow
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        output = result.stdout.strip()
        parts = output.split("|", 1)

        if len(parts) == 2:
            return (parts[0], parts[1])
        else:
            return (parts[0], "")

    except Exception:
        return None


def _extract_project_path(app_name: str, window_title: str) -> Optional[str]:
    """Extract project path from window title if it's a code editor."""
    # VS Code pattern: "filename - project_name - Visual Studio Code"
    if "code" in app_name.lower() or "vscode" in app_name.lower():
        parts = window_title.split(" - ")
        if len(parts) >= 2:
            # Second-to-last part is usually the project name/path
            project_hint = parts[-2]
            # Try to find this directory in common project locations
            for base in [Path.home() / "projects", Path.home() / "code", Path.home()]:
                candidate = base / project_hint
                if candidate.exists() and candidate.is_dir():
                    return str(candidate)

    # Sublime Text, Atom, etc.
    if any(x in app_name.lower() for x in ["sublime", "atom", "emacs", "vim", "neovim"]):
        # Try to extract path from window title
        if "/" in window_title or "\\" in window_title:
            # Looks like a path
            parts = window_title.split()
            for part in parts:
                if "/" in part or "\\" in part:
                    candidate = Path(part)
                    if candidate.exists():
                        if candidate.is_file():
                            return str(candidate.parent)
                        else:
                            return str(candidate)

    return None


def get_active_window_context() -> Optional[dict]:
    """
    Get active window context.

    Returns:
        dict with keys:
            - app_name: str (e.g., "Code", "Firefox")
            - window_title: str (window title text)
            - project_path: Optional[str] (if IDE with detectable project)
        Or None if detection fails/unavailable.
    """
    # Detect platform
    platform = sys.platform

    if platform == "darwin":
        result = _get_active_window_macos()
    elif platform == "linux":
        result = _get_active_window_x11()
    else:
        # Unsupported platform
        return None

    if not result:
        return None

    app_name, window_title = result

    # Try to extract project path
    project_path = _extract_project_path(app_name, window_title)

    return {
        "app_name": app_name,
        "window_title": window_title,
        "project_path": project_path
    }


def is_available() -> bool:
    """Check if window monitoring is available on this system."""
    platform = sys.platform

    if platform == "darwin":
        # macOS: osascript should be available by default
        try:
            result = subprocess.run(
                ["which", "osascript"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    elif platform == "linux":
        # Linux: check for xdotool
        try:
            result = subprocess.run(
                ["which", "xdotool"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    return False


def main():
    """CLI test: show current active window context."""
    if not is_available():
        print("Window monitoring not available on this system.", file=sys.stderr)
        print("Linux: install xdotool (apt install xdotool)", file=sys.stderr)
        print("macOS: osascript should be available by default", file=sys.stderr)
        sys.exit(1)

    context = get_active_window_context()

    if context:
        print(f"App: {context['app_name']}")
        print(f"Window: {context['window_title']}")
        if context['project_path']:
            print(f"Project: {context['project_path']}")
        else:
            print("Project: (not detected)")
    else:
        print("Failed to detect active window.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
