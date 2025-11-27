#!/bin/bash
# Production Deployment Script for Instagram Messenger Automation
# Target: DigitalOcean Droplet (Ubuntu/Debian)
# Usage: sudo bash deploy-production.sh

set -e  # Exit on error

# Disable interactive prompts for apt and service restarts
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

echo "=============================================="
echo "Instagram Messenger - Production Deployment"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="insta-messaging"
INSTALL_DIR="/opt/${APP_NAME}"
APP_USER="${APP_NAME}"
SERVICE_NAME="${APP_NAME}"
REPO_URL="https://github.com/november1306/insta-messaging.git"
BRANCH="main"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo -e "${RED}ERROR: This script must be run as root${NC}"
   echo "Usage: sudo bash deploy-production.sh"
   exit 1
fi

echo -e "${GREEN}[1/13] Checking system...${NC}"
echo "OS: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "Architecture: $(uname -m)"
echo ""

echo -e "${GREEN}[2/13] Updating system packages...${NC}"

# Remove potentially broken PPAs from previous attempts
if ls /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-*.list 2>/dev/null; then
    echo "Removing previously added deadsnakes PPA..."
    rm -f /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-*.list
fi

# Update package lists (ignore PPA errors if any)
apt-get update -qq 2>&1 | grep -v "does not have a Release file" | grep -v "deadsnakes" || true

# Disable needrestart interactive prompts during upgrade
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1
apt-get upgrade -y -qq

echo -e "${GREEN}[3/13] Installing system dependencies...${NC}"
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1
apt-get install -y -qq \
    software-properties-common \
    git \
    nginx \
    curl \
    ufw \
    sqlite3 \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev

# Install Python 3.12 (required)
echo -e "${GREEN}[4/13] Checking for Python 3.12...${NC}"

# Function to get Python version
get_python_version() {
    $1 --version 2>&1 | awk '{print $2}'
}

# Check if Python 3.12 is already installed
PYTHON_BIN=""
if command -v python3.12 &> /dev/null; then
    version=$(get_python_version python3.12)
    echo "Found Python 3.12 (version $version)"
    PYTHON_BIN="python3.12"
fi

# If Python 3.12 not found, install it
if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3.12 not found. Installing..."

    # Try to install from standard repositories first
    if apt-cache show python3.12 &> /dev/null; then
        echo "Installing python3.12 from standard repositories..."
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
        PYTHON_BIN="python3.12"
    else
        # Try deadsnakes PPA
        echo "Python 3.12 not in standard repos, trying deadsnakes PPA..."
        if add-apt-repository -y ppa:deadsnakes/ppa 2>&1 | grep -q "does not have a Release file"; then
            echo -e "${RED}Error: Cannot install Python 3.12${NC}"
            echo "Your Ubuntu version does not have Python 3.12 in standard repos,"
            echo "and the deadsnakes PPA is not yet available for this release."
            echo ""
            echo "Please install Python 3.12 manually and re-run this script."
            exit 1
        else
            # PPA added successfully
            apt-get update -qq 2>&1 | grep -v "does not have a Release file" || true
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12 python3.12-venv python3.12-dev python3-pip
            PYTHON_BIN="python3.12"
            echo "Python 3.12 installed successfully from deadsnakes PPA"
        fi
    fi
else
    # Make sure venv and dev packages are installed for python3.12
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12-venv python3.12-dev 2>/dev/null || true
fi

# Ensure pip is installed
if ! command -v pip3 &> /dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip
fi

echo "Using Python: $PYTHON_BIN ($(get_python_version $PYTHON_BIN))"

# Install Node.js and npm
echo -e "${GREEN}[5/13] Installing Node.js and npm...${NC}"
if ! command -v node &> /dev/null; then
    echo "Installing Node.js from NodeSource repository..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
    echo "Node.js $(node --version) installed"
    echo "npm $(npm --version) installed"
else
    echo "Node.js already installed: $(node --version)"
    echo "npm version: $(npm --version)"
fi

echo -e "${GREEN}[6/13] Creating application user...${NC}"
if ! id -u ${APP_USER} > /dev/null 2>&1; then
    useradd -r -s /bin/bash -d ${INSTALL_DIR} ${APP_USER}
    echo "Created user: ${APP_USER}"
else
    echo "User ${APP_USER} already exists"
fi

echo -e "${GREEN}[7/13] Setting up application directory...${NC}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "Repository exists, updating..."
    cd ${INSTALL_DIR}

    # Fix git ownership issues (directory may have been created by root)
    git config --global --add safe.directory ${INSTALL_DIR}
    chown -R ${APP_USER}:${APP_USER} ${INSTALL_DIR}

    sudo -u ${APP_USER} git fetch origin
    sudo -u ${APP_USER} git checkout ${BRANCH}
    sudo -u ${APP_USER} git pull origin ${BRANCH}
else
    echo "Cloning repository..."
    if [ -d "${INSTALL_DIR}" ]; then
        rm -rf ${INSTALL_DIR}
    fi
    # Clone as root, then change ownership
    git clone -b ${BRANCH} ${REPO_URL} ${INSTALL_DIR}
    chown -R ${APP_USER}:${APP_USER} ${INSTALL_DIR}
    cd ${INSTALL_DIR}
fi

# Create data directory for SQLite database (before running install.sh)
echo ""
echo "Creating data directory for database..."
mkdir -p ${INSTALL_DIR}/data
chown ${APP_USER}:${APP_USER} ${INSTALL_DIR}/data
chmod 755 ${INSTALL_DIR}/data
echo "Data directory created: ${INSTALL_DIR}/data"

