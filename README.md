# Instagram Messenger Automation

Automated Instagram DM system with CRM integration API for e-commerce businesses.

## What It Does

- **Receives Instagram messages** via webhooks from Instagram/Facebook
- **Sends messages** to Instagram users via REST API
- **Stores conversation history** in database
- **Provides CRM integration** through REST API endpoints
- **Supports auto-replies** based on configurable rules
- **Web UI for live testing** - Instagram-like chat interface with real-time updates

## Features

### ✅ Available Now

- **Webhook Integration** - Receive Instagram DMs in real-time
- **CRM Webhook Forwarding** - Forward Instagram messages to your CRM system
- **Message Sending API** - Send messages to Instagram users programmatically
- **Message Status Tracking** - Check delivery status of sent messages
- **Account Management** - Configure multiple Instagram business accounts
- **Conversation Storage** - Full message history in database
- **Auto-Reply Rules** - Automatic responses based on message content
- **Idempotency Protection** - Prevent duplicate message sends
- **Health Monitoring** - Health check endpoint for uptime monitoring
- **Web Chat UI** - Instagram-like interface with real-time updates via SSE

### 🔜 Coming Next

- Async message queue with retries
- Webhook retry logic and dead letter queue
- Delivery status webhooks (delivered, read timestamps)
- Bulk messaging capabilities

---

## Installation

### Prerequisites

- Python 3.12+ (required for full async support)
- Node.js 18+ and npm
- Instagram Business Account
- Facebook App with Instagram permissions
- ngrok (for Instagram webhook testing - **mandatory until you have a real domain**)
  - Download from: https://ngrok.com/download
  - Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken
  - Add `NGROK_AUTHTOKEN=your_token_here` to your `.env` file
  - The install script will automatically configure ngrok with your token

### Quick Setup

**Windows:**
```bash
# Run the installation script (idempotent, safe to run multiple times)
scripts\win\install.bat

# Edit .env with your credentials
notepad .env

# Start all services (backend + frontend + ngrok)
scripts\win\dev-all.bat
```

**Linux/Mac:**
```bash
# Run the installation script (idempotent, safe to run multiple times)
scripts/linux/install.sh

# Edit .env with your credentials
nano .env

# Start all services (backend + frontend + ngrok)
scripts/linux/dev-all.sh
```

The installation script will:
- Create Python virtual environment (`venv/`)
- Install Python dependencies from `requirements.txt`
- Create `.env` from `.env.example`
- Run database migrations
- Install frontend dependencies

Server runs at `http://localhost:8000`

---

## Configuration

Create a `.env` file with the following:

```env
# Instagram/Facebook Credentials
FACEBOOK_VERIFY_TOKEN=your_custom_verify_token
FACEBOOK_APP_SECRET=your_facebook_app_secret
INSTAGRAM_APP_SECRET=your_instagram_app_secret
INSTAGRAM_PAGE_ACCESS_TOKEN=your_instagram_access_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_business_account_id

# Server
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Where to Get Credentials

**FACEBOOK_VERIFY_TOKEN**
- Create your own custom string (e.g., `my_webhook_token_123`)
- Used for webhook verification

**FACEBOOK_APP_SECRET**
- Facebook Developer Console → Your App → Settings → Basic → App Secret

**INSTAGRAM_APP_SECRET**
- Instagram app settings (different from Facebook app secret)
- Used for webhook signature validation

**INSTAGRAM_PAGE_ACCESS_TOKEN**
- Facebook Developer Console → Your App → Instagram → User Token Generator
- Must start with `IGAA` (Instagram token, not Facebook token)

**INSTAGRAM_BUSINESS_ACCOUNT_ID**
- Your Instagram Business Account ID
- Found in webhook payloads or Instagram API responses

---

## Running Locally

### Available Scripts

**Windows:**
- `scripts\win\install.bat` - First-time setup
- `scripts\win\dev-all.bat` - Start all services (backend + frontend + ngrok)
- `scripts\win\dev-backend.bat` - Start backend only
- `scripts\win\dev-frontend.bat` - Start frontend only
- `scripts\win\build.bat` - Build production frontend
- `scripts\win\start.bat` - Start production server
- `scripts\win\stop-all.bat` - Stop all running services (ngrok, backend, frontend)

**Linux/Mac:**
- `scripts/linux/install.sh` - First-time setup
- `scripts/linux/dev-all.sh` - Start all services (backend + frontend + ngrok)
- `scripts/linux/dev-backend.sh` - Start backend only
- `scripts/linux/dev-frontend.sh` - Start frontend only
- `scripts/linux/build.sh` - Build production frontend
- `scripts/linux/start.sh` - Start production server
- `scripts/linux/start-daemon.sh` - Start as background daemon
- `scripts/linux/stop-daemon.sh` - Stop daemon
- `scripts/linux/status-daemon.sh` - Check daemon status

### For API Testing (localhost)

```bash
# Windows
scripts\win\dev-backend.bat

