# Secrets Management Guide

## Overview

This guide covers secure ways to handle sensitive data (tokens, API keys, passwords) for the Instagram Messenger Automation app across different deployment scenarios.

## Security Levels (Best → Good)

### 🥇 Level 1: Systemd Environment Files (Recommended for Production)

**Best for:** DigitalOcean, AWS EC2, any Linux server with systemd

**Advantages:**
- ✅ Secrets never stored in git
- ✅ Restricted file permissions (600)
- ✅ Managed by systemd (process isolation)
- ✅ No secrets in process environment visible to other users
- ✅ No code changes needed

**How it works:**
1. Store secrets in GitHub Secrets
2. Deploy script creates `/opt/insta-messaging/.env` with 600 permissions
3. Systemd service loads environment from file
4. Only the app user can read the file

**Implementation:**

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/insta-messaging

            # Create .env with secrets (only if doesn't exist)
            if [ ! -f .env ]; then
              cat > .env <<EOF
            FACEBOOK_VERIFY_TOKEN=${{ secrets.FACEBOOK_VERIFY_TOKEN }}
            FACEBOOK_APP_SECRET=${{ secrets.FACEBOOK_APP_SECRET }}
            INSTAGRAM_APP_SECRET=${{ secrets.INSTAGRAM_APP_SECRET }}
            INSTAGRAM_PAGE_ACCESS_TOKEN=${{ secrets.INSTAGRAM_PAGE_ACCESS_TOKEN }}
            INSTAGRAM_BUSINESS_ACCOUNT_ID=${{ secrets.INSTAGRAM_BUSINESS_ACCOUNT_ID }}
            CRM_MYSQL_PASSWORD=${{ secrets.CRM_MYSQL_PASSWORD }}
            DATABASE_URL=sqlite+aiosqlite:////opt/insta-messaging/data/production.db
            ENVIRONMENT=production
            USE_STUB_AUTH=false
            EOF
              chmod 600 .env
              chown insta-messaging:insta-messaging .env
            fi

            # Pull latest code
            git pull origin main

            # Restart service
            systemctl restart insta-messaging
```

**Current systemd service (already configured):**
```ini
# /etc/systemd/system/insta-messaging.service
[Service]
User=insta-messaging
Group=insta-messaging
WorkingDirectory=/opt/insta-messaging
EnvironmentFile=/opt/insta-messaging/.env  # ← Loads secrets here
ExecStart=/opt/insta-messaging/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**File permissions:**
```bash
-rw------- 1 insta-messaging insta-messaging  .env  # Only app user can read
```

---

### 🥈 Level 2: Direct Environment Variables in Systemd

**Best for:** High-security deployments, compliance requirements

**Advantages:**
- ✅ No secrets on disk at all
- ✅ Secrets only in systemd config (protected by OS permissions)
- ✅ Each secret can be rotated individually

**How it works:**
Secrets are set directly in the systemd service file using `Environment=` directives.

**Implementation:**

```bash
# On the server, after deployment
sudo systemctl edit insta-messaging --full

# Add secrets directly:
[Service]
Environment="FACEBOOK_VERIFY_TOKEN=your_token_here"
Environment="FACEBOOK_APP_SECRET=your_secret_here"
Environment="INSTAGRAM_APP_SECRET=your_instagram_secret"
Environment="INSTAGRAM_PAGE_ACCESS_TOKEN=your_page_token"
Environment="DATABASE_URL=sqlite+aiosqlite:////opt/insta-messaging/data/production.db"
Environment="ENVIRONMENT=production"

# Save and restart
sudo systemctl daemon-reload
sudo systemctl restart insta-messaging
```

**Automated via GitHub Actions:**
```yaml
- name: Update systemd service with secrets
  run: |
    # Create systemd override file
    sudo mkdir -p /etc/systemd/system/insta-messaging.service.d/
    sudo cat > /etc/systemd/system/insta-messaging.service.d/secrets.conf <<EOF
    [Service]
    Environment="FACEBOOK_VERIFY_TOKEN=${{ secrets.FACEBOOK_VERIFY_TOKEN }}"
    Environment="FACEBOOK_APP_SECRET=${{ secrets.FACEBOOK_APP_SECRET }}"
    Environment="INSTAGRAM_APP_SECRET=${{ secrets.INSTAGRAM_APP_SECRET }}"
    Environment="INSTAGRAM_PAGE_ACCESS_TOKEN=${{ secrets.INSTAGRAM_PAGE_ACCESS_TOKEN }}"
    EOF

    sudo chmod 600 /etc/systemd/system/insta-messaging.service.d/secrets.conf
    sudo systemctl daemon-reload
    sudo systemctl restart insta-messaging
```

---

### 🥉 Level 3: GitHub Secrets → .env (Current Method)

**Best for:** Simple deployments, development servers

**Advantages:**
- ✅ Simple to implement
- ✅ Easy to debug
- ✅ Works with existing scripts

**Disadvantages:**
- ⚠️ Secrets stored on disk (though with 600 permissions)
- ⚠️ Could be exposed if server is compromised

**Already implemented in your code!** See deployment script above.

---

### 🏆 Level 4: Cloud Secrets Manager (Enterprise)

**Best for:** Large-scale deployments, multiple servers, compliance (SOC2, HIPAA)

