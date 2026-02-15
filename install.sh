#!/usr/bin/env bash
# VSM Installer — One-command setup for the Viable System Machine
# Usage: curl -fsSL https://raw.githubusercontent.com/turlockmike/vsm/main/install.sh | bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Symbols
CHECK="${GREEN}✓${NC}"
CROSS="${RED}✗${NC}"
WARN="${YELLOW}⚠${NC}"

# Default installation directory
DEFAULT_VSM_DIR="$HOME/vsm"
VSM_DIR="${VSM_DIR:-$DEFAULT_VSM_DIR}"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       VSM — Viable System Machine Installer             ║"
echo "║       Autonomous AI Computer Built on Claude Code       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check OS compatibility
echo -e "\n${BLUE}[1/8]${NC} Checking system compatibility..."
OS="$(uname -s)"
case "$OS" in
    Linux*)     echo -e "${CHECK} Linux detected" ;;
    Darwin*)    echo -e "${CHECK} macOS detected" ;;
    *)          echo -e "${CROSS} Unsupported OS: $OS. VSM requires Linux or macOS." && exit 1 ;;
esac

# Check prerequisites
echo -e "\n${BLUE}[2/8]${NC} Verifying prerequisites..."

# Python 3
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${CHECK} python3 (${PYTHON_VERSION})"
else
    echo -e "${CROSS} python3 not found. Please install Python 3.x first."
    exit 1
fi

# Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "${CHECK} git (${GIT_VERSION})"
else
    echo -e "${CROSS} git not found. Please install git first."
    exit 1
fi

# Node/npm (needed for claude)
if command -v node &> /dev/null && command -v npm &> /dev/null; then
    NODE_VERSION=$(node --version)
    NPM_VERSION=$(npm --version)
    echo -e "${CHECK} node (${NODE_VERSION}), npm (${NPM_VERSION})"
else
    echo -e "${CROSS} node/npm not found. Please install Node.js first."
    echo -e "   Visit: https://nodejs.org/"
    exit 1
fi

# Claude CLI
if command -v claude &> /dev/null; then
    echo -e "${CHECK} claude CLI installed"
else
    echo -e "${WARN} claude CLI not found."
    echo -e "   Installing Claude Code CLI globally..."
    if npm install -g @anthropic-ai/claude-code; then
        echo -e "${CHECK} claude CLI installed successfully"
    else
        echo -e "${CROSS} Failed to install claude CLI. Please run:"
        echo -e "   ${YELLOW}npm install -g @anthropic-ai/claude-code${NC}"
        exit 1
    fi
fi

# Clone or update repository
echo -e "\n${BLUE}[3/8]${NC} Setting up VSM repository..."

if [ -d "$VSM_DIR" ]; then
    echo -e "${WARN} Directory $VSM_DIR already exists."
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$VSM_DIR"
        if [ -d ".git" ]; then
            echo -e "   Pulling latest changes..."
            git pull origin main
            echo -e "${CHECK} Repository updated"
        else
            echo -e "${CROSS} Directory exists but is not a git repository."
            exit 1
        fi
    else
        echo -e "${WARN} Skipping repository clone/update."
    fi
else
    echo -e "   Cloning repository to $VSM_DIR..."
    if git clone https://github.com/turlockmike/vsm.git "$VSM_DIR"; then
        echo -e "${CHECK} Repository cloned successfully"
    else
        echo -e "${CROSS} Failed to clone repository."
        exit 1
    fi
fi

cd "$VSM_DIR"

# Set up directory structure
echo -e "\n${BLUE}[4/8]${NC} Creating directory structure..."

mkdir -p state/logs
mkdir -p sandbox/tasks
echo -e "${CHECK} Directories created: state/, state/logs/, sandbox/tasks/"

# Make heartbeat.sh executable
chmod +x heartbeat.sh
echo -e "${CHECK} heartbeat.sh made executable"

# Initialize state.json if it doesn't exist
if [ ! -f "state/state.json" ]; then
    cat > state/state.json <<'EOF'
{
  "last_run": null,
  "cycle_count": 0,
  "health_status": "initializing",
  "version": "1.0.0",
  "installed_at": null
}
EOF
    # Update installed_at timestamp
    if command -v python3 &> /dev/null; then
        python3 -c "import json; from datetime import datetime; d=json.load(open('state/state.json')); d['installed_at']=datetime.utcnow().isoformat()+'Z'; json.dump(d, open('state/state.json','w'), indent=2)"
    fi
    echo -e "${CHECK} state/state.json initialized"
else
    echo -e "${WARN} state/state.json already exists, not overwriting"
fi

# Update heartbeat.sh to use correct VSM_ROOT
echo -e "\n${BLUE}[5/8]${NC} Configuring heartbeat script..."

if [ "$VSM_DIR" != "$HOME/projects/vsm/main" ]; then
    # Need to update VSM_ROOT in heartbeat.sh
    if grep -q "VSM_ROOT=" heartbeat.sh; then
        # Create a backup
        cp heartbeat.sh heartbeat.sh.bak
        # Update the path
        sed -i.tmp "s|VSM_ROOT=.*|VSM_ROOT=\"$VSM_DIR\"|" heartbeat.sh
        rm -f heartbeat.sh.tmp
        echo -e "${CHECK} heartbeat.sh configured for $VSM_DIR"
    fi