echo -e "${GREEN}[8/13] Running application deployment script...${NC}"
chmod +x ${INSTALL_DIR}/scripts/linux/install.sh
sudo -u ${APP_USER} PYTHON_BIN="${PYTHON_BIN}" bash ${INSTALL_DIR}/scripts/linux/install.sh

echo -e "${GREEN}[9/13] Configuring environment...${NC}"
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
    sudo -u ${APP_USER} cp ${INSTALL_DIR}/.env.example ${INSTALL_DIR}/.env
    chmod 600 ${INSTALL_DIR}/.env
    chown ${APP_USER}:${APP_USER} ${INSTALL_DIR}/.env

    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}⚠️  IMPORTANT: Configure .env file${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo "Edit ${INSTALL_DIR}/.env and add your Instagram API credentials"
    echo ""
    echo "Required variables:"
    echo "  - FACEBOOK_VERIFY_TOKEN"
    echo "  - FACEBOOK_APP_SECRET"
    echo "  - INSTAGRAM_APP_SECRET"
    echo "  - INSTAGRAM_PAGE_ACCESS_TOKEN"
    echo "  - INSTAGRAM_BUSINESS_ACCOUNT_ID"
    echo "  - ENVIRONMENT=production"
    echo ""
    read -p "Press ENTER to edit .env now (or Ctrl+C to cancel): "
    nano ${INSTALL_DIR}/.env
else
    echo ".env file exists, skipping configuration"
    # Ensure production environment
    if ! grep -q "ENVIRONMENT=production" ${INSTALL_DIR}/.env; then
        echo "Setting ENVIRONMENT=production in .env"
        echo "ENVIRONMENT=production" >> ${INSTALL_DIR}/.env
    fi
fi

echo -e "${GREEN}[10/13] Creating systemd service...${NC}"
cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Instagram Messenger Automation API
Documentation=https://github.com/november1306/insta-messaging
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=${INSTALL_DIR}/.env

# Start command
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=5min
StartLimitBurst=5

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
echo "Systemd service created: ${SERVICE_NAME}.service"

echo -e "${GREEN}[11/13] Configuring Nginx reverse proxy...${NC}"

# Install htpasswd utility if not present
if ! command -v htpasswd &> /dev/null; then
    echo "Installing apache2-utils for htpasswd..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq apache2-utils
fi

# Create HTTP Basic Auth password file for /chat
echo "Creating HTTP Basic Auth credentials..."
htpasswd -cbB /etc/nginx/.htpasswd admin 'InstaChatTest2025'
chmod 644 /etc/nginx/.htpasswd

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Create nginx config with HTTP Basic Auth for /chat
cat > /etc/nginx/sites-available/${APP_NAME} <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Client body size
    client_max_body_size 10M;

    # Logging
    access_log /var/log/nginx/insta-messaging-access.log;
    error_log /var/log/nginx/insta-messaging-error.log;

    # Protected /chat UI with HTTP Basic Auth
    location /chat {
        auth_basic "Instagram Chat - Login Required";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API endpoints - require API key authentication (no HTTP Basic Auth)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }

    # Webhooks - no auth (Instagram needs to call this)
    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }

    # Default proxy for everything else
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/

# Test nginx config
nginx -t

echo -e "${GREEN}[12/13] Configuring firewall (UFW)...${NC}"
# Allow SSH, HTTP, HTTPS
ufw --force disable
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS (future SSL)'

# Set default policies
ufw default deny incoming
ufw default allow outgoing

# Enable firewall
echo "y" | ufw enable

echo -e "${GREEN}[13/13] Starting services...${NC}"

# Start nginx
systemctl restart nginx
systemctl status nginx --no-pager -l | head -5

echo ""

# Start application
systemctl restart ${SERVICE_NAME}
sleep 3
systemctl status ${SERVICE_NAME} --no-pager -l | head -10

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}✅ Production Deployment Complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me || echo "your-droplet-ip")

echo "Your application is now running!"
echo ""
echo "📍 Access URLs:"
echo -e "   API Docs:      ${GREEN}http://${PUBLIC_IP}/docs${NC}"
echo -e "   Health Check:  ${GREEN}http://${PUBLIC_IP}/health${NC}"
echo -e "   Webhook URL:   ${GREEN}http://${PUBLIC_IP}/webhooks/instagram${NC}"
echo ""
echo "🔧 Management Commands:"
echo "   Service status:   sudo systemctl status ${SERVICE_NAME}"
echo "   Restart service:  sudo systemctl restart ${SERVICE_NAME}"
echo "   View logs:        sudo journalctl -u ${SERVICE_NAME} -f"
echo "   Nginx logs:       sudo tail -f /var/log/nginx/insta-messaging-*.log"
echo ""
echo "📝 Configuration:"
echo "   Edit .env:        sudo nano ${INSTALL_DIR}/.env"
echo "   After editing:    sudo systemctl restart ${SERVICE_NAME}"
echo ""
echo "🔒 Security:"
echo "   Firewall status:  sudo ufw status"
echo "   SSH port 22:      ✅ Allowed"
echo "   HTTP port 80:     ✅ Allowed"
echo ""
echo "⚠️  Next Steps:"
echo "1. Configure Instagram webhook in Facebook Developer Console:"
echo "   URL: http://${PUBLIC_IP}/webhooks/instagram"
echo "   Verify Token: (use your FACEBOOK_VERIFY_TOKEN from .env)"
echo ""
echo "2. Test your API:"
echo "   curl http://${PUBLIC_IP}/health"
echo ""
echo "3. Monitor logs for any errors:"
echo "   sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
