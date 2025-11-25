# Production Deployment Guide

Complete guide for deploying Instagram Messenger Automation to Ubuntu VPS with GitHub Actions CI/CD.

## Overview

This setup provides:
- ✅ **Automated deployments** on every push to `main`
- ✅ **Zero-downtime updates** with systemd service restart
- ✅ **Secure secrets management** via GitHub Secrets
- ✅ **Full stack deployment**: Backend + Frontend + Nginx
- ✅ **Health checks** and automatic rollback on failure

---

## Prerequisites

### 1. Ubuntu VPS Server
- **Provider**: DigitalOcean, AWS EC2, Linode, Vultr, etc.
- **OS**: Ubuntu 22.04 LTS or 24.04 LTS (recommended)
- **Specs**: Minimum 1GB RAM, 1 CPU, 25GB storage
- **SSH Access**: Root or sudo user

### 2. Domain Name (Optional but recommended)
- Point your domain to your VPS IP address
- Example: `api.yourdomain.com` → `123.45.67.89`

### 3. Instagram Business Account
- Instagram Business Account ID
- Facebook App with Instagram permissions
- Access tokens and secrets

---

## Step-by-Step Setup

### Step 1: Prepare Your VPS

#### 1.1 Create a Droplet (DigitalOcean example)

```bash
# Or use any VPS provider:
# - AWS EC2: t2.micro (free tier eligible)
# - Linode: Nanode 1GB ($5/month)
# - Vultr: Cloud Compute ($6/month)
# - Hetzner: CX11 (€3.79/month)
```

**Recommended specs:**
- **RAM**: 1GB minimum, 2GB recommended
- **CPU**: 1 vCPU
- **Storage**: 25GB SSD
- **OS**: Ubuntu 22.04 LTS

#### 1.2 Initial Server Setup

SSH into your server:

```bash
ssh root@YOUR_SERVER_IP
```

Create a non-root user (optional but recommended):

```bash
# Create deploy user
adduser deploy
usermod -aG sudo deploy

# Switch to deploy user
su - deploy
```

#### 1.3 Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

### Step 2: Generate SSH Key for GitHub Actions

GitHub Actions will use SSH to connect to your VPS. Generate a dedicated key pair:

#### On your LOCAL machine (not the VPS):

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github-actions-vps

# This creates:
# - Private key: ~/.ssh/github-actions-vps (keep secret!)
# - Public key: ~/.ssh/github-actions-vps.pub
```

#### Copy public key to VPS:

```bash
# Copy public key to your VPS
ssh-copy-id -i ~/.ssh/github-actions-vps.pub root@YOUR_SERVER_IP

# Or manually:
# 1. Display public key
cat ~/.ssh/github-actions-vps.pub

# 2. On VPS, add to authorized_keys
mkdir -p ~/.ssh
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

#### Test SSH connection:

```bash
ssh -i ~/.ssh/github-actions-vps root@YOUR_SERVER_IP
```

If it works without password, you're ready! ✅

---

### Step 3: Configure GitHub Secrets

Go to your GitHub repository:

```
https://github.com/YOUR_USERNAME/insta-messaging/settings/secrets/actions
```

Click **"New repository secret"** and add the following:

#### VPS Connection Secrets

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `VPS_HOST` | Your VPS IP address or domain | `123.45.67.89` or `api.yourdomain.com` |
| `VPS_USER` | SSH username (usually `root`) | `root` |
| `VPS_SSH_KEY` | Private SSH key content | Contents of `~/.ssh/github-actions-vps` |
| `VPS_PORT` | SSH port (optional, defaults to 22) | `22` |

**How to get `VPS_SSH_KEY` value:**

```bash
# On your local machine:
cat ~/.ssh/github-actions-vps

# Copy ENTIRE output including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ... (all the lines)
# -----END OPENSSH PRIVATE KEY-----
```

#### Application Secrets

| Secret Name | Description | Where to Get |
|-------------|-------------|--------------|
| `FACEBOOK_VERIFY_TOKEN` | Webhook verification token | Create a random string (e.g., `my_verify_token_123`) |
| `FACEBOOK_APP_SECRET` | Facebook App Secret | Facebook Developers → Your App → Settings → Basic |
| `INSTAGRAM_APP_SECRET` | Instagram App Secret | Instagram settings in Facebook Developers |
| `INSTAGRAM_PAGE_ACCESS_TOKEN` | Page Access Token | Facebook Developers → Tools → Graph API Explorer |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Business Account ID | Graph API: `/me/accounts` then `/PAGE_ID?fields=instagram_business_account` |

#### Optional MySQL Secrets (if using CRM integration)

| Secret Name | Description |
|-------------|-------------|
| `CRM_MYSQL_ENABLED` | Set to `true` to enable |
| `CRM_MYSQL_HOST` | MySQL server hostname |
| `CRM_MYSQL_USER` | MySQL username |
| `CRM_MYSQL_PASSWORD` | MySQL password |
| `CRM_MYSQL_DATABASE` | MySQL database name |

