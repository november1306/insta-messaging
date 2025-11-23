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
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    echo "Please install Python 3.11 or higher"
    exit 1
fi

# Check Python version (3.11+)
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
    print_error "Python version is too old: $PYTHON_VERSION"
    echo "Please install Python 3.11 or higher"
    exit 1
fi
print_success "Python $PYTHON_VERSION detected"

# Create virtual environment
echo ""
echo "[2/6] Setting up Python virtual environment..."
if [ -d "venv" ]; then
    print_success "Virtual environment already exists"
else
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        print_error "Failed to create virtual environment"
        exit 1
    fi
    print_success "Virtual environment created"
fi

# Activate virtual environment and install dependencies
echo ""
echo "[3/6] Installing Python dependencies..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

python -m pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    print_error "Failed to install Python dependencies"
    exit 1
fi
print_success "Python dependencies installed"

# Create .env file if it doesn't exist
echo ""
echo "[4/6] Setting up environment configuration..."
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

# Run database migrations
echo ""
echo "[5/6] Running database migrations..."
alembic upgrade head
if [ $? -ne 0 ]; then
    print_error "Database migration failed"
    exit 1
fi
print_success "Database migrations completed"

# Install frontend dependencies
echo ""
echo "[6/6] Installing frontend dependencies..."
if [ ! -d "frontend" ]; then
    print_error "Frontend directory not found"
    exit 1
fi

cd frontend
if [ -d "node_modules" ]; then
    print_success "Frontend dependencies already installed"
else
    npm install
    if [ $? -ne 0 ]; then
        print_error "Failed to install frontend dependencies"
        exit 1
    fi
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
