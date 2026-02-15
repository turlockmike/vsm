#!/usr/bin/env python3
"""
VSM Web Dashboard Server
Serves static files and provides API endpoints for VSM status
"""

import json
import os
import glob
import time
import threading
import subprocess
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs

# VSM root directory
VSM_ROOT = Path(__file__).parent.parent
STATE_FILE = VSM_ROOT / "state" / "state.json"
TASKS_DIR = VSM_ROOT / "sandbox" / "tasks"
LOGS_DIR = VSM_ROOT / "state" / "logs"
OUTBOX_DIR = VSM_ROOT / "sandbox" / "outbox"
CHAT_HISTORY_FILE = VSM_ROOT / "state" / "chat_history.json"

# Track state file modification time for SSE
last_state_mtime = 0


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
        elif self.path == '/api/mcp':
            self.serve_mcp()
        elif self.path == '/api/events':
            self.serve_events()
        elif self.path == '/api/chat/history':
            self.serve_chat_history()
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/tasks':
            self.create_task()
        elif self.path == '/api/command':
            self.handle_command()
        elif self.path == '/api/chat':
            self.handle_chat()
        else:
            self.send_error(404, "Not Found")

    def do_PUT(self):
        """Handle PUT requests"""
        if self.path.startswith('/api/tasks/'):
            self.update_task()
        else:
            self.send_error(404, "Not Found")

    def do_DELETE(self):
        """Handle DELETE requests"""
        if self.path.startswith('/api/tasks/'):
            self.delete_task()
        else:
            self.send_error(404, "Not Found")

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

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
                                'description': task_data.get('description', ''),
                                'priority': task_data.get('priority', 0),
                                'status': task_data.get('status', 'pending'),
                                'created': task_data.get('created', ''),
                                'filename': task_file.name
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

    def serve_mcp(self):
        """Serve MCP server configuration"""
        try:
            mcp_file = VSM_ROOT / ".mcp.json"
            servers = {}
            if mcp_file.exists():
                config = json.loads(mcp_file.read_text())
                for name, cfg in config.get("mcpServers", {}).items():
                    servers[name] = {
                        "command": cfg.get("command", "").split("/")[-1],
                        "status": "configured",
                    }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"servers": servers}).encode())
        except Exception as e:
            self.send_error(500, f"Error reading MCP config: {e}")

    def serve_events(self):
        """Serve Server-Sent Events for state updates"""
        global last_state_mtime

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            # Send initial state
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    state_data = f.read()
                self.wfile.write(f"event: state\ndata: {state_data}\n\n".encode())
                self.wfile.flush()
                last_state_mtime = os.path.getmtime(STATE_FILE)

            # Keep connection alive and send updates
            while True:
                time.sleep(2)  # Check every 2 seconds

                if STATE_FILE.exists():
                    current_mtime = os.path.getmtime(STATE_FILE)
                    if current_mtime > last_state_mtime:
                        with open(STATE_FILE, 'r') as f:
                            state_data = f.read()
                        self.wfile.write(f"event: state\ndata: {state_data}\n\n".encode())
                        self.wfile.flush()
                        last_state_mtime = current_mtime
                else:
                    # Send heartbeat to keep connection alive
                    self.wfile.write(": heartbeat\n\n".encode())
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected
            pass

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

    def update_task(self):
        """Update an existing task"""
        try:
            # Extract task ID from path
            task_id = self.path.split('/')[-1]

            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Find the task file
            task_file = None
            if TASKS_DIR.exists():
                for tf in TASKS_DIR.glob(f"{task_id}_*.json"):
                    task_file = tf
                    break

            if not task_file or not task_file.exists():
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Task not found'}).encode())
                return

            # Read existing task
            with open(task_file, 'r') as f:
                task = json.load(f)

            # Update fields
            if 'title' in data:
                task['title'] = data['title']
            if 'description' in data:
                task['description'] = data['description']
            if 'priority' in data:
                task['priority'] = data['priority']
            if 'status' in data:
                task['status'] = data['status']

            # Write updated task
            with open(task_file, 'w') as f:
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

    def delete_task(self):
        """Delete a task"""
        try:
            # Extract task ID from path
            task_id = self.path.split('/')[-1]

            # Find and delete the task file
            deleted = False
            if TASKS_DIR.exists():
                for task_file in TASKS_DIR.glob(f"{task_id}_*.json"):
                    task_file.unlink()
                    deleted = True
                    break

            if deleted:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Task not found'}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())

    def handle_command(self):
        """Handle command interface requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            command = data.get('command', '').strip()
            output = ""
            success = True

            if command.startswith('task add '):
                # Extract title from command
                title = command[9:].strip()
                if title:
                    task_id = self.get_next_task_id()
                    task = {
                        "id": task_id,
                        "priority": 5,
                        "title": title,
                        "description": title,
                        "created": datetime.now().isoformat(timespec='seconds'),
                        "status": "pending"
                    }
                    filename_base = title.lower()[:30].replace(' ', '_')
                    filename_base = ''.join(c for c in filename_base if c.isalnum() or c == '_')
                    filename = TASKS_DIR / f"{task_id}_{filename_base}.json"
                    TASKS_DIR.mkdir(parents=True, exist_ok=True)
                    with open(filename, 'w') as f:
                        json.dump(task, f, indent=2)
                    output = f"Task #{task_id} created: {title}"
                else:
                    output = "Error: task title required"
                    success = False

            elif command == 'task list':
                tasks = []
                if TASKS_DIR.exists():
                    for task_file in sorted(TASKS_DIR.glob("*.json")):
                        try:
                            with open(task_file, 'r') as f:
                                task_data = json.load(f)
                                tasks.append(f"#{task_data.get('id', '?')} [P{task_data.get('priority', '?')}] {task_data.get('title', 'No title')}")
                        except:
                            pass
                if tasks:
                    output = '\n'.join(tasks)
                else:
                    output = "No pending tasks"

            elif command == 'status':
                output = "Status refreshed"

            elif command.startswith('email '):
                # Parse email command: email <subject> | <body>
                parts = command[6:].split('|', 1)
                if len(parts) == 2:
                    subject = parts[0].strip()
                    body = parts[1].strip()

                    # Create outbox directory if needed
                    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

                    # Write email file
                    email_data = {
                        "to": "owner",
                        "subject": subject,
                        "body": body,
                        "created": datetime.now().isoformat(timespec='seconds')
                    }
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    email_file = OUTBOX_DIR / f"{timestamp}_email.json"
                    with open(email_file, 'w') as f:
                        json.dump(email_data, f, indent=2)

                    output = f"Email queued: {subject}"
                else:
                    output = "Error: email format is 'email <subject> | <body>'"
                    success = False

            else:
                output = f"Unknown command: {command}\nAvailable: task add <title>, task list, status, email <subject> | <body>"
                success = False

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': success, 'output': output}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'output': f"Error: {str(e)}"}).encode())

    def serve_chat_history(self):
        """Serve chat history"""
        try:
            if CHAT_HISTORY_FILE.exists():
                with open(CHAT_HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            else:
                history = {"messages": []}

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(history).encode())
        except Exception as e:
            self.send_error(500, f"Error reading chat history: {e}")

    def handle_chat(self):
        """Handle chat interface requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            message = data.get('message', '').strip()
            if not message:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'response': 'Empty message'}).encode())
                return

            # Build prompt for Claude
            prompt = f"You are VSM, an autonomous AI system. The user is your owner asking a question via the web dashboard. Be concise and helpful. Their message: {message}"

            # Call claude CLI
            try:
                result = subprocess.run(
                    ['claude', '-p', prompt, '--max-turns', '3'],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(VSM_ROOT)
                )

                if result.returncode == 0:
                    response = result.stdout.strip()
                    if not response:
                        response = "VSM processed your message but produced no output."
                else:
                    response = f"Error: Claude returned code {result.returncode}\n{result.stderr}"

            except subprocess.TimeoutExpired:
                response = "Error: Request timed out after 60 seconds"
            except FileNotFoundError:
                response = "Error: claude CLI not found"
            except Exception as e:
                response = f"Error: {str(e)}"

            # Save to chat history
            timestamp = datetime.now().isoformat(timespec='seconds')
            self._save_chat_message('owner', message, timestamp)
            self._save_chat_message('vsm', response, timestamp)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'response': response}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'response': f"Error: {str(e)}"}).encode())

    def _save_chat_message(self, role, content, timestamp):
        """Save a message to chat history"""
        try:
            # Load existing history
            if CHAT_HISTORY_FILE.exists():
                with open(CHAT_HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            else:
                history = {"messages": []}

            # Add new message
            history["messages"].append({
                "role": role,
                "content": content,
                "timestamp": timestamp
            })

            # Keep only last 50 messages
            if len(history["messages"]) > 50:
                history["messages"] = history["messages"][-50:]

            # Save
            CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CHAT_HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            print(f"Error saving chat message: {e}")

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
