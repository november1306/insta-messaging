#!/bin/bash
# Linux Daemon Start Script
# Starts FastAPI backend server as a background daemon

set -e  # Exit on error

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

PID_FILE="server.pid"
LOG_FILE="server.log"

echo "========================================"
echo " Starting Production Server (Daemon)"
echo "========================================"
echo ""

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        print_warning "Server is already running (PID: $PID)"
        echo "Use 'scripts/linux/stop-daemon.sh' to stop it first"
        exit 1
    else
        print_warning "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    print_error "Virtual environment not found"
    echo "Please run 'scripts/linux/install.sh' first"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    print_error ".env file not found"
    echo "Please run 'scripts/linux/install.sh' or copy .env.example to .env"
    exit 1
fi

# Check if frontend is built
if [ ! -d "frontend/dist" ]; then
    print_warning "Frontend not built"
    echo "Run 'scripts/linux/build.sh' to build the frontend"
    echo "Frontend will not be available at /chat"
    echo ""
fi

# Activate virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Port 8000 is already in use"
    echo "Please stop any services using this port or change PORT in .env"
    exit 1
fi

# Start uvicorn in background
print_success "Starting server in background..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Save PID
echo $SERVER_PID > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 2

if ps -p $SERVER_PID > /dev/null 2>&1; then
    print_success "Server started successfully (PID: $SERVER_PID)"
    echo ""
    echo "Server is running at: http://0.0.0.0:8000"
    echo "API documentation: http://localhost:8000/docs"
    if [ -d "frontend/dist" ]; then
        echo "Frontend UI: http://localhost:8000/chat"
    fi
    echo ""
    echo "Logs: $LOG_FILE"
    echo "PID file: $PID_FILE"
    echo ""
    echo "To stop: scripts/linux/stop-daemon.sh"
    echo "To check status: scripts/linux/status-daemon.sh"
else
    print_error "Server failed to start"
    echo "Check $LOG_FILE for details"
    rm -f "$PID_FILE"
    exit 1
fi
