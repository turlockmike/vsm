#!/usr/bin/env python3
"""
VSM Dashboard Server — Web interface for the Viable System Machine
Serves on localhost:7777 with built-in HTTP server (no external dependencies)
"""

import http.server
import json
import os
import glob
import socketserver
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Paths
VSM_ROOT = Path(__file__).parent.parent.resolve()
STATE_FILE = VSM_ROOT / 'state' / 'state.json'
TASKS_DIR = VSM_ROOT / 'sandbox' / 'tasks'
LOGS_DIR = VSM_ROOT / 'state' / 'logs'

PORT = 7777


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for VSM dashboard"""

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/':
            self.serve_dashboard()
        elif path == '/api/state':
            self.serve_state()
        elif path == '/api/tasks':
            self.serve_tasks()
        elif path == '/api/logs':
            n = int(query.get('n', ['10'])[0])
            self.serve_logs(n)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/tasks':
            self.create_task()
        else:
            self.send_error(404, "Not Found")

    def serve_dashboard(self):
        """Serve the main HTML dashboard"""
        html = self.get_dashboard_html()
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_state(self):
        """Serve state.json as API endpoint"""
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            self.send_json_response(state)
        except Exception as e:
            self.send_json_response({'error': str(e)}, status=500)

    def serve_tasks(self):
        """Serve task list as API endpoint"""
        try:
            task_files = sorted(glob.glob(str(TASKS_DIR / '*.json')))
            tasks = []
            for task_file in task_files:
                try:
                    with open(task_file, 'r') as f:
                        task = json.load(f)
                        tasks.append(task)
                except json.JSONDecodeError:
                    continue

            # Sort by priority, then by ID
            tasks.sort(key=lambda t: (t.get('priority', 999), t.get('id', '999')))
            self.send_json_response({'tasks': tasks})
        except Exception as e:
            self.send_json_response({'error': str(e)}, status=500)

    def serve_logs(self, n=10):
        """Serve recent log entries as API endpoint"""
        try:
            # Filter out heartbeat.log
            log_files = sorted(
                [f for f in glob.glob(str(LOGS_DIR / '*.log')) if not f.endswith('heartbeat.log')],
                key=os.path.getmtime, reverse=True
            )[:n]

            logs = []
            for log_file in log_files:
                try:
                    with open(log_file, 'r') as f:
                        log_data = json.load(f)
                        logs.append(log_data)
                except json.JSONDecodeError:
                    continue

            self.send_json_response({'logs': logs})
        except Exception as e:
            self.send_json_response({'error': str(e)}, status=500)

    def create_task(self):
        """Create a new task from POST request"""
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Get next task ID
            task_id = self.get_next_task_id()

            # Create task
            task = {
                "id": task_id,
                "priority": data.get('priority', 5),
                "title": data.get('title', 'Untitled task'),
                "description": data.get('description', data.get('title', 'No description')),
                "created": datetime.now().isoformat(timespec='seconds'),
                "status": "pending"
            }

            # Create filename from title (sanitized)
            filename_base = task['title'].lower()[:30].replace(' ', '_')
            filename_base = ''.join(c for c in filename_base if c.isalnum() or c == '_')
            filename = TASKS_DIR / f"{task_id}_{filename_base}.json"

            # Ensure tasks directory exists
            TASKS_DIR.mkdir(parents=True, exist_ok=True)

            # Write task file
            with open(filename, 'w') as f:
                json.dump(task, f, indent=2)

            self.send_json_response({'success': True, 'task': task})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)}, status=500)

    def get_next_task_id(self):
        """Find the next available task ID"""
        task_files = glob.glob(str(TASKS_DIR / '*.json'))
        if not task_files:
            return "001"

        max_id = 0
        for task_file in task_files:
            try:
                with open(task_file, 'r') as f:
                    task = json.load(f)
                    task_id = int(task.get('id', '0'))
                    max_id = max(max_id, task_id)
            except (json.JSONDecodeError, ValueError):
                continue

        return f"{max_id + 1:03d}"

    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_dashboard_html(self):
        """Generate dashboard HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VSM Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #333;
        }

        h1 {
            font-size: 2.5em;
            color: #4CAF50;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #888;
            font-size: 0.9em;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .panel {
            background: #252525;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
        }

        .panel h2 {
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #4CAF50;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #2a2a2a;
        }

        .metric:last-child {
            border-bottom: none;
        }

        .metric-label {
            color: #888;
        }

        .metric-value {
            font-weight: 600;
        }

        .status-good { color: #4CAF50; }
        .status-warn { color: #FFC107; }
        .status-bad { color: #f44336; }

        .task {
            background: #2a2a2a;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 12px;
            margin-bottom: 10px;
        }

        .task-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }

        .task-id {
            font-weight: 600;
            color: #4CAF50;
        }

        .task-priority {
            font-size: 0.85em;
            color: #888;
        }

        .task-title {
            margin-bottom: 5px;
        }

        .task-status {
            font-size: 0.85em;
            padding: 2px 8px;
            border-radius: 3px;
            display: inline-block;
        }

        .status-pending {
            background: #FFC107;
            color: #000;
        }

        .status-in_progress {
            background: #2196F3;
            color: #fff;
        }

        .status-done, .status-complete {
            background: #4CAF50;
            color: #fff;
        }

        .log-entry {
            background: #2a2a2a;
            border-left: 3px solid #4CAF50;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 4px;
        }

        .log-entry.failed {
            border-left-color: #f44336;
        }

        .log-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9em;
        }

        .log-timestamp {
            color: #4CAF50;
            font-weight: 600;
        }

        .log-mode {
            color: #888;
        }

        .log-summary {
            font-size: 0.9em;
            color: #ccc;
            white-space: pre-wrap;
            max-height: 100px;
            overflow: hidden;
        }

        form {
            margin-top: 15px;
        }

        input[type="text"],
        textarea {
            width: 100%;
            padding: 10px;
            background: #2a2a2a;
            border: 1px solid #444;
            border-radius: 4px;
            color: #e0e0e0;
            margin-bottom: 10px;
            font-family: inherit;
        }

        input[type="number"] {
            width: 80px;
            padding: 10px;
            background: #2a2a2a;
            border: 1px solid #444;
            border-radius: 4px;
            color: #e0e0e0;
            margin-bottom: 10px;
        }

        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }

        button:hover {
            background: #45a049;
        }

        .auto-refresh {
            color: #666;
            font-size: 0.85em;
            text-align: right;
        }

        .empty {
            color: #666;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }

        .full-width {
            grid-column: 1 / -1;
        }

        .form-row {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .form-row label {
            color: #888;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>VSM Dashboard</h1>
            <div class="subtitle">Viable System Machine — Real-time monitoring and control</div>
        </header>

        <div class="grid">
            <!-- System Health -->
            <div class="panel">
                <h2>System Health</h2>
                <div id="health-content">
                    <div class="empty">Loading...</div>
                </div>
            </div>

            <!-- Add Task -->
            <div class="panel">
                <h2>Add Task</h2>
                <form id="task-form" onsubmit="addTask(event)">
                    <input type="text" id="task-title" placeholder="Task title" required>
                    <textarea id="task-description" placeholder="Task description (optional)" rows="3"></textarea>
                    <div class="form-row">
                        <label for="task-priority">Priority:</label>
                        <input type="number" id="task-priority" value="5" min="1" max="10">
                        <button type="submit">Add Task</button>
                    </div>
                </form>
            </div>

            <!-- Task Queue -->
            <div class="panel full-width">
                <h2>Task Queue</h2>
                <div id="tasks-content">
                    <div class="empty">Loading...</div>
                </div>
            </div>

            <!-- Cycle Log Timeline -->
            <div class="panel full-width">
                <h2>Cycle Log Timeline</h2>
                <div id="logs-content">
                    <div class="empty">Loading...</div>
                </div>
            </div>
        </div>

        <div class="auto-refresh" id="last-update">
            Auto-refresh: every 30 seconds
        </div>
    </div>

    <script>
        // Fetch and display system health
        async function fetchHealth() {
            try {
                const response = await fetch('/api/state');
                const state = await response.json();

                const health = state.health || {};
                const html = `
                    <div class="metric">
                        <span class="metric-label">Cycle Count</span>
                        <span class="metric-value">${state.cycle_count || 0}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Criticality</span>
                        <span class="metric-value">${(state.criticality || 0).toFixed(2)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Last Action</span>
                        <span class="metric-value">${state.last_action || 'None'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Last Updated</span>
                        <span class="metric-value">${formatDate(state.updated)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Status</span>
                        <span class="metric-value ${state.last_result_success ? 'status-good' : 'status-bad'}">
                            ${state.last_result_success ? '✓ Success' : '✗ Failed'}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Disk Free</span>
                        <span class="metric-value">${(health.disk_free_gb || 0).toFixed(1)} GB</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Memory Available</span>
                        <span class="metric-value">${health.mem_available_mb || 0} MB</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Cron Status</span>
                        <span class="metric-value ${health.cron_installed ? 'status-good' : 'status-bad'}">
                            ${health.cron_installed ? '✓ Installed' : '✗ Not installed'}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Pending Tasks</span>
                        <span class="metric-value">${health.pending_tasks || 0}</span>
                    </div>
                `;

                document.getElementById('health-content').innerHTML = html;
            } catch (error) {
                document.getElementById('health-content').innerHTML = `<div class="empty status-bad">Error: ${error.message}</div>`;
            }
        }

        // Fetch and display tasks
        async function fetchTasks() {
            try {
                const response = await fetch('/api/tasks');
                const data = await response.json();
                const tasks = data.tasks || [];

                if (tasks.length === 0) {
                    document.getElementById('tasks-content').innerHTML = '<div class="empty">No tasks</div>';
                    return;
                }

                const html = tasks.map(task => `
                    <div class="task">
                        <div class="task-header">
                            <span class="task-id">#${task.id}</span>
                            <span class="task-priority">Priority: ${task.priority}</span>
                        </div>
                        <div class="task-title">${task.title}</div>
                        <div>
                            <span class="task-status status-${task.status}">${task.status}</span>
                        </div>
                    </div>
                `).join('');

                document.getElementById('tasks-content').innerHTML = html;
            } catch (error) {
                document.getElementById('tasks-content').innerHTML = `<div class="empty status-bad">Error: ${error.message}</div>`;
            }
        }

        // Fetch and display logs
        async function fetchLogs() {
            try {
                const response = await fetch('/api/logs?n=10');
                const data = await response.json();
                const logs = data.logs || [];

                if (logs.length === 0) {
                    document.getElementById('logs-content').innerHTML = '<div class="empty">No logs</div>';
                    return;
                }

                const html = logs.map(log => `
                    <div class="log-entry ${log.success ? '' : 'failed'}">
                        <div class="log-header">
                            <span class="log-timestamp">${log.success ? '✓' : '✗'} ${formatDate(log.timestamp)}</span>
                            <span class="log-mode">[${log.mode}] Cycle ${log.cycle || '?'}</span>
                        </div>
                        ${log.reason ? `<div style="color: #888; font-size: 0.85em; margin-bottom: 5px;">Reason: ${log.reason}</div>` : ''}
                        <div class="log-summary">${truncate(log.summary || 'No summary', 200)}</div>
                    </div>
                `).join('');

                document.getElementById('logs-content').innerHTML = html;
            } catch (error) {
                document.getElementById('logs-content').innerHTML = `<div class="empty status-bad">Error: ${error.message}</div>`;
            }
        }

        // Add a new task
        async function addTask(event) {
            event.preventDefault();

            const title = document.getElementById('task-title').value;
            const description = document.getElementById('task-description').value || title;
            const priority = parseInt(document.getElementById('task-priority').value);

            try {
                const response = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ title, description, priority })
                });

                const result = await response.json();

                if (result.success) {
                    // Clear form
                    document.getElementById('task-title').value = '';
                    document.getElementById('task-description').value = '';
                    document.getElementById('task-priority').value = '5';

                    // Refresh tasks
                    fetchTasks();
                    fetchHealth(); // Update pending tasks count
                } else {
                    alert('Error adding task: ' + result.error);
                }
            } catch (error) {
                alert('Error adding task: ' + error.message);
            }
        }

        // Utility functions
        function formatDate(dateStr) {
            if (!dateStr) return 'Unknown';
            return dateStr.replace('T', ' ').substring(0, 19);
        }

        function truncate(str, length) {
            if (!str) return '';
            if (str.length <= length) return str;
            return str.substring(0, length) + '...';
        }

        // Initial load
        function refresh() {
            fetchHealth();
            fetchTasks();
            fetchLogs();
            document.getElementById('last-update').innerHTML = `Last updated: ${new Date().toLocaleTimeString()} — Auto-refresh: every 30 seconds`;
        }

        // Auto-refresh every 30 seconds
        refresh();
        setInterval(refresh, 30000);
    </script>
</body>
</html>
"""

    def log_message(self, format, *args):
        """Override to customize logging"""
        # Simple logging to stdout
        print(f"[{self.log_date_time_string()}] {format % args}")


def start_server():
    """Start the dashboard server"""
    handler = DashboardHandler

    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"VSM Dashboard running at http://localhost:{PORT}")
        print(f"Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == '__main__':
    start_server()
