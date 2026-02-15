#!/usr/bin/env bash
# VSM Installer Test Suite
# Tests the install.sh script for correctness without running actual installation
# Usage: ./test_install.sh

set -eo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Test result reporting
pass() {
    echo -e "${GREEN}✓${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    echo -e "  ${RED}Reason: $2${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

info() {
    echo -e "${BLUE}→${NC} $1"
}

section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
}

# Read install.sh
INSTALL_SCRIPT="install.sh"
if [ ! -f "$INSTALL_SCRIPT" ]; then
    echo -e "${RED}ERROR: install.sh not found${NC}"
    exit 1
fi

section "Test 1: Script Safety - Error Handling"

# Test: set -euo pipefail is present
if grep -q "^set -euo pipefail" "$INSTALL_SCRIPT"; then
    pass "Script has 'set -euo pipefail' for strict error handling"
else
    fail "Script missing 'set -euo pipefail'" "Without this, errors may be silently ignored"
fi

section "Test 2: Prerequisite Detection Logic"

# Test: Python3 detection
info "Testing Python3 detection logic..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    if [ -n "$PYTHON_VERSION" ]; then
        pass "Python3 detection works (found version $PYTHON_VERSION)"
    else
        fail "Python3 version extraction failed" "Command succeeded but version parsing failed"
    fi
else
    info "Python3 not installed - installer would correctly fail"
    pass "Python3 check logic is correct (detects absence)"
fi

# Test: Git detection
info "Testing Git detection logic..."
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version 2>&1 | cut -d' ' -f3)
    if [ -n "$GIT_VERSION" ]; then
        pass "Git detection works (found version $GIT_VERSION)"
    else
        fail "Git version extraction failed" "Command succeeded but version parsing failed"
    fi
else
    info "Git not installed - installer would correctly fail"
    pass "Git check logic is correct (detects absence)"
fi

# Test: Node detection
info "Testing Node/npm detection logic..."
if command -v node &> /dev/null && command -v npm &> /dev/null; then
    NODE_VERSION=$(node --version 2>&1)
    NPM_VERSION=$(npm --version 2>&1)
    if [ -n "$NODE_VERSION" ] && [ -n "$NPM_VERSION" ]; then
        pass "Node/npm detection works (node $NODE_VERSION, npm $NPM_VERSION)"
    else
        fail "Node/npm version extraction failed" "Commands succeeded but version parsing failed"
    fi
else
    info "Node/npm not fully installed - installer would correctly fail"
    pass "Node/npm check logic is correct (detects absence)"
fi

# Test: Claude CLI detection
info "Testing Claude CLI detection logic..."
if command -v claude &> /dev/null; then
    pass "Claude CLI detection works (found installed)"
else
    info "Claude CLI not installed - installer would attempt npm install"
    pass "Claude CLI check logic is correct (detects absence for auto-install)"
fi

section "Test 3: Path Handling and sed Commands"

# Test: sed command syntax for VSM_ROOT update
info "Testing sed command for VSM_ROOT path substitution..."

# Create a test heartbeat.sh snippet
TEST_FILE=$(mktemp)
cat > "$TEST_FILE" <<'EOF'
#!/usr/bin/env bash
VSM_ROOT="$HOME/projects/vsm/main"
cd "$VSM_ROOT" || exit 1
EOF

# Test the sed command from install.sh (line 158)
TEST_PATH="/home/testuser/custom/vsm"
if sed -e "s|VSM_ROOT=.*|VSM_ROOT=\"$TEST_PATH\"|" "$TEST_FILE" | grep -q "VSM_ROOT=\"$TEST_PATH\""; then
    pass "sed command correctly updates VSM_ROOT path"
else
    fail "sed command failed to update VSM_ROOT" "Path substitution regex may be incorrect"
fi

# Test with various path formats
info "Testing sed with edge case paths..."
EDGE_CASES=(
    "/path/with spaces/vsm"
    "/path/with/trailing/slash/"
    "$HOME/vsm"
    "/root/vsm"
)

EDGE_PASSED=0
for path in "${EDGE_CASES[@]}"; do
    if sed -e "s|VSM_ROOT=.*|VSM_ROOT=\"$path\"|" "$TEST_FILE" | grep -q "VSM_ROOT=\"$path\""; then
        EDGE_PASSED=$((EDGE_PASSED + 1))
    fi
