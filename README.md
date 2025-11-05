# Instagram Messenger Automation

Automated Instagram DM response system for e-commerce businesses.

## Overview

This system receives customer messages via Instagram Direct Messages through Facebook's webhook callbacks and automatically responds based on predefined rules.

## Tech Stack

- **Backend**: Python with FastAPI (async support)
- **Database**: MySQL (multi-account storage)
- **ORM**: SQLAlchemy with Alembic migrations
- **Security**: Cryptography for credential encryption
- **Deployment**: Railway or custom Linux server
- **Local Development**: Windows with ngrok for webhook tunneling

## Quick Start

### Prerequisites

- **Miniconda or Anaconda** (recommended) or Python 3.12+
- **Facebook App** with Instagram permissions configured
- **ngrok** for local webhook testing

### Automated Setup (Windows)

```bash
# Run the setup script
setup.bat
```

This will:
1. Create conda environment with all dependencies
2. Copy .env.example to .env
3. Run database migrations

### Manual Setup

1. **Create conda environment:**
   ```bash
   # Create environment from environment.yml
   conda env create -f environment.yml
   
   # Activate environment
   conda activate insta-auto
   ```

2. **Configure environment variables:**
   ```bash
   # Copy the example file
   copy .env.example .env  # Windows
   
   # Edit .env with your credentials
   ```

3. **Initialize database:**
   ```bash
   # Run migrations to create SQLite database
   alembic upgrade head
   ```

4. **Start the server:**
   ```bash
   # Start FastAPI server (runs on http://localhost:8000)
   uvicorn app.main:app --reload
   ```

For detailed setup instructions, see [SETUP.md](SETUP.md)

4. **Set up ngrok tunnel (in separate terminal):**
   ```bash
   # Create public HTTPS tunnel to your local server
   ngrok http 8000
   
   # Copy the HTTPS URL (e.g., https://abc123.ngrok-free.dev)
   ```

5. **Configure Facebook webhook:**
   - Go to https://developers.facebook.com/apps/YOUR_APP_ID/webhooks
   - **Webhook URL**: `https://your-ngrok-url.ngrok-free.dev/webhooks/instagram`
   - **Verify Token**: Same value as `FACEBOOK_VERIFY_TOKEN` in your `.env`
   - **Subscribe to**: `messages` events

6. **Test the webhook:**
   - Use Facebook's "Send to My Server" button to test
   - Check server logs for incoming messages
   - Server responds at: http://localhost:8000

## Token Setup (Critical)

This system requires 3 specific tokens from Facebook/Instagram. **Getting the right tokens is crucial** - wrong tokens will cause authentication failures.

### 1. FACEBOOK_VERIFY_TOKEN
**What it is**: A custom string you create for webhook verification
**Where to get**: You make this up yourself
**Example**: `"my_webhook_token_123"`
**Usage**: Facebook sends this back to verify your webhook endpoint

```env
FACEBOOK_VERIFY_TOKEN="my_webhook_token_123"
```

### 2. FACEBOOK_APP_SECRET  
**What it is**: Your Facebook app's secret key for webhook signature validation
**Where to get**: 
1. Go to https://developers.facebook.com/apps/YOUR_APP_ID/settings/basic/
2. Find "App Secret" section
3. Click "Show" and copy the value
**Format**: 32-character hex string
**Example**: `"6fc9d415657d17e47cda9c61d44a511b"`

```env
FACEBOOK_APP_SECRET="your_32_character_app_secret"
```

### 3. INSTAGRAM_PAGE_ACCESS_TOKEN ⚠️ **Most Important**
**What it is**: Token for sending Instagram messages via Instagram Graph API
**Critical**: Must be an **Instagram Access Token** (starts with `IGAA`), NOT a Facebook Page token

#### How to get the correct token:
1. **Go to**: https://developers.facebook.com/apps/YOUR_APP_ID/instagram-basic-display/
2. **Find**: "User Token Generator" section  
3. **Select**: Your Instagram business account (@ser_bain)
4. **Generate Token**: Click "Generate Token"
5. **Copy**: The token (starts with `IGAA`, ~180 characters)

#### ❌ **Wrong Token Types** (Don't use these):
- Facebook Page Access Tokens (start with `EAAG`) - Won't work for Instagram
- User Access Tokens for personal Facebook accounts - Wrong scope
- Instagram Basic Display tokens without messaging permissions

#### ✅ **Correct Token Format**:
```env
INSTAGRAM_PAGE_ACCESS_TOKEN="IGAALkT2BsMhxBZAFR0eUhBVXlRYVBjTVllb3ZAWQUtTQTYwcDNET1VxWXZAKaTRXYUVuNy1KeW9mTm5RYXdVOVhwTjl2NTZAJUXhSa2lobm8zMTJfZAlF2bDdPZAUg5UU9zVXE0bmFUTDUzQVoyYzdzMllIY2d1T2VycDB1Nlp3dnNzcwZDZD"
```

### Complete .env File Example (New Architecture):

