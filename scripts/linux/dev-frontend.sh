#!/bin/bash
# Linux Development Frontend Script
# Starts Vue/Vite frontend development server

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

echo "========================================"
echo " Starting Frontend Development Server"
echo "========================================"
echo ""

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
    print_error "Frontend directory not found"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    print_error "Frontend dependencies not installed"
    echo "Please run 'scripts/linux/install.sh' first"
    exit 1
fi

# Check if port 5173 is available
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 5173 is already in use"
    echo "Please stop any services using this port"
    exit 1
fi

print_success "Starting Vite frontend on http://localhost:5173"
print_success "Make sure backend is running on port 8000 for API calls"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Change to frontend directory and start dev server
cd frontend
npm run dev
