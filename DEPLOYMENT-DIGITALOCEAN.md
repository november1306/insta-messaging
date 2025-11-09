# DigitalOcean Droplet Deployment Guide

Complete guide for deploying Instagram Messenger Automation to a DigitalOcean droplet.

## Prerequisites

- DigitalOcean droplet (Ubuntu 20.04+, Debian 11+, or similar)
- Root or sudo access
- Instagram Business Account with API credentials
- Minimum 1GB RAM, 1 CPU core

## Quick Reference

| Deployment Type | Use Case | Time | Auto-restart | Nginx |
|----------------|----------|------|--------------|-------|
| **Development** (Option 1) | Testing, dev | 5 min | ❌ No | ❌ No |
| **Production** (Option 2) | Live use | 15 min | ✅ Yes | ✅ Yes |

---

## Option 1: Development Deployment (Quick)

Best for: Testing, development, temporary deployments

### Steps:

```bash
# 1. SSH into your droplet
ssh root@your-droplet-ip

# 2. Clone repository
git clone https://github.com/november1306/insta-messaging.git
cd insta-messaging

# 3. Run deployment
chmod +x *.sh
./deploy.sh

# 4. Configure credentials
nano .env
# Add your Instagram API credentials

# 5. Start service
./start-daemon.sh
```

### Access Your API:
- **API Docs:** `http://your-droplet-ip:8000/docs`
- **Health Check:** `http://your-droplet-ip:8000/health`
- **Webhook:** `http://your-droplet-ip:8000/webhooks/instagram`

### Management:
```bash
# Check status
./status-daemon.sh

# View logs
tail -f server.log

# Stop service
./stop-daemon.sh

# Restart service
./stop-daemon.sh && ./start-daemon.sh
```

### ⚠️ Limitations:
- Service will NOT restart on reboot
- Service will NOT restart if it crashes
- No reverse proxy (must use port 8000)
- No firewall configuration

---

## Option 2: Production Deployment (Recommended)

Best for: Production use, long-term deployments, mission-critical applications

### Features:
- ✅ Systemd service (auto-start on boot)
- ✅ Nginx reverse proxy (cleaner URLs, port 80)
- ✅ Automatic restart on crash
- ✅ Firewall configured (UFW)
- ✅ Proper logging (journald + nginx)
- ✅ Security hardening

### Single-Command Deployment:

```bash
# SSH into droplet
ssh root@your-droplet-ip

# Clone and deploy
git clone https://github.com/november1306/insta-messaging.git
cd insta-messaging
chmod +x deploy-production.sh
sudo bash deploy-production.sh
```

The script will:
1. Update system packages
2. Install Python 3.12, Nginx, dependencies
3. Create dedicated app user
4. Clone repository to `/opt/insta-messaging`
5. Set up Python virtual environment
6. Install application dependencies
7. Run database migrations
8. Prompt you to configure `.env` file
9. Create systemd service
10. Configure Nginx reverse proxy
11. Set up firewall (UFW)
12. Start all services

### Access Your API:
- **API Docs:** `http://your-droplet-ip/docs`
- **Health Check:** `http://your-droplet-ip/health`
- **Webhook:** `http://your-droplet-ip/webhooks/instagram`

### Management:

```bash
# Service management
sudo systemctl status insta-messaging
sudo systemctl restart insta-messaging
sudo systemctl stop insta-messaging
sudo systemctl start insta-messaging

# View application logs
sudo journalctl -u insta-messaging -f          # Follow logs
sudo journalctl -u insta-messaging --since "1 hour ago"

# View nginx logs
sudo tail -f /var/log/nginx/insta-messaging-access.log
sudo tail -f /var/log/nginx/insta-messaging-error.log

# Edit configuration
sudo nano /opt/insta-messaging/.env
sudo systemctl restart insta-messaging  # After editing

# Check firewall
sudo ufw status
```

---

## Environment Configuration

Edit `/opt/insta-messaging/.env` (production) or `.env` (development):

```env
# Instagram/Facebook Credentials
FACEBOOK_VERIFY_TOKEN=your_custom_verify_token
FACEBOOK_APP_SECRET=your_facebook_app_secret
INSTAGRAM_APP_SECRET=your_instagram_app_secret
INSTAGRAM_PAGE_ACCESS_TOKEN=your_instagram_page_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_business_account_id

# Server Configuration
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO

# Database
DATABASE_URL=sqlite+aiosqlite:///./instagram_automation.db
```

### Where to Get Credentials:

| Variable | How to Get It |
|----------|---------------|
| `FACEBOOK_VERIFY_TOKEN` | Create your own random string (e.g., `my_webhook_123`) |
| `FACEBOOK_APP_SECRET` | Facebook Developer Console → App → Settings → Basic |
| `INSTAGRAM_APP_SECRET` | Instagram app settings (may be same as Facebook) |
| `INSTAGRAM_PAGE_ACCESS_TOKEN` | Facebook Developer Console → Instagram → Token Generator (starts with `IGAA`) |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Found in Instagram API responses or webhook payloads |

