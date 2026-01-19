#!/bin/bash
# Nginx Configuration Script for Instagram Messaging
# Usage: sudo bash configure-nginx.sh [app_name] [install_dir] [domain_name]
#
# Arguments:
#   app_name    - Name of the app (default: insta-messaging)
#   install_dir - Installation directory (default: /opt/insta-messaging)
#   domain_name - Domain name for SSL (optional, default: _ for catch-all)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="${1:-insta-messaging}"
INSTALL_DIR="${2:-/opt/insta-messaging}"
DOMAIN_NAME="${3:-_}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo -e "${RED}ERROR: This script must be run as root${NC}"
   echo "Usage: sudo bash configure-nginx.sh [app_name] [install_dir]"
   exit 1
fi

echo -e "${GREEN}Configuring Nginx for ${APP_NAME}...${NC}"
echo "Installation directory: ${INSTALL_DIR}"
echo "Domain name: ${DOMAIN_NAME}"
echo ""

# Remove default site if it exists
if [ -L /etc/nginx/sites-enabled/default ]; then
    echo "Removing default nginx site..."
    rm -f /etc/nginx/sites-enabled/default
fi

# Create nginx configuration
echo "Creating nginx configuration..."
cat > /etc/nginx/sites-available/${APP_NAME} <<NGINX_EOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};
    client_max_body_size 10M;

    # Frontend (served from /chat/ path)
    location /chat/ {
        alias /opt/insta-messaging/frontend/dist/;
        try_files \$uri \$uri/ /chat/index.html;
        add_header Cache-Control "no-cache";
    }

    # Root redirects to /chat/
    location = / {
        return 301 /chat/;
    }

    # API endpoints (with SSE support)
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        # SSE-specific settings
        proxy_buffering off;
        proxy_read_timeout 24h;
        proxy_connect_timeout 24h;
        proxy_send_timeout 24h;
    }

    # Webhooks
    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000/webhooks/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # OAuth callbacks
    location /oauth/ {
        proxy_pass http://127.0.0.1:8000/oauth/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Media files
    location /media/ {
        proxy_pass http://127.0.0.1:8000/media/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    # API docs
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }

    # Redoc
    location /redoc {
        proxy_pass http://127.0.0.1:8000/redoc;
    }
}
NGINX_EOF

echo "✓ Nginx configuration created at /etc/nginx/sites-available/${APP_NAME}"

# Enable site
echo "Enabling nginx site..."
ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/
echo "✓ Nginx site enabled"

# Test nginx config
echo "Testing nginx configuration..."
if nginx -t 2>&1 | tee /tmp/nginx-test.log; then
    echo -e "${GREEN}✅ Nginx configuration is valid${NC}"
else
    echo -e "${RED}❌ Nginx configuration test failed!${NC}"
    cat /tmp/nginx-test.log
    exit 1
fi

# Reload nginx
echo "Reloading nginx..."
systemctl reload nginx || systemctl restart nginx

# Check nginx status
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx is running${NC}"
else
    echo -e "${RED}❌ Nginx failed to start${NC}"
    systemctl status nginx --no-pager -l | head -20
    exit 1
fi

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}✅ Nginx configuration complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
if [ "${DOMAIN_NAME}" != "_" ]; then
    echo "Nginx is configured for domain: ${DOMAIN_NAME}"
    echo ""
    echo "Endpoints:"
    echo "  - Frontend:  http://${DOMAIN_NAME}/chat/"
    echo "  - API:       http://${DOMAIN_NAME}/api/"
    echo "  - Webhooks:  http://${DOMAIN_NAME}/webhooks/"
    echo "  - Docs:      http://${DOMAIN_NAME}/docs"
    echo ""
    echo -e "${YELLOW}⚠️  To enable HTTPS, run:${NC}"
    echo "  certbot --nginx -d ${DOMAIN_NAME}"
else
    echo "Nginx is configured with catch-all server_name"
    echo ""
    echo "Endpoints (replace YOUR_IP with your server IP):"
    echo "  - Frontend:  http://YOUR_IP/chat/"
    echo "  - API:       http://YOUR_IP/api/"
    echo "  - Webhooks:  http://YOUR_IP/webhooks/"
    echo "  - Docs:      http://YOUR_IP/docs"
fi
echo ""
