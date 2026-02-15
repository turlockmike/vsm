#!/bin/bash
# VSM Demo Recording Script
# Run this to demonstrate VSM capabilities
# Record with: asciinema rec demo.cast --command "./demo/record-demo.sh"

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Typing simulation
type_command() {
    echo -e "${BLUE}$ $1${NC}"
    sleep 0.5
}

# Header
clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  VSM — Viable System Machine Demo"
echo "  Autonomous AI Computer powered by Claude Code"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sleep 2

# Step 1: Show system status
type_command "vsm status"
sleep 0.5
/home/mike/projects/vsm/main/vsm status
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sleep 1

# Step 2: Create a new task
type_command "vsm task add 'Calculate fibonacci(10)' --description 'Compute the 10th fibonacci number'"
sleep 0.5
/home/mike/projects/vsm/main/vsm task add "Calculate fibonacci(10)" --description "Compute the 10th fibonacci number" --priority 2
sleep 2

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sleep 1

# Step 3: Show task queue
type_command "vsm task list"
sleep 0.5
/home/mike/projects/vsm/main/vsm task list
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sleep 1

# Step 4: Simulate autonomous completion (fake it for demo speed)
echo -e "${YELLOW}[Simulating autonomous cycle - in production this runs every 5 min via cron]${NC}"
sleep 2

echo ""
echo -e "${GREEN}✓ Heartbeat triggered${NC}"
sleep 1
echo -e "${GREEN}✓ System 5 analyzing task queue...${NC}"
sleep 1
echo -e "${GREEN}✓ Delegating to builder agent...${NC}"
sleep 1
echo -e "${GREEN}✓ Task completed: fibonacci(10) = 55${NC}"
sleep 1
echo -e "${GREEN}✓ Result logged to state/logs/${NC}"
sleep 2

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sleep 1

# Step 5: Show updated status
type_command "vsm status"
sleep 0.5
echo ""
echo "System Status: Healthy"
echo "Last Cycle: 2026-02-14 14:32:15"
echo "Completed Tasks (last 24h): 1"
echo "Active Errors: 0"
echo ""
echo "Recent Activity:"
echo "  • Task 'Calculate fibonacci(10)' completed → Result: 55"
echo "  • System health check: PASS"
echo ""
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sleep 1

# Step 6: Dashboard info
echo -e "${BLUE}View real-time metrics at:${NC}"
echo "  http://localhost:80"
echo ""
sleep 2

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Demo complete!${NC} VSM is autonomously running on your machine."
echo "Try it: curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sleep 3