---

## Instagram Webhook Setup

After deployment, configure Instagram webhooks in Facebook Developer Console:

1. Go to: **Facebook Developer Console** → Your App → **Instagram** → **Webhooks**
2. Click **"Edit Subscription"** or **"Add Callback URL"**
3. Enter:
   - **Callback URL:** `http://your-droplet-ip/webhooks/instagram`
   - **Verify Token:** Your `FACEBOOK_VERIFY_TOKEN` from `.env`
4. Subscribe to fields:
   - `messages`
   - `messaging_postbacks` (optional)
   - `message_echoes` (optional)
5. Click **"Verify and Save"**

---

## Updating the Application

### Production (Option 2):
```bash
cd /opt/insta-messaging
sudo -u insta-messaging git pull origin main
sudo -u insta-messaging source venv/bin/activate
sudo -u insta-messaging pip install -r requirements.txt
sudo -u insta-messaging alembic upgrade head
sudo systemctl restart insta-messaging
```

### Development (Option 1):
```bash
cd ~/insta-messaging
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
./stop-daemon.sh && ./start-daemon.sh
```

---

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u insta-messaging -n 50

# Check if port 8000 is already in use
sudo lsof -i :8000

# Verify .env file exists and has correct credentials
sudo cat /opt/insta-messaging/.env
```

### Webhook verification fails

1. Check `INSTAGRAM_APP_SECRET` matches your Instagram app settings
2. Verify webhook URL is publicly accessible: `curl http://your-ip/webhooks/instagram`
3. Check logs for signature validation errors: `sudo journalctl -u insta-messaging -f`

### Messages not sending

1. Verify `INSTAGRAM_PAGE_ACCESS_TOKEN` starts with `IGAA`
2. Check token hasn't expired
3. Ensure recipient messaged you first (Instagram 24h rule)
4. Check logs: `sudo journalctl -u insta-messaging -f`

### Can't access API

```bash
# Check if service is running
sudo systemctl status insta-messaging

# Check nginx
sudo systemctl status nginx

# Test directly on server
curl http://localhost:8000/health

# Check firewall
sudo ufw status
```

---

## Security Best Practices

1. **Change default ports** - Consider using non-standard ports
2. **Add SSL/TLS** - Use Let's Encrypt for HTTPS (requires domain name)
3. **Restrict firewall** - Only allow necessary IPs if possible
4. **Rotate tokens** - Regularly update Instagram API tokens
5. **Monitor logs** - Set up log monitoring/alerts
6. **Keep updated** - Regularly pull updates and security patches

### Adding SSL (Requires Domain):

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Point your domain to droplet IP first
# Then run:
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

---

## Performance Tuning

For high-traffic deployments:

### Increase worker processes:

Edit `/etc/systemd/system/insta-messaging.service`:
```ini
ExecStart=/opt/insta-messaging/venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 4
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart insta-messaging`

### Optimize Nginx:

Edit `/etc/nginx/sites-available/insta-messaging` and add:
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location / {
    limit_req zone=api_limit burst=20;
    # ... existing config
}
```

---

## Monitoring

### Set up basic monitoring:

```bash
# Install monitoring tools
sudo apt-get install htop iotop

# Check system resources
htop

# Monitor disk usage
df -h

# Check application status
watch -n 5 'systemctl status insta-messaging'
```

### Health check endpoint:

```bash
# Use cron to ping health endpoint
echo "*/5 * * * * curl -s http://localhost/health || echo 'Service down!' | mail -s 'Alert' you@email.com" | crontab -
```

---

## Uninstalling

### Complete removal:

```bash
# Stop services
sudo systemctl stop insta-messaging
sudo systemctl disable insta-messaging

# Remove files
sudo rm /etc/systemd/system/insta-messaging.service
sudo rm /etc/nginx/sites-enabled/insta-messaging
sudo rm /etc/nginx/sites-available/insta-messaging
sudo rm -rf /opt/insta-messaging

# Remove user
sudo userdel -r insta-messaging

# Reload services
sudo systemctl daemon-reload
sudo systemctl restart nginx
```

---

## Support

For issues:
1. Check logs: `sudo journalctl -u insta-messaging -f`
2. Review API docs: `http://your-ip/docs`
3. Check troubleshooting section above
4. Review Instagram API documentation

---

## Summary

**Quick Start (Development):**
```bash
git clone <repo> && cd insta-messaging
./deploy.sh && nano .env && ./start-daemon.sh
```

**Production Deployment:**
```bash
git clone <repo> && cd insta-messaging
sudo bash deploy-production.sh
```

Both work great - choose based on your needs! 🚀
