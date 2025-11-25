#!/bin/bash
# Linux Development Backend Script
# Starts FastAPI backend server in development mode

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
echo " Starting Backend Development Server"
echo "========================================"
echo ""

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

# Activate virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 8000 is already in use"
    echo "Please stop any services using this port or change PORT in .env"
    exit 1
fi

print_success "Starting FastAPI backend on http://localhost:8000"
print_success "API documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start uvicorn with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