---

### Step 4: Deploy!

#### Option 1: Automatic Deployment (Recommended)

Just push to main:

```bash
git push origin main
```

GitHub Actions will automatically:
1. Connect to your VPS via SSH ✅
2. Clone/update the repository ✅
3. Create `.env` with secrets ✅
4. Install Python 3.12, Nginx, dependencies ✅
5. Build frontend ✅
6. Run database migrations ✅
7. Start systemd service ✅
8. Configure Nginx ✅

Watch progress at:
```
https://github.com/YOUR_USERNAME/insta-messaging/actions
```

#### Option 2: Manual Deployment

SSH into your VPS and run:

```bash
# First time setup
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/insta-messaging/main/deploy-production.sh)"

# Or clone first:
git clone https://github.com/YOUR_USERNAME/insta-messaging.git /opt/insta-messaging
cd /opt/insta-messaging
sudo bash deploy-production.sh
```

---

### Step 5: Configure Domain & SSL (Optional but recommended)

If you have a domain name:

#### 5.1 Point Domain to VPS

Add DNS A record:
```
Type: A
Name: api (or @)
Value: YOUR_VPS_IP
TTL: 3600
```

Wait for DNS propagation (5-60 minutes):
```bash
dig api.yourdomain.com +short
# Should return your VPS IP
```

#### 5.2 Install SSL Certificate (Let's Encrypt)

On your VPS:

```bash
# Install Certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d api.yourdomain.com

# Follow prompts:
# - Enter email
# - Agree to terms
# - Choose redirect HTTP → HTTPS (option 2)

# Auto-renewal is configured automatically!
# Test renewal:
sudo certbot renew --dry-run
```

Your app is now available at:
```
https://api.yourdomain.com
https://api.yourdomain.com/docs
https://api.yourdomain.com/chat
```

---

## Deployment Workflow Explained

### What Happens on Each Deployment

```
┌─────────────────────────────────────────────────────────┐
│ 1. Push to main branch                                  │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 2. GitHub Actions triggered                             │
│    - Checks out code                                    │
│    - Connects to VPS via SSH                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3. On VPS: Check if first deployment or update         │
└──────────────────┬──────────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
   First Time              Update
       │                       │
       ▼                       ▼
 Run deploy-           Pull latest code
 production.sh         Update .env
       │               Update deps
       │               Build frontend
       │               Restart service
       │                       │
       └───────────┬───────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Health check                                         │
│    - Check systemd service status                      │
│    - Call /health endpoint                             │
│    - If failed: abort & show logs                      │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 5. ✅ Deployment complete!                              │
└─────────────────────────────────────────────────────────┘
```

### File Structure on VPS

```
/opt/insta-messaging/
├── app/                      # Backend Python code
├── frontend/                 # Vue.js source
│   └── dist/                 # Built frontend (served by Nginx)
├── venv/                     # Python virtual environment
├── data/                     # SQLite database
│   └── production.db
├── .env                      # Secrets (chmod 600)
├── requirements.txt
└── alembic/                  # Database migrations

/etc/systemd/system/
└── insta-messaging.service   # Systemd service

/etc/nginx/sites-available/
└── insta-messaging           # Nginx config

/var/log/
└── insta-messaging/          # Application logs
```

---

## Verification & Testing

### Check Service Status

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Check systemd service
sudo systemctl status insta-messaging

# Check logs
sudo journalctl -u insta-messaging -f

# Check Nginx
sudo systemctl status nginx
sudo nginx -t  # Test config

# Check health endpoint
curl http://localhost:8000/health
```

### Test Application

```bash
# Backend health check
curl https://YOUR_DOMAIN/health

# API documentation
curl https://YOUR_DOMAIN/docs

# Frontend
curl https://YOUR_DOMAIN/chat/
```

### Check Instagram Webhook

1. Go to Facebook Developers: https://developers.facebook.com/apps/
2. Select your app → Products → Webhooks
3. Edit Instagram subscription
4. Set callback URL: `https://YOUR_DOMAIN/webhooks/instagram`
5. Set verify token: (use `FACEBOOK_VERIFY_TOKEN` from secrets)
6. Subscribe to `messages` events
7. Click "Send Test Request" - should return 200 OK

---

## Monitoring & Maintenance

### View Logs

```bash
# Real-time logs
sudo journalctl -u insta-messaging -f

# Last 100 lines
sudo journalctl -u insta-messaging -n 100

# Errors only
sudo journalctl -u insta-messaging -p err

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Restart Services

```bash
# Restart app
sudo systemctl restart insta-messaging

# Restart Nginx
sudo systemctl restart nginx

# Check status
sudo systemctl status insta-messaging
sudo systemctl status nginx
```

### Update Application

Just push to main - automatic deployment!

```bash
git add .
git commit -m "Update feature"
git push origin main

