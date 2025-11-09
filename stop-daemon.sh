#!/bin/bash
# Stop Instagram Messenger Automation daemon

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Server is not running (no PID file found)"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "Server is not running (process $PID not found)"
    rm "$PID_FILE"
    exit 1
fi

echo "Stopping server (PID: $PID)..."
kill "$PID"

# Wait for process to stop
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "Server stopped successfully"
        rm "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
echo "Server didn't stop gracefully, forcing..."
kill -9 "$PID"
rm "$PID_FILE"
echo "Server stopped (forced)"
