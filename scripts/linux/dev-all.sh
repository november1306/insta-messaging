#!/bin/bash
# Linux Development All Services Script
# Starts ngrok, backend, and frontend in development mode

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

print_info() {
    echo -e "[INFO] $1"
}

# Track PIDs for cleanup
NGROK_PID=""
BACKEND_PID=""

# Cleanup function
cleanup() {
    echo ""
    print_info "Shutting down services..."

    # Gracefully stop backend
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        sleep 1
        # Only force kill if still running
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            kill -9 $BACKEND_PID 2>/dev/null || true
        fi
        print_info "Backend stopped"
    fi

    # Gracefully stop ngrok
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
        sleep 1
        # Only force kill if still running
        if ps -p $NGROK_PID > /dev/null 2>&1; then
            kill -9 $NGROK_PID 2>/dev/null || true
        fi
        print_info "ngrok stopped"
    fi

    # Clean up any orphaned processes on our ports (only if PIDs weren't tracked)
    if [ -z "$BACKEND_PID" ] && lsof -ti:8000 > /dev/null 2>&1; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    fi
    if [ -z "$NGROK_PID" ] && lsof -ti:4040 > /dev/null 2>&1; then
        lsof -ti:4040 | xargs kill -9 2>/dev/null || true
    fi
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true

    print_info "All services stopped"
    exit 0
}

# Set up trap for cleanup on Ctrl+C
trap cleanup INT TERM

echo "========================================"
echo " Starting All Development Services"
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

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    print_error "Frontend dependencies not installed"
    echo "Please run 'scripts/linux/install.sh' first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Start backend first
echo "[1/3] Starting backend server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
BACKEND_PID=$!
sleep 3

# Verify backend started
if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
    print_error "Backend failed to start"
    echo "Check logs for errors. Common issues:"
    echo "  - Port 8000 already in use"
    echo "  - Missing dependencies in venv"
    echo "  - Database connection errors"
    exit 1
fi
print_success "Backend started (http://localhost:8000)"

# Start ngrok (check if installed first, but don't fail if not found)
echo ""
echo "[2/3] Starting ngrok tunnel..."
if command -v ngrok &> /dev/null; then
    ngrok http 8000 > /dev/null 2>&1 &
    NGROK_PID=$!
    sleep 2

    # Verify ngrok started
    if ps -p $NGROK_PID > /dev/null 2>&1; then
        print_success "ngrok started (UI at http://localhost:4040)"
    else
        print_warning "ngrok failed to start (not critical for local development)"
        NGROK_PID=""
    fi
else
    print_warning "ngrok not installed (optional for Instagram webhooks)"
    echo "Install from: https://ngrok.com/download"
    NGROK_PID=""
fi

# Start frontend
echo ""
echo "[3/3] Starting frontend server..."
print_success "Frontend will start on http://localhost:5173"
echo ""
echo "========================================"
echo " All Services Running"
echo "========================================"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8000/docs"
echo "  ngrok UI: http://localhost:4040"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start frontend in foreground (blocks until Ctrl+C)
cd frontend
npm run dev

# This will only run if npm exits normally (not from Ctrl+C)
cleanup
