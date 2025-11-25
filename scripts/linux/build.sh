#!/bin/bash
# Linux Build Script
# Builds production frontend

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "========================================"
echo " Building Production Frontend"
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

print_success "Building frontend..."
cd frontend
npm run build
if [ $? -ne 0 ]; then
    print_error "Frontend build failed"
    exit 1
fi
cd ..

echo ""
echo "========================================"
echo " Build Complete!"
echo "========================================"
echo ""
echo "Frontend built to: frontend/dist/"
echo "Served by backend at: http://localhost:8000/chat"
echo ""
echo "To start production server: scripts/linux/start.sh"
echo ""
