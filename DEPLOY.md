# Deployment Guide

## Quick Deploy

```bash
# 1. Clone repo
git clone <repo-url>
cd instagram-messenger-automation

# 2. Deploy (creates venv, installs deps, runs migrations)
chmod +x deploy.sh start.sh start-daemon.sh stop-daemon.sh status-daemon.sh
./deploy.sh

# 3. Edit .env with your credentials
nano .env

# 4a. Start in foreground (for testing)
./start.sh

# 4b. Or start as daemon (for production)
./start-daemon.sh
```

## Required Environment Variables

Edit `.env`:
```env
FACEBOOK_VERIFY_TOKEN=your_token
FACEBOOK_APP_SECRET=your_secret
INSTAGRAM_APP_SECRET=your_instagram_secret
INSTAGRAM_PAGE_ACCESS_TOKEN=your_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_id
ENVIRONMENT=production
```

## Background Service (Daemon)

```bash
# Start in background
./start-daemon.sh

# Check status
./status-daemon.sh

# View logs
tail -f server.log

# Stop
./stop-daemon.sh
```

## Python 3.11+ Required

If Python too old, install with pyenv (no root needed):
```bash
curl https://pyenv.run | bash
export TMPDIR=~/tmp  # If /tmp has noexec
pyenv install 3.12.0
pyenv global 3.12.0
```

## Update Application

```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
./stop-daemon.sh && ./start-daemon.sh
```

## Health Check

```bash
curl http://localhost:8000/health
```

Open Swagger UI: `http://localhost:8000/docs`