# GitHub Actions handles the rest
```

### Database Backups

```bash
# Manual backup
sudo -u insta-messaging sqlite3 /opt/insta-messaging/data/production.db ".backup /opt/insta-messaging/data/backup-$(date +%Y%m%d).db"

# Automated backup (add to crontab)
sudo crontab -e -u insta-messaging

# Add this line (daily backup at 2 AM):
0 2 * * * sqlite3 /opt/insta-messaging/data/production.db ".backup /opt/insta-messaging/data/backup-$(date +\%Y\%m\%d).db"
```

---

## Troubleshooting

### Deployment Failed

**Check GitHub Actions logs:**
```
https://github.com/YOUR_USERNAME/insta-messaging/actions
```

**Common issues:**

#### 1. SSH Connection Failed
```
Error: ssh: connect to host ... Connection refused
```

**Fix:**
- Check `VPS_HOST` secret is correct IP/domain
- Check `VPS_PORT` (default 22)
- Verify firewall allows SSH: `sudo ufw status`
- Test SSH manually: `ssh -i ~/.ssh/github-actions-vps root@YOUR_VPS_IP`

#### 2. Permission Denied (publickey)
```
Error: Permission denied (publickey)
```

**Fix:**
- Verify `VPS_SSH_KEY` secret contains ENTIRE private key
- Check public key is in VPS `~/.ssh/authorized_keys`
- Check permissions: `chmod 600 ~/.ssh/authorized_keys`

#### 3. Service Failed to Start
```
Error: Service failed to start!
```

**Fix:**
```bash
# SSH to VPS
ssh root@YOUR_VPS_IP

# Check logs
sudo journalctl -u insta-messaging -n 50

# Common issues:
# - Missing .env file
# - Wrong Python version
# - Port 8000 already in use
# - Database migration failed
```

#### 4. Python Version Mismatch
```
Error: Python version is too old
```

**Fix:**
- Deployment script installs Python 3.12 automatically
- If failed, manually install:
  ```bash
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install python3.12 python3.12-venv python3.12-dev
  ```

#### 5. Nginx 502 Bad Gateway
```
502 Bad Gateway
```

**Fix:**
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not running:
sudo systemctl status insta-messaging
sudo systemctl restart insta-messaging

# Check Nginx config
sudo nginx -t
sudo systemctl restart nginx
```

---

## Security Best Practices

### ✅ DO:

- **Use SSH keys** (not passwords)
- **Enable firewall** (ufw)
- **Use HTTPS/SSL** (Let's Encrypt)
- **Set `.env` to 600 permissions** (done automatically)
- **Rotate secrets** every 90 days
- **Use strong passwords** for database
- **Monitor logs** regularly
- **Keep system updated**: `sudo apt update && sudo apt upgrade`

### ❌ DON'T:

- Commit secrets to git
- Use root user for app (app runs as `insta-messaging` user)
- Expose port 8000 directly (Nginx proxies it)
- Disable firewall
- Use HTTP without HTTPS in production
- Share SSH private keys

---

## Scaling & Performance

### Vertical Scaling (Upgrade VPS)

If you need more resources:

**DigitalOcean:**
```
Current: $6/month (1GB RAM)
Upgrade: $12/month (2GB RAM)
Upgrade: $24/month (4GB RAM)
```

**How to upgrade:**
1. Power off droplet
2. Resize in DigitalOcean dashboard
3. Power on
4. No code changes needed!

### Horizontal Scaling (Multiple Servers)

For high traffic:
1. Add load balancer (DigitalOcean Load Balancer: $12/month)
2. Deploy to multiple VPS instances
3. Use PostgreSQL/MySQL instead of SQLite
4. Consider Redis for caching

---

## Cost Breakdown

### Minimum Setup

| Item | Provider | Cost |
|------|----------|------|
| VPS (1GB RAM) | DigitalOcean | $6/month |
| Domain Name | Namecheap | $12/year ($1/month) |
| SSL Certificate | Let's Encrypt | **FREE** ✅ |
| GitHub Actions | GitHub | **FREE** ✅ (2000 min/month) |
| **Total** | | **~$7/month** |

### Recommended Setup

| Item | Provider | Cost |
|------|----------|------|
| VPS (2GB RAM) | DigitalOcean | $12/month |
| Domain Name | Namecheap | $12/year ($1/month) |
| SSL Certificate | Let's Encrypt | **FREE** ✅ |
| **Total** | | **~$13/month** |

---

## Next Steps

1. ✅ Add all GitHub Secrets
2. ✅ Push to main branch
3. ✅ Watch deployment in GitHub Actions
4. ✅ Configure domain & SSL
5. ✅ Set up Instagram webhooks
6. ✅ Test with real Instagram messages
7. ✅ Monitor logs and performance

---

## Support

- **Issues**: https://github.com/YOUR_USERNAME/insta-messaging/issues
- **Documentation**: See `/docs` folder
- **Deployment Logs**: GitHub Actions tab

Happy deploying! 🚀
