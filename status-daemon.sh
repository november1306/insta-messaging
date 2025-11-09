#!/bin/bash
# Check status of Instagram Messenger Automation daemon

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"

if [ ! -f "$PID_FILE" ]; then
    echo "Status: NOT RUNNING (no PID file)"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Status: RUNNING"
    echo "  PID: $PID"
    echo "  Log: $LOG_FILE"
    echo ""
    echo "Recent logs:"
    tail -n 20 "$LOG_FILE"
else
    echo "Status: NOT RUNNING (stale PID file)"
    rm "$PID_FILE"
    exit 1
fi
