# Instagram Messenger Automation

**Automated Instagram DM router for e-commerce businesses** - Receive Instagram messages via webhooks, send messages via API, and integrate with your CRM system.

## What It Does

This application acts as a **message router** between Instagram and your business systems:

- **Receives** Instagram DMs via webhooks from Meta/Instagram
- **Forwards** messages to your CRM system with signature verification
- **Sends** messages to Instagram users via REST API
- **Stores** full conversation history in database
- **Provides** real-time chat UI for monitoring and testing

Perfect for e-commerce businesses that need to automate Instagram customer conversations and integrate with existing CRM platforms.

---

## Key Features

✅ **Webhook Integration** - Real-time Instagram message reception
✅ **CRM Forwarding** - Forward messages to your CRM with HMAC signatures
✅ **REST API** - Send messages programmatically with async background processing
✅ **Multi-Account** - Support multiple Instagram business accounts
✅ **Web Chat UI** - Instagram-like interface with live updates (SSE)
✅ **Auto-Replies** - Configure automatic responses based on rules
✅ **Secure** - Encrypted credentials, signature validation, API key auth

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for web UI)
- Instagram Business Account
- Facebook App with Instagram permissions
- ngrok account (for local webhook testing)

### Installation

**Windows:**
```bash
# Run installation script
scripts\win\install.bat

# Configure credentials
notepad .env

# Start all services (backend + frontend + ngrok)
scripts\win\dev-all.bat
```

**Linux/Mac:**
```bash
# Run installation script
scripts/linux/install.sh

# Configure credentials
nano .env

# Start all services
scripts/linux/dev-all.sh
```

**What gets installed:**
- Python virtual environment with dependencies
- Database with migrations applied
- Frontend dependencies (Vue 3 + Vite)
- `.env` file from template

**Services:**
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:5173
- API Docs: http://localhost:8000/docs
- ngrok UI: http://localhost:4040

---

## Configuration

Create `.env` file with your Instagram/Facebook credentials:

```env
# Instagram Credentials
INSTAGRAM_PAGE_ACCESS_TOKEN=IGAA...      # Must start with IGAA (not EAAG)
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_id
INSTAGRAM_APP_SECRET=your_app_secret

# Facebook App
FACEBOOK_VERIFY_TOKEN=your_custom_token   # Create your own string
FACEBOOK_APP_SECRET=your_facebook_secret

# Optional: ngrok for webhook testing
NGROK_AUTHTOKEN=your_ngrok_token
```

**Where to get credentials:**
- **Access Token** - Facebook Developer Console → Instagram → Token Generator
- **Business Account ID** - Found in Instagram API responses or webhook payloads
- **App Secrets** - Facebook Developer Console → App Settings → Basic
- **Verify Token** - Create your own custom string (e.g., `my_webhook_token_123`)

---

## Usage

### 1. Generate API Key

```bash
python -m app.cli.generate_api_key --name "My Key" --type admin --env test
```

Save the generated key - you'll need it for API requests.

### 2. Configure Account

Tell the router about your Instagram account and CRM webhook URL:

```bash
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_account_id": "17841405728832526",
    "username": "myshop",
    "access_token": "IGAA...",
    "crm_webhook_url": "https://your-crm.com/webhooks/instagram",
    "webhook_secret": "shared_secret_123"
  }'
```

### 3. Set Up Instagram Webhook

Configure Facebook App webhook to point to your server:

**Development (ngrok):**
- URL: `https://YOUR-NGROK-URL.ngrok.io/webhooks/instagram`
- Verify Token: (same as `FACEBOOK_VERIFY_TOKEN` in `.env`)
- Fields: `messages`

**Production:**
- URL: `https://your-domain.com/webhooks/instagram`

### 4. Send Messages via API

```bash
curl -X POST "http://localhost:8000/api/v1/messages/send" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "account_id=17841405728832526" \
  -F "recipient_id=1558635688632972" \
  -F "message=Hello! Your order is ready."

# Response (immediate): {"message_id": "msg_abc123", "status": "pending", ...}

# Check status
curl -X GET "http://localhost:8000/api/v1/messages/msg_abc123/status" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Response: {"message_id": "msg_abc123", "status": "sent", ...}
```