# Linux/Mac
scripts/linux/dev-backend.sh

# Server available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### For Full Development (with UI and ngrok)

```bash
# Windows
scripts\win\dev-all.bat

# Linux/Mac
scripts/linux/dev-all.sh

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
# ngrok UI: http://localhost:4040
```

**To stop all services:**
```bash
# Windows
scripts\win\stop-all.bat

# Linux/Mac
# Press Ctrl+C in the terminal running dev-all.sh
```

**When to use what:**
- **dev-backend** - API testing only (faster startup)
- **dev-frontend** - UI development only
- **dev-all** - Full development with Instagram webhook testing (requires ngrok)
- **stop-all** (Windows) - Clean shutdown of all services

---

## Web UI (Chat Interface)

The project includes an Instagram-like chat interface for live testing and demonstration.

### Quick Start

**Development mode** (with hot reload):
```bash
# Windows
scripts\win\dev-all.bat

# Linux/Mac
scripts/linux/dev-all.sh
```
- Frontend (dev): http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- ngrok UI: http://localhost:4040

**Production mode** (single server):
```bash
# Windows
scripts\win\build.bat    # Build frontend
scripts\win\start.bat    # Start server

# Linux/Mac
scripts/linux/build.sh   # Build frontend
scripts/linux/start.sh   # Start server
```
- Chat UI: http://localhost:8000/chat
- API: http://localhost:8000/api/v1

### Features

- ✅ Real-time message updates (Server-Sent Events)
- ✅ Instagram-style 3-column layout
- ✅ Conversation list with unread counts
- ✅ Message sending and receiving
- ✅ Delivery status indicators (✓✓)
- ✅ Auto-scroll and message animations
- ✅ Responsive design

### Tech Stack

- **Frontend**: Vue 3 + Vite + Tailwind CSS
- **Real-time**: Server-Sent Events (SSE)
- **Backend**: FastAPI (existing)

📖 **See [UI_SETUP.md](UI_SETUP.md) for detailed setup instructions and API documentation.**

---

## Deployment

### Railway (Recommended)

1. **Connect repository** to Railway
2. **Set environment variables** in Railway dashboard
3. **Deploy** - Railway auto-detects Python and runs the app
4. **Configure webhook** in Facebook with your Railway URL

### Custom Server

1. **Install dependencies** on server
2. **Set environment variables**
3. **Run with production server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. **Configure webhook** with your server's public URL
5. **Use process manager** (systemd, supervisor) for auto-restart

---

## API Usage

### Authentication

All endpoints use **API Key Authentication** (both CRM API and UI).

#### Quick Start

**Generate an API key:**
```bash
python -m app.cli.generate_api_key --name "My Key" --type admin --env test
```

**Use the API key:**
```bash
# For CRM endpoints
curl -H "Authorization: Bearer <your-api-key-here>" \
     http://localhost:8000/api/v1/messages/send

# For UI endpoints
curl -H "Authorization: Bearer <your-api-key-here>" \
     http://localhost:8000/ui/conversations
```

**Development mode:** Set `USE_STUB_AUTH=true` to accept any Bearer token
**Production mode:** Generate proper API keys (required)

📖 **See [AUTHENTICATION.md](AUTHENTICATION.md) for complete authentication documentation.**

### API Documentation

Interactive API docs available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI Spec:** `http://localhost:8000/openapi.json`

### Quick Examples

