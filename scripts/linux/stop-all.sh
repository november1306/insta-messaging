#!/bin/bash
# Linux Stop All Services Script
# Stops all development services (ngrok, backend, frontend)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_info() {
    echo -e "[INFO] $1"
}

echo "========================================"
echo "  Stopping All Development Services"
echo "========================================"
echo ""

FOUND_PROCESS=0

# Stop frontend (Vite on port 5173)
echo "[1/3] Stopping frontend server..."
if lsof -ti:5173 >/dev/null 2>&1; then
    kill $(lsof -ti:5173) 2>/dev/null || true
    print_success "Frontend stopped"
    FOUND_PROCESS=1
else
    print_info "Frontend not running"
fi

echo ""

# Stop backend (uvicorn on port 8000)
echo "[2/3] Stopping backend server..."
if lsof -ti:8000 >/dev/null 2>&1; then
    kill $(lsof -ti:8000) 2>/dev/null || true
    print_success "Backend stopped"
    FOUND_PROCESS=1
else
    print_info "Backend not running"
fi

echo ""

# Stop ngrok (on port 4040)
echo "[3/3] Stopping ngrok tunnel..."
if lsof -ti:4040 >/dev/null 2>&1; then
    kill $(lsof -ti:4040) 2>/dev/null || true
    print_success "ngrok stopped"
    FOUND_PROCESS=1
else
    print_info "ngrok not running"
fi

# Also kill any stray ngrok processes
pkill -f ngrok 2>/dev/null || true

echo ""
echo "========================================"
echo "  All Services Stopped"
echo "========================================"
echo ""