```env
# Database Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=instagram_automation
MYSQL_USERNAME=app_user
MYSQL_PASSWORD=secure_password

# Application Security
APP_SECRET_KEY=your-secret-key-for-encryption-change-this-in-production

# Server Configuration
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development

# Note: Instagram account credentials are now stored in the database
# Use the account management API to add Instagram business accounts
```

### Old .env File Example (MVP - Being Phased Out):

```env
# Facebook/Instagram Configuration (OLD - will be moved to database)
FACEBOOK_VERIFY_TOKEN="my_webhook_token_123"
FACEBOOK_APP_SECRET="6fc9d415657d17e47cda9c61d44a511b"
INSTAGRAM_PAGE_ACCESS_TOKEN="IGAALkT2BsMhxBZAFR0eUhBVXlRYVBjTVllb3ZAWQUtTQTYwcDNET1VxWXZAKaTRXYUVuNy1KeW9mTm5RYXdVOVhwTjl2NTZAJUXhSa2lobm8zMTJfZAlF2bDdPZAUg5UU9zVXE0bmFUTDUzQVoyYzdzMllIY2d1T2VycDB1Nlp3dnNzcwZDZD"

# Server Configuration
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
```

### Token Troubleshooting:

#### Problem: "Invalid OAuth access token - Cannot parse access token"
**Solution**: You're using a Facebook token instead of Instagram token
- ❌ Wrong: `EAAG...` (Facebook Page token)  
- ✅ Correct: `IGAA...` (Instagram token)

#### Problem: "Object with ID 'me' does not exist"
**Solution**: Use Instagram Graph API, not Facebook Graph API
- ❌ Wrong: `https://graph.facebook.com/v18.0/me/messages`
- ✅ Correct: `https://graph.instagram.com/v21.0/me/messages`

#### Problem: Messages not sending
**Solution**: Ensure your Instagram account is in Live mode
1. Go to your Facebook App dashboard
2. Switch from "Development" to "Live" mode
3. Ensure privacy policy URL is set

### Testing Endpoints

- **Root**: http://localhost:8000/ - Server status
- **Webhook**: http://localhost:8000/webhooks/instagram - Instagram webhook endpoint
- **ngrok Web UI**: http://127.0.0.1:4040 - Monitor tunnel traffic

### Message Testing

Use the test script to send messages programmatically:

```bash
# Send a message to @ser_bain
py test_send_message.py "@ser_bain" "Hello from automation!"

# Send a message to @tol1306  
py test_send_message.py "@tol1306" "Thanks for your message!"
```

**Available users:**
- `@ser_bain`: Business account (ID: 1180376147344794)
- `@tol1306`: Test user account (ID: 1558635688632972)

### Quick Resume Tomorrow

1. **Start servers:**
   ```bash
   # Terminal 1: Start FastAPI server
   py -m uvicorn app.main:app --reload
   
   # Terminal 2: Start ngrok tunnel
   ngrok http 8000
   ```

2. **Test webhook:** Send message from @tol1306 to @ser_bain on Instagram

3. **Test sending:** `py test_send_message.py "@ser_bain" "Test message"`

## Current Status

**Phase 1 Complete**: Minimal Viable Solution - Basic webhook and messaging working ✅  
**Phase 2 In Progress**: Architecture Refactoring for Production Scale 🔄

### ✅ **What's Working (MVP):**
- **Basic webhook server** receiving Instagram messages
- **Message sending** via Instagram Graph API  
- **Single account** (@ser_bain) messaging capability
- **Test script** for manual message sending

### 🔄 **Current Refactoring (Phase 2):**
- **Multi-account architecture** - Support multiple Instagram business accounts
- **Proper interfaces** - Abstract messaging operations with clean interfaces (IMessageReceiver, IMessageSender)
- **MySQL integration** - Replace hardcoded data with database storage
- **Configuration management** - Move hardcoded values to database/config
- **Account-specific routing** - Route messages to correct Instagram accounts

### 🎯 **Target Architecture:**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Webhook API   │────│  Message Router  │────│ Instagram APIs  │
│  (per account)  │    │  (IMessageRcvr)  │    │ (IMessageSndr)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────│ Account Manager │──────────────┘
                        │  (Repository)   │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │ MySQL Database  │
                        │ - Accounts      │
                        │ - Messages      │
                        │ - Conversations │
                        │ - Rules         │
                        └─────────────────┘
```

### 📚 **Architecture Documentation:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - Comprehensive architecture overview
- [Design Document](.kiro/specs/instagram-messenger-automation/design.md) - Detailed component design
- [Implementation Tasks](.kiro/specs/instagram-messenger-automation/tasks.md) - Step-by-step implementation plan

See [tasks.md](.kiro/specs/instagram-messenger-automation/tasks.md) for detailed implementation progress.

## Documentation

- [Requirements](.kiro/specs/instagram-messenger-automation/requirements.md)
- [Design](.kiro/specs/instagram-messenger-automation/design.md)
- [Tasks](.kiro/specs/instagram-messenger-automation/tasks.md)

## License

See [LICENSE](LICENSE) file for details.