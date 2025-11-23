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

    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        print_info "Backend stopped"
    fi

    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
        print_info "ngrok stopped"
    fi

    # Kill any remaining processes on our ports
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    lsof -ti:4040 | xargs kill -9 2>/dev/null || true

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

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    print_error "ngrok is not installed or not in PATH"
    echo ""
    echo "ngrok is required for Instagram webhook testing."
    echo "Please install from: https://ngrok.com/download"
    echo ""
    echo "On Linux/Mac:"
    echo "  brew install ngrok  (macOS)"
    echo "  snap install ngrok  (Linux)"
    echo ""
    exit 1
fi

# Check if ports are available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Port 8000 is already in use"
    echo "Please stop any services using this port"
    exit 1
fi

if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Port 5173 is already in use"
    echo "Please stop any services using this port"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Start ngrok
echo "[1/3] Starting ngrok tunnel..."
ngrok http 8000 > /dev/null 2>&1 &
NGROK_PID=$!
sleep 2
print_success "ngrok started (UI at http://localhost:4040)"

# Start backend
echo ""
echo "[2/3] Starting backend server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
BACKEND_PID=$!
sleep 3
print_success "Backend started (http://localhost:8000)"

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
