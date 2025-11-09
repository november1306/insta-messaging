#!/bin/bash
# Start Instagram Messenger Automation as background daemon

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Server is already running (PID: $PID)"
        echo "Use ./stop-daemon.sh to stop it first"
        exit 1
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run ./deploy.sh first."
    exit 1
fi

echo "Starting Instagram Messenger Automation..."

# Activate virtual environment and start server in background
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &

# Save PID
echo $! > "$PID_FILE"

# Verify server started
sleep 2
if ! ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    echo "Error: Server failed to start. Check $LOG_FILE"
    rm "$PID_FILE"
    exit 1
fi

echo "Server started successfully!"
echo "  PID: $(cat $PID_FILE)"
echo "  Logs: $LOG_FILE"
echo ""
echo "Commands:"
echo "  View logs: tail -f $LOG_FILE"
echo "  Stop server: ./stop-daemon.sh"
echo "  Check status: ./status-daemon.sh"
