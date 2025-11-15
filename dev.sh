#!/bin/bash
# Development startup script for Instagram Messenger Automation
# Starts both FastAPI backend and Vue frontend in parallel

set -e

echo "🚀 Starting Instagram Messenger Automation (Development Mode)"
echo "============================================================"

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill 0
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "Starting servers:"
echo "  - Backend (FastAPI):  http://localhost:8000"
echo "  - Frontend (Vue):     http://localhost:5173"
echo "  - API Docs:           http://localhost:8000/docs"
echo "  - Chat UI (dev):      http://localhost:5173"
echo "  - Chat UI (prod URL): http://localhost:8000/chat (after build)"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "============================================================"
echo ""

# Start FastAPI backend
echo "🐍 Starting FastAPI backend..."
uvicorn app.main:app --reload --port 8000 &

# Wait a moment for backend to start
sleep 2

# Start Vue frontend dev server
echo "⚡ Starting Vue frontend..."
cd frontend && npm run dev &

# Wait for all background processes
wait
