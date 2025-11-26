#!/bin/bash
# Linux Installation Script
# Idempotent setup script for fresh or existing environments

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo " Instagram Auto - Installation Script"
echo "========================================"
echo ""

# Function to print colored output
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

# Check Python installation
echo "[1/7] Checking Python installation..."

# Use PYTHON_BIN if provided by caller (e.g., deploy-production.sh), otherwise default to python3
if [ -z "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

if ! command -v $PYTHON_BIN &> /dev/null; then
    print_error "Python is not installed ($PYTHON_BIN)"
    echo "Please install Python 3.12 or higher"
    exit 1
fi

# Check Python version (3.12+)
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 12 ]); then
    print_error "Python version is too old: $PYTHON_VERSION"
    echo "Please install Python 3.12 or higher"
    echo "This application requires Python 3.12+ for full async support"
    exit 1
fi
print_success "Python $PYTHON_VERSION detected (using $PYTHON_BIN)"

# Create virtual environment
echo ""
echo "[2/7] Setting up Python virtual environment..."
if [ -d "venv" ]; then
    print_success "Virtual environment already exists"
else
    $PYTHON_BIN -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment and install dependencies
echo ""
echo "[3/7] Installing Python dependencies..."
source venv/bin/activate

print_info "Upgrading pip..."
python -m pip install --upgrade pip
pip install -r requirements.txt
print_success "Python dependencies installed"

# Create .env file if it doesn't exist
echo ""
echo "[4/7] Setting up environment configuration..."
if [ -f ".env" ]; then
    print_success ".env file already exists"
else
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
        chmod 600 ".env"
        print_success "Created .env from .env.example"
        print_warning "Please edit .env file with your configuration"
    else
        print_error ".env.example file not found"
        exit 1
    fi
fi

# Configure ngrok (if auth token is available)
echo ""
echo "[5/7] Configuring ngrok..."
if command -v ngrok &> /dev/null; then
    print_success "ngrok is already installed"

    # Check if NGROK_AUTHTOKEN is set in environment or .env file
    if [ -f ".env" ]; then
        source .env 2>/dev/null || true
    fi

    if [ ! -z "$NGROK_AUTHTOKEN" ]; then
        print_info "Configuring ngrok with auth token..."
        ngrok config add-authtoken "$NGROK_AUTHTOKEN" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "ngrok configured successfully"
        else
            print_warning "Failed to configure ngrok auth token"
        fi
    else
        print_warning "NGROK_AUTHTOKEN not found in .env"
        echo "ngrok will work but with limitations (60 min sessions, random URLs)"
        echo "Add NGROK_AUTHTOKEN to .env for persistent URLs and longer sessions"
    fi
else
    print_warning "ngrok not installed (optional but recommended for Instagram webhooks)"
    echo "Install from: https://ngrok.com/download"
    echo "Then add NGROK_AUTHTOKEN to .env file"
fi

# Run database migrations
echo ""
echo "[6/7] Running database migrations..."
alembic upgrade head
print_success "Database migrations completed"

# Install frontend dependencies
echo ""
echo "[7/7] Installing frontend dependencies..."
if [ ! -d "frontend" ]; then
    print_error "Frontend directory not found"
    exit 1
fi

cd frontend
if [ -d "node_modules" ]; then
    print_success "Frontend dependencies already installed"
else
    npm install
    print_success "Frontend dependencies installed"
fi
cd ..

echo ""
echo "========================================"
echo " Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your configuration"
echo "  2. Run 'scripts/linux/dev-all.sh' to start development server"
echo "  3. Or run individual components:"
echo "     - scripts/linux/dev-backend.sh (backend only)"
echo "     - scripts/linux/dev-frontend.sh (frontend only)"
echo ""
