#!/bin/bash
# Start script for Instagram Messenger Automation

echo "========================================"
echo "Instagram Messenger Automation"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run ./deploy.sh first."
    echo ""
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Starting FastAPI server..."
echo "Server will be available at: http://0.0.0.0:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000
