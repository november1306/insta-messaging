# Setup Notes - Instagram Messenger Automation

## Current Configuration (Working)

### App Status
- ✅ **Facebook App**: Live mode activated
- ✅ **Instagram Account**: @ser_bain (Business account)
- ✅ **Test User**: @tol1306 
- ✅ **Privacy Policy**: https://november1306.github.io/insta-messaging/privacy-policy.html

### Tokens & IDs (Working Configuration)

#### INSTAGRAM_PAGE_ACCESS_TOKEN
- **Format**: `IGAA...` (182 characters)
- **Source**: Facebook App > Instagram Basic Display > User Token Generator
- **Critical**: Must be Instagram token, NOT Facebook Page token
- **Status**: ✅ Working with Instagram Graph API

#### FACEBOOK_APP_SECRET  
- **Value**: `6fc9d415657d17e47cda9c61d44a511b`
- **Source**: Facebook App > Settings > Basic > App Secret
- **Usage**: Webhook signature validation (future implementation)

#### FACEBOOK_VERIFY_TOKEN
- **Value**: `fb_token` 
- **Source**: Custom string you create
- **Usage**: Webhook verification during setup

### User IDs (for messaging)
- **@ser_bain**: `1180376147344794` (Business account)
- **@tol1306**: `1558635688632972` (Test user)

## API Endpoints (Working)

### Instagram Graph API
- **Base URL**: `https://graph.instagram.com/v21.0/`
- **Send Messages**: `POST /me/messages`
- **Authorization**: `Bearer {token}` (Header, not query param)

### Webhook
- **Local**: `http://localhost:8000/webhooks/instagram`
- **Public**: `https://your-ngrok-url.ngrok-free.dev/webhooks/instagram`

## What's Working ✅

1. **Webhook Reception**: 
   - Receiving real Instagram messages
   - Getting full message content (Live mode)
   - Proper webhook verification

2. **Message Sending**:
   - Instagram Graph API working
   - Can send to any user who messaged first
   - Self-messaging (@ser_bain to @ser_bain) works

3. **Test Script**:
   - `py test_send_message.py "@ser_bain" "message"`
   - Parameterized with user mappings

## Next Session TODO

1. **Implement Auto-Reply**:
   - Update webhook handler to automatically send replies
   - Add keyword-based response logic
   - Test full automation loop

2. **Deploy to Production**:
   - Set up Railway deployment
   - Configure environment variables
   - Test with real customers

3. **Enhanced Features**:
   - Database integration for message history
   - Multiple response templates
   - Business hours logic

## Quick Start Commands

```bash
# Start development environment
py -m uvicorn app.main:app --reload    # Terminal 1
ngrok http 8000                        # Terminal 2

# Test message sending
py test_send_message.py "@ser_bain" "Hello!"

# Check webhook logs
# Watch Terminal 1 for incoming messages
```

## Important Files

- `.env` - Contains working tokens (don't commit)
- `test_send_message.py` - Parameterized message sender
- `app/api/webhooks.py` - Webhook handler (needs auto-reply)
- `README.md` - Updated with current status
- `docs/privacy-policy.html` - Live privacy policy

## Troubleshooting

### Token Issues
- **Wrong API**: Use `graph.instagram.com` NOT `graph.facebook.com`
- **Wrong token type**: Use Instagram token (`IGAA...`) NOT Facebook Page token (`EAAG...`)
- **Authorization**: Use `Bearer` header, not query parameter
- **Token expiry**: Instagram tokens expire, regenerate from Facebook App dashboard

### Common Errors
- `"Invalid OAuth access token"` = Wrong token type (using Facebook instead of Instagram)
- `"Object with ID 'me' does not exist"` = Wrong API endpoint (using Facebook API)
- `"Cannot parse access token"` = Token format issue or expired token

### API Differences
| Facebook Graph API | Instagram Graph API |
|-------------------|-------------------|
| `graph.facebook.com` | `graph.instagram.com` |
| Page Access Token (`EAAG...`) | Instagram Token (`IGAA...`) |
| Query param auth | Bearer header auth |
| For Facebook Pages | For Instagram Business |

### Other Issues
- **User IDs**: Use recipient IDs from webhook logs or USER_IDS mapping
- **Webhook**: Must be HTTPS (use ngrok for local testing)
- **Live Mode**: App must be in Live mode to receive real messages