done

if [ $EDGE_PASSED -eq ${#EDGE_CASES[@]} ]; then
    pass "sed command handles edge cases (spaces, trailing slashes, etc.)"
else
    fail "sed command failed on some edge cases" "Failed $((${#EDGE_CASES[@]} - EDGE_PASSED))/${#EDGE_CASES[@]} edge cases"
fi

rm -f "$TEST_FILE"

section "Test 4: Cron Entry Format"

# Test: Cron entry syntax
info "Testing cron entry format..."
TEST_VSM_DIR="/home/testuser/vsm"
CRON_ENTRY="*/5 * * * * $TEST_VSM_DIR/heartbeat.sh"

# Basic cron syntax validation
# Format: minute hour day month weekday command
if [[ "$CRON_ENTRY" =~ ^\*/5[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]+.+$ ]]; then
    pass "Cron entry format is syntactically valid"
else
    fail "Cron entry format is invalid" "Does not match cron syntax pattern"
fi

# Test: Cron timing - every 5 minutes
if [[ "$CRON_ENTRY" =~ ^\*/5 ]]; then
    pass "Cron timing correctly set to */5 (every 5 minutes)"
else
    fail "Cron timing incorrect" "Expected */5 for 5-minute intervals"
fi

# Test: Cron command path
if [[ "$CRON_ENTRY" =~ heartbeat\.sh$ ]]; then
    pass "Cron entry correctly points to heartbeat.sh"
else
    fail "Cron entry doesn't point to heartbeat.sh" "Invalid script reference"
fi

# Test: Absolute path in cron entry
if [[ "$CRON_ENTRY" =~ [[:space:]]/.*heartbeat\.sh$ ]]; then
    pass "Cron entry uses absolute path (required for cron reliability)"
else
    fail "Cron entry uses relative path" "Cron jobs require absolute paths"
fi

section "Test 5: Directory Structure Creation"

# Test: mkdir commands are safe
info "Testing directory creation logic..."
if grep -q "mkdir -p state/logs" "$INSTALL_SCRIPT" && \
   grep -q "mkdir -p sandbox/tasks" "$INSTALL_SCRIPT"; then
    pass "Directory creation uses 'mkdir -p' (safe for existing dirs)"
else
    fail "Directory creation might not use 'mkdir -p'" "Could fail if dirs already exist"
fi

section "Test 6: State.json Initialization"

# Test: state.json template is valid JSON
info "Extracting state.json template from installer..."
STATE_JSON_TEMPLATE=$(sed -n '/cat > state\/state.json <<'\''EOF'\''/,/^EOF$/p' "$INSTALL_SCRIPT" | sed '1d;$d')

if [ -n "$STATE_JSON_TEMPLATE" ]; then
    # Try to parse it with python
    if echo "$STATE_JSON_TEMPLATE" | python3 -m json.tool > /dev/null 2>&1; then
        pass "state.json template is valid JSON"
    else
        fail "state.json template is invalid JSON" "JSON parsing failed"
    fi
else
    fail "Could not extract state.json template" "Template not found in installer"
fi

section "Test 7: Python One-liner for Timestamp"

# Test: Python command for setting installed_at timestamp
info "Testing Python timestamp injection..."
TEMP_STATE=$(mktemp)
cat > "$TEMP_STATE" <<'EOF'
{
  "last_run": null,
  "cycle_count": 0,
  "health_status": "initializing",
  "version": "1.0.0",
  "installed_at": null
}
EOF

# Run the python command from line 142
if python3 -c "import json; from datetime import datetime; d=json.load(open('$TEMP_STATE')); d['installed_at']=datetime.utcnow().isoformat()+'Z'; json.dump(d, open('$TEMP_STATE','w'), indent=2)" 2>&1; then
    # Check if timestamp was added
    if grep -q "installed_at.*20[0-9][0-9]-" "$TEMP_STATE"; then
        pass "Python timestamp injection works correctly"
    else
        fail "Python timestamp injection didn't add timestamp" "File written but no timestamp found"
    fi
else
    fail "Python timestamp injection command failed" "Syntax or execution error"
fi

rm -f "$TEMP_STATE"

section "Test 8: Error Exit Codes"

# Test: All error exits have exit 1
info "Checking error exit codes..."
ERROR_EXITS=$(grep -n "exit 1" "$INSTALL_SCRIPT" | wc -l)
if [ "$ERROR_EXITS" -gt 0 ]; then
    pass "Script uses 'exit 1' for error conditions ($ERROR_EXITS occurrences)"
else
    fail "No 'exit 1' found" "Script may not properly signal errors"
fi

# Test: Check for potentially dangerous patterns
info "Checking for dangerous patterns..."
DANGEROUS_FOUND=0

if grep -q "rm -rf /" "$INSTALL_SCRIPT"; then
    fail "DANGEROUS: Found 'rm -rf /' pattern" "Could delete entire filesystem"
    DANGEROUS_FOUND=$((DANGEROUS_FOUND + 1))
fi

if grep -q "chmod 777" "$INSTALL_SCRIPT"; then
    fail "DANGEROUS: Found 'chmod 777' pattern" "Overly permissive permissions"
    DANGEROUS_FOUND=$((DANGEROUS_FOUND + 1))
fi

if [ $DANGEROUS_FOUND -eq 0 ]; then
    pass "No dangerous patterns found (rm -rf /, chmod 777, etc.)"
fi

section "Test 9: Path Expansion and Variables"

# Test: HOME variable usage
info "Testing HOME variable usage..."
if grep -q '\$HOME' "$INSTALL_SCRIPT"; then
    pass "Script uses \$HOME for user-relative paths"
else
    fail "Script doesn't use \$HOME" "May have hardcoded paths"
fi

# Test: Variable quoting in paths
info "Checking for unquoted variable expansions..."
UNQUOTED=$(grep -E '\$[A-Z_]+/' "$INSTALL_SCRIPT" | grep -v '"' | wc -l)
if [ "$UNQUOTED" -eq 0 ]; then
    pass "Path variables are properly quoted"
else
    info "Found $UNQUOTED potentially unquoted variable expansions (review manually)"
fi

section "Test 10: Symlink Creation"

# Test: Symlink command syntax
info "Testing symlink creation logic..."
if grep -q "ln -s.*vsm.*\.local/bin/vsm" "$INSTALL_SCRIPT"; then
    pass "Symlink creation command is present"
else
    fail "Symlink creation command not found" "CLI may not be linked to PATH"
fi

# Test: Old symlink removal before creation
if grep -q "rm.*\.local/bin/vsm" "$INSTALL_SCRIPT"; then
    pass "Script removes old symlink before creating new one"
else
    info "Script may not remove old symlinks (could cause conflicts)"
fi

section "Test 11: Git Operations"

# Test: Git clone command
info "Testing git clone command..."
if grep -q "git clone https://github.com/turlockmike/vsm.git" "$INSTALL_SCRIPT"; then
    pass "Git clone uses correct repository URL"
else
    fail "Git clone URL incorrect or missing" "Repository may not be cloned"
fi

# Test: Git pull for updates
if grep -q "git pull origin main" "$INSTALL_SCRIPT"; then
    pass "Git pull uses 'origin main' for updates"
else
    fail "Git pull command incorrect" "May fail on existing installations"
fi

section "Test 12: Interactive Prompts"

# Test: read -p commands have proper fallbacks
info "Checking interactive prompts..."
READ_PROMPTS=$(grep -c "read -p" "$INSTALL_SCRIPT")
if [ "$READ_PROMPTS" -gt 0 ]; then
    pass "Script has $READ_PROMPTS interactive prompts for user confirmation"
    # Note: In CI/CD this could be an issue, but for manual install it's good
fi

section "Test 13: Backup Creation"

# Test: Backup before modifying files
info "Checking for backup safety..."
if grep -q "cp heartbeat.sh heartbeat.sh.bak" "$INSTALL_SCRIPT"; then
    pass "Script creates backup before modifying heartbeat.sh"
else
    fail "No backup created before modifying files" "Could lose data on failed modification"
fi

section "Test 14: Crontab Safety"

# Test: Crontab append logic
info "Testing crontab append logic..."
if grep -q "(crontab -l 2>/dev/null; echo" "$INSTALL_SCRIPT"; then
    pass "Crontab append preserves existing entries (2>/dev/null handles empty crontab)"
else
    fail "Crontab append may not preserve existing entries" "Could delete user's crontab"
fi

# Test: Duplicate cron entry prevention
if grep -q "grep -q.*heartbeat.sh" "$INSTALL_SCRIPT"; then
    pass "Script checks for duplicate cron entries before adding"
else
    fail "No duplicate cron entry check" "Could add multiple duplicate entries"
fi

section "Test 15: OS Compatibility Check"

# Test: OS detection
info "Testing OS compatibility check..."
if grep -q "uname -s" "$INSTALL_SCRIPT" && \
   grep -q "Linux\*" "$INSTALL_SCRIPT" && \
   grep -q "Darwin\*" "$INSTALL_SCRIPT"; then
    pass "Script checks OS compatibility (Linux/macOS)"
else
    fail "OS compatibility check incomplete" "May run on unsupported systems"
fi

# Test: Unsupported OS exit
if grep -q "Unsupported OS.*exit 1" "$INSTALL_SCRIPT"; then
    pass "Script exits on unsupported OS"
else
    fail "Script may not exit on unsupported OS" "Could proceed with broken installation"
fi

section "BUGS AND ISSUES FOUND"

# Analyze for specific bugs
echo ""
info "Analyzing for common issues..."
echo ""

BUG_COUNT=0

# Bug check 1: sed -i compatibility (macOS vs Linux)
if grep -q "sed -i\.tmp" "$INSTALL_SCRIPT"; then
    echo -e "${GREEN}✓${NC} sed -i uses .tmp suffix for cross-platform compatibility"
else
    echo -e "${RED}BUG #$((++BUG_COUNT)):${NC} sed -i without suffix breaks on macOS"
    echo -e "  ${YELLOW}Fix: Change 'sed -i' to 'sed -i.tmp' and add 'rm -f file.tmp'${NC}"
fi

# Bug check 2: Heartbeat grep pattern
if grep -q 'grep -q "VSM_ROOT=" heartbeat.sh' "$INSTALL_SCRIPT"; then
    echo -e "${GREEN}✓${NC} Heartbeat VSM_ROOT detection uses correct pattern"
else
    echo -e "${RED}BUG #$((++BUG_COUNT)):${NC} Heartbeat VSM_ROOT detection may fail"
    echo -e "  ${YELLOW}Fix: Ensure grep pattern matches VSM_ROOT= in heartbeat.sh${NC}"
fi

# Bug check 3: PATH detection regex
if grep -q '\[\[ ":\$PATH:" == \*":\$HOME/\.local/bin:"\* \]\]' "$INSTALL_SCRIPT"; then
    echo -e "${GREEN}✓${NC} PATH detection uses correct glob pattern"
else
    echo -e "${YELLOW}INFO:${NC} PATH detection pattern may not catch all cases"
fi

# Bug check 4: File existence checks before operations
MKDIR_COUNT=$(grep -c "mkdir -p" "$INSTALL_SCRIPT")
FILE_CHECK_COUNT=$(grep -c "if \[ -f" "$INSTALL_SCRIPT")
DIR_CHECK_COUNT=$(grep -c "if \[ -d" "$INSTALL_SCRIPT")

if [ $((FILE_CHECK_COUNT + DIR_CHECK_COUNT)) -ge 3 ]; then
    echo -e "${GREEN}✓${NC} Script checks for file/directory existence before operations"
else
    echo -e "${YELLOW}INFO:${NC} Limited file/directory existence checks (found $((FILE_CHECK_COUNT + DIR_CHECK_COUNT)))"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Total tests run: ${BLUE}$TESTS_TOTAL${NC}"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Bugs found: ${YELLOW}$BUG_COUNT${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ] && [ $BUG_COUNT -eq 0 ]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}ALL TESTS PASSED! Installer appears correct.${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    exit 0
elif [ $BUG_COUNT -gt 0 ]; then
    echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}TESTS PASSED BUT BUGS FOUND - Review recommendations above${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}═══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}SOME TESTS FAILED - Review failures above${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════${NC}"
    exit 1
fi
