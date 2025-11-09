#!/bin/bash
# Deployment script for Instagram Messenger Automation
# Tested on: Gentoo Linux
# Requirements: Python 3.11+, pip

set -e  # Exit on error

echo "========================================"
echo "Instagram Messenger Automation Deploy"
echo "========================================"
echo ""

# Detect Python binary (try python3.12, python3.11, then python3)
echo "[1/6] Detecting Python version..."
PYTHON_BIN=""
for py in python3.12 python3.11 python3; do
    if command -v $py &> /dev/null; then
        version=$($py --version 2>&1 | awk '{print $2}')
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_BIN=$py
            echo "Found $py (version $version) ✓"
            break
        else
            echo "Found $py (version $version) - too old, need 3.11+"
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo ""
    echo "Error: Python 3.11+ not found."
    echo "On Gentoo, install with: emerge dev-lang/python:3.12"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "[2/6] Creating virtual environment..."
    $PYTHON_BIN -m venv venv
else
    echo ""
    echo "[2/6] Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "[3/6] Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "[4/6] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if it doesn't exist
echo ""
echo "[5/6] Checking for .env file..."
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    chmod 600 .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file and add your credentials!"
    echo "Set .env permissions to 600 (owner read/write only)"
    echo ""
else
    echo ".env file already exists"
fi

# Run database migrations
echo ""
echo "[6/6] Running database migrations..."
alembic upgrade head

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Or use: ./start.sh"
echo ""