else
    echo -e "${CHECK} Using default VSM_ROOT path"
fi

# Install vsm CLI to PATH
echo -e "\n${BLUE}[6/8]${NC} Installing vsm CLI to PATH..."

# Make vsm executable
chmod +x "$VSM_DIR/vsm"
echo -e "${CHECK} vsm CLI made executable"

# Create ~/.local/bin if it doesn't exist
mkdir -p "$HOME/.local/bin"
echo -e "${CHECK} ~/.local/bin directory ready"

# Remove old symlink if it exists
if [ -L "$HOME/.local/bin/vsm" ]; then
    rm "$HOME/.local/bin/vsm"
    echo -e "${CHECK} Removed old vsm symlink"
fi

# Create symlink
ln -s "$VSM_DIR/vsm" "$HOME/.local/bin/vsm"
echo -e "${CHECK} Symlinked vsm to ~/.local/bin/vsm"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    echo -e "${CHECK} ~/.local/bin is already in PATH"
else
    echo -e "${WARN} ~/.local/bin is not in your PATH"
    echo -e "${YELLOW}   Add this line to your shell profile (~/.bashrc or ~/.zshrc):${NC}"
    echo -e "   ${BLUE}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo ""
    echo -e "   Then reload your shell:"
    echo -e "   ${BLUE}source ~/.bashrc${NC}  (or source ~/.zshrc)"
    echo ""
fi

# Guide .env setup
echo -e "\n${BLUE}[7/8]${NC} Environment configuration..."

if [ -f ".env" ]; then
    echo -e "${WARN} .env file already exists, not overwriting"
else
    echo -e "${YELLOW}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " REQUIRED: Create your .env file"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"
    echo "VSM needs an .env file with the following variables:"
    echo ""
    echo "1. AGENTMAIL_API_KEY — Get your API key from:"
    echo "   https://agentmail.to/"
    echo ""
    echo "2. OWNER_EMAIL — Your email address for system notifications"
    echo ""
    echo -e "${YELLOW}Create this file now:${NC}"
    echo "  cd $VSM_DIR"
    echo "  nano .env"
    echo ""
    echo "Add these lines (replace with your actual values):"
    echo "  AGENTMAIL_API_KEY=your_api_key_here"
    echo "  OWNER_EMAIL=your.email@example.com"
    echo ""
    read -p "Press Enter when you've created the .env file... " -r
    echo

    if [ ! -f ".env" ]; then
        echo -e "${CROSS} .env file not found. VSM will not work without it."
        echo -e "   Please create it before continuing."
        exit 1
    else
        echo -e "${CHECK} .env file detected"
    fi
fi

# Create/update cron job
echo -e "\n${BLUE}[8/8]${NC} Setting up cron job..."

CRON_ENTRY="*/5 * * * * $VSM_DIR/heartbeat.sh"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$VSM_DIR/heartbeat.sh"; then
    echo -e "${WARN} Cron job already exists for this VSM instance"
else
    echo -e "${YELLOW}"
    echo "VSM runs autonomously via a cron job that executes every 5 minutes."
    echo "This will add the following cron entry:"
    echo ""
    echo "  */5 * * * * $VSM_DIR/heartbeat.sh"
    echo -e "${NC}"

    read -p "Install cron job? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
        echo -e "${CHECK} Cron job installed successfully"
    else
        echo -e "${WARN} Skipped cron installation. To install manually, run:"
        echo -e "   ${YELLOW}(crontab -l; echo \"$CRON_ENTRY\") | crontab -${NC}"
    fi
fi

# Success!
echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           VSM Installation Complete! 🎉                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "Installation directory: ${BLUE}$VSM_DIR${NC}"
echo ""
echo -e "${GREEN}What was installed:${NC}"
echo "  • VSM repository cloned from GitHub"
echo "  • Directory structure created (state/, sandbox/tasks/)"
echo "  • Initial state.json initialized"
echo "  • Heartbeat script configured"
echo "  • Cron job scheduled (every 5 minutes)"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo ""
echo "1. Verify your .env configuration:"
echo -e "   ${BLUE}cat $VSM_DIR/.env${NC}"
echo ""
echo "2. Check system status:"
echo -e "   ${BLUE}vsm status${NC}"
echo ""
echo "3. Add a task to the queue:"
echo -e "   ${BLUE}vsm task add \"Say hello\"${NC}"
echo ""
echo "4. View logs:"
echo -e "   ${BLUE}vsm logs${NC}"
echo ""
echo "5. Open the dashboard:"
echo -e "   ${BLUE}vsm dashboard${NC}"
echo ""
echo "6. Manual test run:"
echo -e "   ${BLUE}vsm run${NC}"
echo ""
echo "7. View cron jobs:"
echo -e "   ${BLUE}crontab -l${NC}"
echo ""
echo -e "${YELLOW}Documentation:${NC} https://github.com/turlockmike/vsm"
echo -e "${YELLOW}Support:${NC} Open an issue on GitHub"
echo ""
echo -e "${GREEN}VSM will begin autonomous operation within 5 minutes.${NC}"
echo ""
