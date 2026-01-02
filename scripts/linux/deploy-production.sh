#!/bin/bash
# Production Deployment Script for VPS
# Handles fresh deployments and updates with database migration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

echo "========================================"
echo " Production Deployment Script"
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
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Detect deployment type
DEPLOYMENT_TYPE="update"
DB_RESET=false

echo "[1/8] Detecting deployment type..."
if [ ! -f "instagram_automation.db" ] || [ ! -s "instagram_automation.db" ]; then
    DEPLOYMENT_TYPE="fresh"
    DB_RESET=true
    print_info "Fresh deployment detected (no existing database)"
else
    print_info "Update deployment detected (existing database found)"

    # Ask if user wants to reset database for update deployments
    echo ""
    echo -e "${YELLOW}Do you want to reset the database? (yes/no)${NC}"
    echo "  - Type 'yes' to delete existing data and recreate from baseline"
    echo "  - Type 'no' to keep existing data and run migrations normally"
    read -p "Reset database? " RESET_CHOICE

    if [ "$RESET_CHOICE" = "yes" ]; then
        DB_RESET=true
        print_warning "Database will be reset (backup will be created)"
    else
        print_info "Database will be preserved, running incremental migrations"
    fi
fi

# Pull latest code
echo ""
echo "[2/8] Pulling latest code from repository..."
if [ -d ".git" ]; then
    git pull origin main
    print_success "Code updated to latest version"
else
    print_warning "Not a git repository, skipping pull"
fi

# Set Python binary (try python3.12 first, fallback to python3)
echo ""
echo "[3/8] Detecting Python installation..."
if command -v python3.12 &> /dev/null; then
    export PYTHON_BIN="python3.12"
    print_success "Using Python 3.12"
elif command -v python3 &> /dev/null; then
    export PYTHON_BIN="python3"
    PYTHON_VERSION=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
    print_success "Using Python $PYTHON_VERSION"
else
    print_error "Python 3 not found"
    exit 1
fi

# Run installation script (handles venv, dependencies, frontend build)
echo ""
echo "[4/8] Running installation script..."
bash scripts/linux/install.sh

# Handle database setup
echo ""
if [ "$DB_RESET" = true ]; then
    echo "[5/8] Resetting database from baseline migration..."
    source venv/bin/activate
    python reset_db_and_migrations.py --force
    print_success "Database reset complete"
else
    echo "[5/8] Running incremental database migrations..."
    source venv/bin/activate
    alembic upgrade head
    print_success "Database migrations applied"
fi

# Create initial admin user if fresh deployment
if [ "$DEPLOYMENT_TYPE" = "fresh" ]; then
    echo ""
    echo "[6/8] Creating initial admin user..."
    print_info "You'll need to create an admin user for the web UI"
    echo ""
    python -m app.cli.manage_users
    print_success "User created"
else
    echo ""
    echo "[6/8] Skipping user creation (update deployment)"
fi

# Restart systemd service if it exists
echo ""
echo "[7/8] Restarting application service..."
if systemctl is-active --quiet insta-messaging; then
    print_info "Stopping existing service..."
    systemctl stop insta-messaging
    print_success "Service stopped"
fi

if [ -f "/etc/systemd/system/insta-messaging.service" ]; then
    systemctl daemon-reload
    systemctl start insta-messaging
    print_success "Service started"

    # Check service status
    sleep 2
    if systemctl is-active --quiet insta-messaging; then
        print_success "Service is running"
    else
        print_error "Service failed to start"
        echo "Check logs with: journalctl -u insta-messaging -n 50 --no-pager"
        exit 1
    fi
else
    print_warning "Systemd service not configured"
    print_info "To set up as service, create /etc/systemd/system/insta-messaging.service"
fi

# Deployment summary
echo ""
echo "[8/8] Deployment complete!"
echo ""
echo "========================================"
echo " Deployment Summary"
echo "========================================"
echo "Deployment type:  $DEPLOYMENT_TYPE"
echo "Database reset:   $DB_RESET"
echo "Service status:   $(systemctl is-active insta-messaging 2>/dev/null || echo 'not configured')"
echo ""
echo "Useful commands:"
echo "  - Check status:  systemctl status insta-messaging"
echo "  - View logs:     journalctl -u insta-messaging -f"
echo "  - Restart:       systemctl restart insta-messaging"
echo "  - Stop:          systemctl stop insta-messaging"
echo ""
echo "Frontend URL:     http://YOUR-DOMAIN/chat/"
echo "API Docs:         http://YOUR-DOMAIN/docs"
echo ""
echo "========================================"
echo ""
