#!/usr/bin/env python3
"""
VSM Web Dashboard Server
Serves static files and provides API endpoints for VSM status
"""

import json
import os
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
        elif self.path == '/api/logs':
            self.serve_logs()
        else:
            # Serve static files
            super().do_GET()

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
                                'id': task_file.stem,
                                'title': task_data.get('title', 'No title'),
                                'priority': task_data.get('priority', 0),
                                'created': task_data.get('created', '')
                            })
                    except Exception as e:
                        print(f"Error reading task {task_file}: {e}")

            # Sort by priority (highest first) then by ID
            tasks.sort(key=lambda t: (-t['priority'], t['id']))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(tasks).encode())
        except Exception as e:
            self.send_error(500, f"Error reading tasks: {e}")

    def serve_logs(self):
        """Serve recent log entries"""
        try:
            logs = []
            if LOGS_DIR.exists():
                # Get the 5 most recent log files
                log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)[:5]
                for log_file in log_files:
                    try:
                        with open(log_file, 'r') as f:
                            # Read last 20 lines of each log file
                            lines = f.readlines()
                            for line in lines[-20:]:
                                logs.append({
                                    'file': log_file.name,
                                    'content': line.strip()
                                })
                    except Exception as e:
                        print(f"Error reading log {log_file}: {e}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(logs[-50:]).encode())  # Return last 50 entries
        except Exception as e:
            self.send_error(500, f"Error reading logs: {e}")

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