**Async Processing:** Messages are sent in background. API returns immediately with `status="pending"`. Use the status endpoint or SSE to track delivery.

### 5. Monitor Conversations

**Web UI:** http://localhost:5173 (dev) or http://localhost:8000/chat (production)

Real-time Instagram-like interface shows all conversations with live updates.

---

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/messages/send` | POST | Send message to Instagram user |
| `/api/v1/messages/{id}/status` | GET | Check message delivery status |
| `/api/v1/accounts` | POST | Configure Instagram account |
| `/webhooks/instagram` | POST | Receive Instagram webhooks (Meta calls this) |
| `/health` | GET | Health check |

**Full API Documentation:** http://localhost:8000/docs (Swagger UI)

---

## CRM Webhook Integration

When Instagram messages arrive, the router forwards them to your CRM:

**Payload sent to your CRM:**
```json
{
  "event": "message.received",
  "message_id": "mid.abc123",
  "sender_id": "1234567890",
  "message": "Customer message text",
  "timestamp": "2025-11-08T10:30:00+00:00"
}
```

**Security Header:**
```
X-Hub-Signature-256: sha256=<hmac-signature>
```

Validate the signature using HMAC-SHA256 with your `webhook_secret` to ensure messages are authentic.

---

## Development Scripts

**Windows:**
- `scripts\win\dev-all.bat` - Start everything (backend + frontend + ngrok)
- `scripts\win\dev-backend.bat` - Backend only (fastest for API testing)
- `scripts\win\dev-frontend.bat` - Frontend only
- `scripts\win\stop-all.bat` - Stop all services
- `scripts\win\build.bat` - Build production frontend

**Linux/Mac:**
- `scripts/linux/dev-all.sh` - Start everything
- `scripts/linux/dev-backend.sh` - Backend only
- `scripts/linux/dev-frontend.sh` - Frontend only
- `scripts/linux/build.sh` - Build production

---

## Production Deployment

### Option A: Automatic (GitHub Actions)

Push to `main` branch triggers automatic deployment to VPS:

```bash
git push origin main
```

The workflow automatically:
- SSHs to VPS
- Pulls latest code
- Runs migrations
- Builds frontend
- Restarts services

### Option B: Manual VPS Deployment

```bash
# SSH to VPS
ssh -i ~/.ssh/id_ed25519 root@your-vps-ip

# Navigate to app directory
cd /opt/insta-messaging

# First-time setup only
bash scripts/linux/provision-vps.sh

# Pull updates
git pull

# Restart services
systemctl restart insta-messaging nginx
```

**Check logs:**
```bash
journalctl -u insta-messaging -n 100 --no-pager
```

---

## Troubleshooting

**Webhooks not arriving:**
- Check ngrok is running and URL matches Facebook webhook config
- Verify `INSTAGRAM_APP_SECRET` matches your app settings
- Look for "Invalid signature" errors in logs

**Messages not sending:**
- Ensure token starts with `IGAA` (not `EAAG` - wrong token type)
- Recipient must have messaged you first (Instagram 24-hour policy)
- Check token hasn't expired in Facebook Developer Console

**Database errors:**
- Run migrations: `.\venv\Scripts\python.exe -m alembic upgrade head`

---

## Documentation

- **[CLAUDE.md](.claude/CLAUDE.md)** - Complete development guide for Claude Code
- **[AUTHENTICATION.md](AUTHENTICATION.md)** - Authentication and API key management
- **[ACCOUNT_ID_GUIDE.md](.claude/ACCOUNT_ID_GUIDE.md)** - Understanding Instagram ID types
- **[API Docs](http://localhost:8000/docs)** - Interactive Swagger documentation

---

## Tech Stack

- **Backend:** Python 3.12 + FastAPI (async)
- **Frontend:** Vue 3 + Vite + Tailwind CSS
- **Database:** SQLite (local) / PostgreSQL (production ready)
- **ORM:** SQLAlchemy 2.0 (async)
- **Real-time:** Server-Sent Events (SSE)

---

## License

See [LICENSE](LICENSE) file for details.
