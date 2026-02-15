#!/usr/bin/env python3
"""
VSM Web Dashboard Server
Serves static files and provides API endpoints for VSM status
"""

import json
import os
import glob
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# VSM root directory
VSM_ROOT = Path(__file__).parent.parent
STATE_FILE = VSM_ROOT / "state" / "state.json"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
LOGS_DIR = VSM_ROOT / "state" / "logs"


class VSMHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for VSM dashboard"""

    def __init__(self, *args, **kwargs):
        # Serve files from the web directory
        super().__init__(*args, directory=str(VSM_ROOT / "web"), **kwargs)

    def do_GET(self):
        """Handle GET requests"""

        # API endpoints
        if self.path == '/api/state':
            self.serve_state()
        elif self.path == '/api/tasks':
            self.serve_tasks()
        elif self.path.startswith('/api/logs'):
            self.serve_logs()
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/tasks':
            self.create_task()
        else:
            self.send_error(404, "Not Found")

    def serve_state(self):
        """Serve state.json"""
        try:
            with open(STATE_FILE, 'r') as f:
                state_data = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(state_data.encode())
        except Exception as e:
            self.send_error(500, f"Error reading state: {e}")

    def serve_tasks(self):
        """Serve list of pending tasks"""
        try:
            tasks = []
            if TASKS_DIR.exists():
                for task_file in sorted(TASKS_DIR.glob("*.json")):
                    try:
                        with open(task_file, 'r') as f:
                            task_data = json.load(f)
                            tasks.append({
                                'id': task_data.get('id', task_file.stem),
                                'title': task_data.get('title', 'No title'),
                                'priority': task_data.get('priority', 0),
                                'status': task_data.get('status', 'pending'),
                                'created': task_data.get('created', '')
                            })
                    except Exception as e:
                        print(f"Error reading task {task_file}: {e}")

            # Sort by priority (lowest number = highest priority) then by ID
            tasks.sort(key=lambda t: (t.get('priority', 999), t.get('id', '999')))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'tasks': tasks}).encode())
        except Exception as e:
            self.send_error(500, f"Error reading tasks: {e}")

    def serve_logs(self):
        """Serve recent log entries"""
        try:
            logs = []
            if LOGS_DIR.exists():
                # Filter out heartbeat.log and get the most recent cycle logs
                log_files = sorted(
                    [f for f in LOGS_DIR.glob("*.log") if f.name != 'heartbeat.log'],
                    key=os.path.getmtime, reverse=True
                )[:10]

                for log_file in log_files:
                    try:
                        with open(log_file, 'r') as f:
                            log_data = json.load(f)
                            logs.append(log_data)
                    except json.JSONDecodeError:
                        # Skip files that aren't JSON
                        continue
                    except Exception as e:
                        print(f"Error reading log {log_file}: {e}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'logs': logs}).encode())
        except Exception as e:
            self.send_error(500, f"Error reading logs: {e}")

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

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'task': task}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())

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

    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[VSM Dashboard] {self.address_string()} - {format % args}")


def run_server(port=8090):
    """Run the VSM dashboard server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, VSMHandler)
    print(f"VSM Dashboard Server running on port {port}")
    print(f"Serving from: {VSM_ROOT / 'web'}")
    print(f"State file: {STATE_FILE}")
    print(f"Tasks dir: {TASKS_DIR}")
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
