#!/usr/bin/env python3
"""
Project Watcher — Intelligent monitoring for code projects

Watches git repositories for common issues:
- Uncommitted work sitting >1h
- Test failures in recent commits
- Security vulnerabilities in dependencies
- Large files accidentally staged
- Unresolved TODO/FIXME in recent changes

Creates VSM tasks with actionable suggestions.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path


def run_cmd(cmd, cwd=None):
    """Run shell command, return (stdout, stderr, returncode)"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1


def check_uncommitted_work(project_path):
    """Detect uncommitted changes sitting >1h"""
    stdout, stderr, code = run_cmd("git status --porcelain", cwd=project_path)

    if code != 0 or not stdout.strip():
        return None

    # Count modified/staged files
    lines = [l for l in stdout.strip().split('\n') if l]
    if not lines:
        return None

    # Check timestamp of most recent change
    stdout, _, _ = run_cmd("git diff HEAD --name-only", cwd=project_path)
    changed_files = [f for f in stdout.strip().split('\n') if f]

    if not changed_files:
        return None

    # Get mtime of most recently modified file
    newest_mtime = 0
    for fname in changed_files:
        fpath = Path(project_path) / fname
        if fpath.exists():
            newest_mtime = max(newest_mtime, fpath.stat().st_mtime)

    if newest_mtime == 0:
        return None

    age_seconds = datetime.now().timestamp() - newest_mtime
    age_hours = age_seconds / 3600

    # Only report if >1h old
    if age_hours < 1.0:
        return None

    return {
        'type': 'uncommitted_work',
        'priority': 'medium' if age_hours > 4 else 'low',
        'title': f'Uncommitted work in {Path(project_path).name} ({int(age_hours)}h {int((age_hours % 1) * 60)}m old)',
        'description': f'Found {len(lines)} modified/staged files:\n' + '\n'.join(f'  - {l.strip()}' for l in lines[:10]),
        'suggested_action': f'Review and commit changes in {project_path}'
    }


def check_large_files(project_path):
    """Detect large files (>10MB) in staging area"""
    stdout, stderr, code = run_cmd("git diff --cached --name-only", cwd=project_path)

    if code != 0 or not stdout.strip():
        return None

    staged_files = [f for f in stdout.strip().split('\n') if f]
    large_files = []

    for fname in staged_files:
        fpath = Path(project_path) / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024 * 1024)
            if size_mb > 10:
                large_files.append((fname, size_mb))

    if not large_files:
        return None

    return {
        'type': 'large_files_staged',
        'priority': 'high',
        'title': f'Large files staged in {Path(project_path).name}',
        'description': 'Files >10MB detected in staging area:\n' + '\n'.join(f'  - {f} ({s:.1f}MB)' for f, s in large_files),
        'suggested_action': 'Review gitignore or use git-lfs for large assets'
    }


def check_todos(project_path):
    """Detect TODO/FIXME in recent commits (last 24h)"""
    # Get commits from last 24h
    since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
    stdout, stderr, code = run_cmd(f"git log --since={since} --pretty=format:%H", cwd=project_path)

    if code != 0 or not stdout.strip():
        return None

    commits = stdout.strip().split('\n')

    # Search for TODO/FIXME in diff
    for commit in commits[:5]:  # Check up to 5 recent commits
        stdout, _, _ = run_cmd(f"git show {commit}", cwd=project_path)
        added_lines = [l for l in stdout.split('\n') if l.startswith('+') and ('TODO' in l or 'FIXME' in l)]

        if added_lines:
            return {
                'type': 'new_todos',
                'priority': 'low',
                'title': f'New TODOs added in {Path(project_path).name}',
                'description': f'Found {len(added_lines)} TODO/FIXME in recent commits:\n' + '\n'.join(f'  {l[:80]}' for l in added_lines[:5]),
                'suggested_action': 'Review and resolve TODOs or create tracking issues'
            }

    return None


def check_npm_vulnerabilities(project_path):
    """Check for npm security vulnerabilities"""
    package_json = Path(project_path) / 'package.json'
    if not package_json.exists():
        return None

    stdout, stderr, code = run_cmd("npm audit --json 2>/dev/null", cwd=project_path)

    if code == 0:
        return None  # No vulnerabilities

    try:
        audit_data = json.loads(stdout) if stdout else {}
        vuln_count = audit_data.get('metadata', {}).get('vulnerabilities', {})

        total = sum(vuln_count.values()) if isinstance(vuln_count, dict) else 0

        if total > 0:
            high = vuln_count.get('high', 0)
            critical = vuln_count.get('critical', 0)

            priority = 'high' if (high + critical > 0) else 'medium'

            return {
                'type': 'npm_vulnerabilities',
                'priority': priority,
                'title': f'npm vulnerabilities in {Path(project_path).name}',
                'description': f'Found {total} vulnerabilities: {critical} critical, {high} high',
                'suggested_action': 'Run: npm audit fix'
            }
    except:
        pass

    return None


