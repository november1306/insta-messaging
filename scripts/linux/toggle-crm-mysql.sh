#!/bin/bash
# Toggle CRM MySQL sync: ./crm-toggle.sh true|false

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 true|false"
    exit 1
fi

VALUE="$1"

if [ "$VALUE" != "true" ] && [ "$VALUE" != "false" ]; then
    echo "Error: Value must be 'true' or 'false'"
    exit 1
fi

# Update .env
sed -i "s/^CRM_MYSQL_ENABLED=.*/CRM_MYSQL_ENABLED=$VALUE/" .env
echo "Updated CRM_MYSQL_ENABLED=$VALUE"

# Restart daemon
PID_FILE="server.pid"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$PID_FILE" ]; then
    echo "Stopping server..."
    bash "$SCRIPT_DIR/stop-daemon.sh"
    sleep 2
fi

echo "Starting server..."
bash "$SCRIPT_DIR/start-daemon.sh"