**Send a message:**
```bash
curl -X POST "http://localhost:8000/api/v1/messages/send" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{
    "account_id": "17841405728832526",
    "recipient_id": "1558635688632972",
    "message": "Hello from our system!",
    "idempotency_key": "order_123_confirmation"
  }'
```

**Check message status:**
```bash
curl -X GET "http://localhost:8000/api/v1/messages/msg_abc123/status" \
  -H "Authorization: Bearer test_api_key"
```

**Health check:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Create account configuration (enables CRM webhook forwarding):**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{
    "instagram_account_id": "17841405728832526",
    "username": "myshop",
    "access_token": "IGAA...",
    "crm_webhook_url": "https://crm.myshop.com/webhooks/instagram",
    "webhook_secret": "shared_secret_xyz"
  }'
```

**Response:**
```json
{
  "account_id": "acc_abc123def456",
  "instagram_account_id": "17841405728832526",
  "username": "myshop",
  "crm_webhook_url": "https://crm.myshop.com/webhooks/instagram",
  "created_at": "2025-11-08T10:30:00Z"
}
```

---

## API Endpoints

### Messages

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/v1/messages/send` | POST | Send message to Instagram user | ✅ Implemented |
| `/api/v1/messages/{id}/status` | GET | Get message delivery status | ✅ Implemented |

### Accounts

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/v1/accounts` | POST | Create account configuration | ✅ Implemented |
| `/api/v1/accounts/{id}` | GET | Get account details | 🚧 Documented |
| `/api/v1/accounts/{id}` | PUT | Update account configuration | 🚧 Documented |

### System

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/health` | GET | Health check | ✅ Implemented |
| `/webhooks/instagram` | POST | Instagram webhook receiver | ✅ Implemented |

---

## CRM Webhook Integration

The router forwards Instagram messages to your CRM via webhooks. Configure your CRM webhook URL when creating an account:

```bash
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer test_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_account_id": "17841405728832526",
    "username": "myshop",
    "access_token": "IGAA...",
    "crm_webhook_url": "https://your-crm.com/webhooks/instagram",
    "webhook_secret": "shared_secret_123"
  }'
```

**Your CRM receives:**
```json
{
  "event": "message.received",
  "message_id": "mid.abc123",
  "sender_id": "1234567890",
  "message": "Customer message text",
  "timestamp": "2025-11-08T10:30:00+00:00"
}
```

**Security:** Validate the `X-Hub-Signature-256` header using HMAC-SHA256 with your webhook secret. See `/docs` for full webhook schema and signature validation examples.

---

## Testing

### Manual Testing

```bash
# Test sending a message
python test_send_message.py "@username" "Test message"

# Test CRM endpoints
python test_crm_endpoints.py http://localhost:8000

# Check database contents
python check_database.py
```

### Automated Tests

```bash
# Run test suite
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_webhooks.py
```

---

## Troubleshooting

### Webhooks Not Arriving

1. Check ngrok is running and URL hasn't changed
2. Verify webhook URL in Facebook Developer Console
3. Check `INSTAGRAM_APP_SECRET` matches Instagram app settings
4. Look for "Invalid signature" errors in logs

### Messages Not Sending

1. Verify `INSTAGRAM_PAGE_ACCESS_TOKEN` starts with `IGAA`
2. Check token hasn't expired
3. Ensure recipient has messaged you within 24 hours (Instagram policy)
4. Check logs for Instagram API errors

### "Invalid OAuth access token"

- Using Facebook token instead of Instagram token
- Token format should start with `IGAA`, not `EAAG`

---

## Tech Stack

- **Backend:** Python 3.12+ with FastAPI (async)
- **Frontend:** Vue 3 + Vite + Tailwind CSS
- **Database:** SQLite (development), MySQL (production target)
- **ORM:** SQLAlchemy 2.0 with async support
- **Migrations:** Alembic
- **Security:** Cryptography for credential encryption
- **Testing:** pytest with async support
- **Environment:** Python venv (standard virtual environment)

---

## Documentation

- **[SETUP.md](SETUP.md)** - Detailed setup instructions
- **[LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md)** - localhost vs ngrok guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[API Docs](http://localhost:8000/docs)** - Interactive API documentation

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review API documentation at `/docs`
3. Check server logs for error messages
4. Verify all environment variables are set correctly

---

## License

See [LICENSE](LICENSE) file for details.