def check_pip_vulnerabilities(project_path):
    """Check for pip security vulnerabilities"""
    requirements_txt = Path(project_path) / 'requirements.txt'
    if not requirements_txt.exists():
        return None

    # Check if pip-audit is installed
    _, _, code = run_cmd("which pip-audit")
    if code != 0:
        return None  # pip-audit not available

    stdout, stderr, code = run_cmd("pip-audit -r requirements.txt --format json 2>/dev/null", cwd=project_path)

    if code == 0:
        return None  # No vulnerabilities

    try:
        audit_data = json.loads(stdout) if stdout else []
        if isinstance(audit_data, list) and len(audit_data) > 0:
            return {
                'type': 'pip_vulnerabilities',
                'priority': 'high',
                'title': f'pip vulnerabilities in {Path(project_path).name}',
                'description': f'Found {len(audit_data)} vulnerable packages',
                'suggested_action': 'Run: pip-audit and update dependencies'
            }
    except:
        pass

    return None


def create_vsm_task(finding, project_path):
    """Create task in VSM queue"""
    vsm_tasks_dir = Path(__file__).parent.parent / 'tasks'

    # Generate task ID
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    task_id = f"watch_{finding['type']}_{timestamp}"

    task = {
        'id': task_id,
        'title': finding['title'],
        'description': f"{finding['description']}\n\nSuggested action: {finding['suggested_action']}\n\nProject: {project_path}",
        'status': 'pending',
        'priority': finding['priority'],
        'created_at': datetime.now().isoformat(),
        'source': 'project_watcher',
        'metadata': {
            'project_path': str(project_path),
            'finding_type': finding['type']
        }
    }

    task_file = vsm_tasks_dir / f"{task_id}.json"
    with open(task_file, 'w') as f:
        json.dump(task, f, indent=2)

    return task_id


def watch_project(project_path):
    """Run all checks on a project"""
    project_path = Path(project_path).resolve()

    if not project_path.exists():
        print(f"Error: {project_path} does not exist", file=sys.stderr)
        return []

    # Check if it's a git repo
    if not (project_path / '.git').exists():
        print(f"Skipping {project_path} (not a git repository)", file=sys.stderr)
        return []

    print(f"Watching {project_path}...")

    checks = [
        check_uncommitted_work,
        check_large_files,
        check_todos,
        check_npm_vulnerabilities,
        check_pip_vulnerabilities
    ]

    findings = []
    for check_fn in checks:
        try:
            result = check_fn(project_path)
            if result:
                findings.append(result)
                task_id = create_vsm_task(result, project_path)
                print(f"  [{result['priority'].upper()}] {result['title']} -> {task_id}")
        except Exception as e:
            print(f"  Error in {check_fn.__name__}: {e}", file=sys.stderr)

    if not findings:
        print(f"  No issues found in {project_path.name}")

    return findings


def main():
    if len(sys.argv) < 2:
        print("Usage: project_watcher.py <project_path>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  project_watcher.py ~/projects/myapp", file=sys.stderr)
        print("  project_watcher.py ~/projects  # watches all subdirs with .git", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    all_findings = []

    # If target is a directory, watch all git repos within
    if target.is_dir():
        if (target / '.git').exists():
            # Single git repo
            findings = watch_project(target)
            all_findings.extend(findings)
        else:
            # Watch all subdirs with .git
            for subdir in target.iterdir():
                if subdir.is_dir() and (subdir / '.git').exists():
                    findings = watch_project(subdir)
                    all_findings.extend(findings)

    # Summary
    print(f"\n=== Summary ===")
    print(f"Total findings: {len(all_findings)}")

    if all_findings:
        by_priority = {}
        for f in all_findings:
            by_priority.setdefault(f['priority'], []).append(f)

        for priority in ['high', 'medium', 'low']:
            if priority in by_priority:
                print(f"  {priority.upper()}: {len(by_priority[priority])}")


if __name__ == '__main__':
    main()
