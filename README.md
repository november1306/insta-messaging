# Instagram Messenger Automation

Automated Instagram DM system with CRM integration API for e-commerce businesses.

## What It Does

- **Receives Instagram messages** via webhooks from Instagram/Facebook
- **Sends messages** to Instagram users via REST API
- **Stores conversation history** in database
- **Provides CRM integration** through REST API endpoints
- **Supports auto-replies** based on configurable rules

## Features

### ✅ Available Now

- **Webhook Integration** - Receive Instagram DMs in real-time
- **Message Sending API** - Send messages to Instagram users programmatically
- **Message Status Tracking** - Check delivery status of sent messages
- **Account Management** - Configure multiple Instagram business accounts
- **Conversation Storage** - Full message history in database
- **Auto-Reply Rules** - Automatic responses based on message content
- **Idempotency Protection** - Prevent duplicate message sends
- **Health Monitoring** - Health check endpoint for uptime monitoring

### 🔜 Coming Next

- Async message queue with retries
- Webhook delivery to external CRM systems
- Advanced delivery tracking (delivered, read timestamps)
- Bulk messaging capabilities

---

## Installation

### Prerequisites

- Python 3.12+ or Miniconda/Anaconda
- Instagram Business Account
- Facebook App with Instagram permissions
- ngrok (for local webhook testing)

### Quick Setup

1. **Clone and install dependencies:**
   ```bash
   # Using conda (recommended)
   conda env create -f environment.yml
   conda activate insta-auto

   # Or using pip
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   # Copy example config
   cp .env.example .env

   # Edit .env with your credentials (see Configuration section)
   ```

3. **Initialize database:**
   ```bash
   alembic upgrade head
   ```

4. **Start server:**
   ```bash
   uvicorn app.main:app --reload
   ```

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

### For API Testing (localhost)

```bash
# Start server
uvicorn app.main:app --reload

# Server available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### For Webhook Testing (ngrok)

```bash
# Terminal 1: Start server
uvicorn app.main:app --reload

# Terminal 2: Start ngrok
ngrok http 8000

# Copy ngrok URL (e.g., https://abc123.ngrok-free.dev)
# Configure in Facebook Developer Console:
# Webhook URL: https://your-ngrok-url.ngrok-free.dev/webhooks/instagram
# Verify Token: (your FACEBOOK_VERIFY_TOKEN)
```

**When to use what:**
- **localhost:8000** - Testing API endpoints (faster, direct)
- **ngrok URL** - Testing Instagram webhooks (publicly accessible)

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

All API endpoints require Bearer token authentication:

```bash
Authorization: Bearer your_api_key_here
```

**Development mode:** Any Bearer token is accepted (stub authentication)  
**Production mode:** Real API key validation required

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

**Create account configuration:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{
    "instagram_account_id": "17841405728832526",
    "username": "myshop",
    "access_token": "IGAA...",
    "crm_webhook_url": "https://crm.myshop.com/webhooks",
    "webhook_secret": "shared_secret"
  }'
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
- **Database:** SQLite (development), MySQL (production target)
- **ORM:** SQLAlchemy 2.0 with async support
- **Migrations:** Alembic
- **Security:** Cryptography for credential encryption
- **Testing:** pytest with async support

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
