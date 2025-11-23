#!/bin/bash
# Linux Daemon Status Script
# Checks the status of the background daemon server

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "[INFO] $1"
}

PID_FILE="server.pid"
LOG_FILE="server.log"

echo "========================================"
echo " Production Server Status (Daemon)"
echo "========================================"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    print_error "Server is not running (no PID file found)"
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! ps -p $PID > /dev/null 2>&1; then
    print_error "Server process not found (PID: $PID)"
    print_warning "PID file exists but process is not running"
    print_info "Run 'scripts/linux/stop-daemon.sh' to clean up"
    exit 1
fi

# Get process info
PROCESS_INFO=$(ps -p $PID -o pid,etime,cmd --no-headers)

print_success "Server is running"
echo ""
echo "Process Information:"
echo "  $PROCESS_INFO"
echo ""
echo "Server URLs:"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
if [ -d "frontend/dist" ]; then
    echo "  Frontend: http://localhost:8000/chat"
fi
echo ""
echo "Files:"
echo "  PID file: $PID_FILE"
echo "  Log file: $LOG_FILE"
echo ""

# Show last 20 lines of log
if [ -f "$LOG_FILE" ]; then
    echo "Last 20 log lines:"
    echo "----------------------------------------"
    tail -n 20 "$LOG_FILE"
    echo "----------------------------------------"
    echo ""
    echo "To view full logs: tail -f $LOG_FILE"
else
    print_warning "Log file not found: $LOG_FILE"
fi

echo ""
echo "To stop the server: scripts/linux/stop-daemon.sh"
