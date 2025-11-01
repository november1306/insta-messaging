# Instagram Messenger Automation

Automated Instagram DM response system for e-commerce businesses.

## Overview

This system receives customer messages via Instagram Direct Messages through Facebook's webhook callbacks and automatically responds based on predefined rules.

## Tech Stack

- **Backend**: Python with FastAPI
- **Database**: PostgreSQL
- **Deployment**: Railway or custom Linux server
- **Local Development**: Windows with ngrok for webhook tunneling

## Quick Start

### Prerequisites

- **Python 3.9+** (tested with Python 3.9.13)
- **Facebook App** with Instagram permissions configured
- **ngrok** for local webhook testing (install via `scoop install ngrok`)

### Local Development Setup

1. **Clone and install dependencies:**
   ```bash
   git clone https://github.com/november1306/insta-messaging.git
   cd insta-messaging
   
   # Install dependencies (use 'py' on Windows)
   py -m pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env with your Facebook/Instagram credentials:
   # - FACEBOOK_VERIFY_TOKEN: Any random string (e.g., "my_webhook_token_123")
   # - FACEBOOK_APP_SECRET: From Facebook App Settings > Basic
   # - INSTAGRAM_PAGE_ACCESS_TOKEN: From Facebook App > Instagram > Settings
   ```

3. **Start the server:**
   ```bash
   # Start FastAPI server (runs on http://localhost:8000)
   py -m uvicorn app.main:app --reload
   ```

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

### Environment Variables

```env
# Required for webhook functionality
FACEBOOK_VERIFY_TOKEN=your_custom_verify_token
FACEBOOK_APP_SECRET=your_facebook_app_secret
INSTAGRAM_PAGE_ACCESS_TOKEN=your_instagram_page_token

# Server configuration (optional)
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
```

### Testing Endpoints

- **Root**: http://localhost:8000/ - Server status
- **Webhook**: http://localhost:8000/webhooks/instagram - Instagram webhook endpoint
- **ngrok Web UI**: http://127.0.0.1:4040 - Monitor tunnel traffic

## Development Status

🚧 **In Development** - Currently implementing Phase 1: Minimal Viable Solution

See [tasks.md](.kiro/specs/instagram-messenger-automation/tasks.md) for implementation progress.

## Documentation

- [Requirements](.kiro/specs/instagram-messenger-automation/requirements.md)
- [Design](.kiro/specs/instagram-messenger-automation/design.md)
- [Tasks](.kiro/specs/instagram-messenger-automation/tasks.md)

## License

See [LICENSE](LICENSE) file for details.