**Advantages:**
- ✅ Centralized secret management
- ✅ Automatic rotation
- ✅ Audit logs
- ✅ Access control
- ✅ Secrets never touch disk

**Options:**
- **AWS Secrets Manager** ($0.40/secret/month + API calls)
- **HashiCorp Vault** (open source or cloud)
- **Google Secret Manager** (similar pricing to AWS)
- **Azure Key Vault**

**Example with AWS Secrets Manager:**

```python
# app/core/config.py
import boto3
from botocore.exceptions import ClientError
import json

def get_secret(secret_name: str) -> dict:
    """Fetch secret from AWS Secrets Manager"""
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='us-east-1'
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        raise Exception(f"Error fetching secret: {e}")

# In your settings:
class Settings(BaseSettings):
    # Fetch from Secrets Manager if in production
    if os.getenv("ENVIRONMENT") == "production":
        secrets = get_secret("insta-messaging/production")
        FACEBOOK_APP_SECRET: str = secrets["FACEBOOK_APP_SECRET"]
        INSTAGRAM_APP_SECRET: str = secrets["INSTAGRAM_APP_SECRET"]
    else:
        # Fall back to .env for development
        FACEBOOK_APP_SECRET: str
        INSTAGRAM_APP_SECRET: str

        class Config:
            env_file = ".env"
```

**Cost consideration:** ~$2-5/month for typical usage

---

## Comparison Table

| Method | Security | Cost | Complexity | Recommended For |
|--------|----------|------|------------|-----------------|
| **Systemd EnvironmentFile** | ⭐⭐⭐⭐ | Free | Low | **Your case** ✓ |
| **Systemd Environment=** | ⭐⭐⭐⭐⭐ | Free | Medium | High-security apps |
| **GitHub Secrets → .env** | ⭐⭐⭐ | Free | Very Low | Dev/staging |
| **Secrets Manager** | ⭐⭐⭐⭐⭐ | $$$ | High | Enterprise |

---

## Recommended Setup for Your Project

Based on your DigitalOcean deployment:

### Phase 1: Use Current Method (GitHub Secrets → .env) ✅

**You're already set up correctly!** Your deployment script:
1. Creates `.env` with 600 permissions ✓
2. Owned by `insta-messaging` user ✓
3. Loaded by systemd ✓

**GitHub Secrets to configure:**
```
FACEBOOK_VERIFY_TOKEN
FACEBOOK_APP_SECRET
INSTAGRAM_APP_SECRET
INSTAGRAM_PAGE_ACCESS_TOKEN
INSTAGRAM_BUSINESS_ACCOUNT_ID
CRM_MYSQL_PASSWORD
NGROK_AUTHTOKEN (for testing only)
```

### Phase 2: Upgrade to Systemd Override (Optional)

If you want better security:
1. Keep secrets in GitHub Secrets ✓
2. Use systemd override files instead of `.env`
3. Secrets never written to disk

---

## Best Practices

### ✅ DO:
- Store all secrets in GitHub Secrets
- Use `.env` files with 600 permissions (owner read/write only)
- Add `.env` to `.gitignore` (already done)
- Rotate secrets regularly (every 90 days)
- Use different secrets for dev/staging/production
- Audit secret access logs

### ❌ DON'T:
- Commit secrets to git (obviously)
- Use same secrets across environments
- Give secrets 644 permissions (world-readable)
- Store secrets in application code
- Echo secrets in logs
- Share secrets via Slack/email/unencrypted channels

---

## Quick Start: Securing Your Deployment

### 1. Add Secrets to GitHub

Go to: `https://github.com/november1306/insta-messaging/settings/secrets/actions`

Add these secrets:
```
FACEBOOK_VERIFY_TOKEN=your_value_here
FACEBOOK_APP_SECRET=your_value_here
INSTAGRAM_APP_SECRET=your_value_here
INSTAGRAM_PAGE_ACCESS_TOKEN=your_value_here
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_value_here
```

### 2. Deploy

Your existing `deploy-production.sh` script already handles this securely!

### 3. Verify Permissions

SSH to your server:
```bash
ls -la /opt/insta-messaging/.env
# Should show: -rw------- 1 insta-messaging insta-messaging

# Only the app user should be able to read it
sudo -u insta-messaging cat /opt/insta-messaging/.env  # Works
cat /opt/insta-messaging/.env  # Permission denied (if you're not root)
```

### 4. Test

```bash
systemctl status insta-messaging
curl http://localhost:8000/health
```

---

## Troubleshooting

### "Permission denied" reading .env
```bash
sudo chmod 600 /opt/insta-messaging/.env
sudo chown insta-messaging:insta-messaging /opt/insta-messaging/.env
```

### Secrets not loading
```bash
# Check systemd service
systemctl status insta-messaging

# Check environment variables
systemctl show insta-messaging | grep Environment

# Check if .env exists
ls -la /opt/insta-messaging/.env
```

### Updating secrets
```bash
# Method 1: Edit .env directly
sudo nano /opt/insta-messaging/.env
sudo systemctl restart insta-messaging

# Method 2: Re-run deployment (will recreate .env if missing)
cd /opt/insta-messaging && git pull && sudo bash deploy-production.sh
```

---

## Conclusion

**Your current setup (GitHub Secrets → .env with 600 permissions) is secure and appropriate for your use case.**

No changes needed unless you want to upgrade to Level 2 (systemd environment variables) for even better security.
