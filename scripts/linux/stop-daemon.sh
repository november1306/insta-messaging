#!/bin/bash
# Linux Daemon Stop Script
# Stops the background daemon server

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

echo "========================================"
echo " Stopping Production Server (Daemon)"
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
    print_warning "Server process not found (PID: $PID)"
    print_info "Removing stale PID file"
    rm -f "$PID_FILE"
    exit 0
fi

# Send SIGTERM
print_info "Sending SIGTERM to process $PID..."
kill -TERM $PID

# Wait for graceful shutdown (up to 10 seconds)
TIMEOUT=10
for i in $(seq 1 $TIMEOUT); do
    if ! ps -p $PID > /dev/null 2>&1; then
        print_success "Server stopped gracefully"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# If still running, force kill
print_warning "Server did not stop gracefully, forcing..."
kill -9 $PID 2>/dev/null || true

# Wait a moment and verify
sleep 1
if ! ps -p $PID > /dev/null 2>&1; then
    print_success "Server stopped (forced)"
    rm -f "$PID_FILE"
    exit 0
else
    print_error "Failed to stop server"
    exit 1
fi
