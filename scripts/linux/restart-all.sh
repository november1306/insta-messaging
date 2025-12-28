#!/bin/bash
# Linux Restart All Services Script
# Stops all services, then starts them again

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

echo "========================================"
echo "  Restarting All Development Services"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: Stop all services
echo "[STEP 1/2] Stopping existing services..."
echo ""
bash "$SCRIPT_DIR/stop-all.sh"

echo ""
echo "Waiting 2 seconds before restart..."
sleep 2
echo ""

# Step 2: Start all services
echo "[STEP 2/2] Starting services..."
echo ""
bash "$SCRIPT_DIR/dev-all.sh"
