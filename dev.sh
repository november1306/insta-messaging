#!/bin/bash
# Development startup script for Instagram Messenger Automation
# Starts FastAPI backend, Vue frontend, and ngrok tunnel in parallel

set -e

echo "🚀 Starting Instagram Messenger Automation (Development Mode)"
echo "============================================================"

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "⚠️  WARNING: ngrok not found!"
    echo "   Instagram webhooks require ngrok for local development."
    echo "   Download from: https://ngrok.com/download"
    echo ""
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down all services..."
    kill 0
    echo "✓ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "Starting servers:"
echo "  - Backend (FastAPI):  http://localhost:8000"
echo "  - Frontend (Vue):     http://localhost:5173"
echo "  - API Docs:           http://localhost:8000/docs"
echo "  - Chat UI (dev):      http://localhost:5173"
echo "  - Chat UI (prod):     http://localhost:8000/chat (after build)"
if command -v ngrok &> /dev/null; then
    echo "  - ngrok tunnel:       Starting... (check logs for URL)"
fi
echo ""
echo "Press Ctrl+C to stop all servers"
echo "============================================================"
echo ""

# Start ngrok tunnel (if installed)
if command -v ngrok &> /dev/null; then
    echo "🌐 Starting ngrok tunnel..."
    ngrok http 8000 > /dev/null &
    sleep 3
    echo "   ✓ ngrok started (check http://localhost:4040 for tunnel URL)"
    echo ""
fi

# Start FastAPI backend
echo "🐍 Starting FastAPI backend..."
uvicorn app.main:app --reload --port 8000 &

# Wait a moment for backend to start
sleep 2

# Start Vue frontend dev server
echo "⚡ Starting Vue frontend..."
echo ""
cd frontend && npm run dev &

# Wait for all background processes
wait
