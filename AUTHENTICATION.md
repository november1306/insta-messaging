# Authentication Guide

This document explains how to use the authentication system in the Instagram Messenger Automation project.

## Overview

The project uses **API Key Authentication** for all endpoints (both CRM API and UI).

- Single authentication method for consistency
- Bcrypt-hashed API keys stored in database
- Two permission levels: admin and account-scoped
- Generate keys via CLI tool

---

## API Key Authentication

API keys are used for all CRM integration endpoints (`/api/v1/*`). Keys are stored securely with bcrypt hashing and support two permission levels.

### API Key Types

#### Admin Keys
- Full access to all accounts and operations
- Can create new accounts
- Can send messages for any account
- Recommended for development and administrative tasks

#### Account-Scoped Keys
- Limited to specific Instagram accounts
- Cannot create new accounts
- Can only send/view messages for permitted accounts
- Recommended for production integrations

### Generating API Keys

Use the CLI tool to generate API keys:

```bash
# Generate admin key for testing
python -m app.cli.generate_api_key \
  --name "Development Admin" \
  --type admin \
  --env test

# Generate production admin key
python -m app.cli.generate_api_key \
  --name "Production Admin" \
  --type admin \
  --env live

# Generate account-scoped key
python -m app.cli.generate_api_key \
  --name "Customer A Integration" \
  --type account \
  --env live \
  --accounts acc_abc123,acc_def456

# Generate key with expiration
python -m app.cli.generate_api_key \
  --name "Temporary Key" \
  --type admin \
  --env test \
  --expires 90  # Expires in 90 days
```

**Output example:**
```
======================================================================
✅ API Key created successfully!
======================================================================

API Key: <your-test-api-key-here>

⚠️  SAVE THIS KEY - It will not be shown again!

Key Details:
  • ID: key_a1b2c3d4e5f6
  • Name: Development Admin
  • Type: admin
  • Environment: test
  • Created: 2025-11-17 20:55:00 UTC

Usage Example:
  curl -H 'Authorization: Bearer <your-test-api-key-here>' \
       http://localhost:8000/api/v1/messages/send

======================================================================
```

### Using API Keys

Include the API key in the `Authorization` header of all CRM API requests:

```bash
curl -X POST "http://localhost:8000/api/v1/messages/send" \
  -H "Authorization: Bearer <your-test-api-key-here>" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acc_123",
    "recipient_id": "1234567890",
    "message": "Hello from CRM!",
    "idempotency_key": "order_123_msg_1"
  }'
```

### API Key Format

```
sk_{environment}_{random_32_chars}
```

- `sk_` - Secret key prefix
- `test_` or `live_` - Environment indicator
- 32 random alphanumeric characters

**Examples:**
- `<your-test-api-key-here>` (test key)
- `<your-live-api-key-here>` (live key)

### Security Features

- ✅ **Bcrypt hashing** - Keys are hashed, never stored in plain text
- ✅ **Prefix lookup** - Fast database queries without exposing full keys
- ✅ **Revocable** - Keys can be deactivated without deleting data
- ✅ **Expirable** - Optional expiration dates
- ✅ **Permission scoping** - Account-level access control
- ✅ **Usage tracking** - Last used timestamp for audit logs

### Managing API Keys

#### Revoking a Key

```python
from app.services.api_key_service import APIKeyService
from app.db.connection import get_db_session

async with get_db_session() as db:
    await APIKeyService.revoke_api_key(db, "key_a1b2c3d4e5f6")
```

#### Checking Permissions

```python
from app.services.api_key_service import APIKeyService

# Check if key has access to an account
has_permission = await APIKeyService.check_account_permission(
    db, api_key, "acc_123"
)

# Get all permitted accounts
account_ids = await APIKeyService.get_permitted_account_ids(db, api_key)
```

### Error Responses

#### 401 Unauthorized
- Missing `Authorization` header
- Invalid API key format
- Invalid or expired key

```json
{
  "detail": "Invalid API key. Check your credentials."
}
```

#### 403 Forbidden
- Valid key but insufficient permissions
- Account-scoped key accessing unauthorized account

```json
{
  "detail": "API key does not have permission to access account acc_123"
}
```

---

## UI Endpoints

The web chat UI endpoints (`/ui/conversations`, `/ui/messages/*`) use the **same API key authentication** as the CRM API.

### Accessing UI Endpoints

```bash
# Generate an API key for UI access
python -m app.cli.generate_api_key \
  --name "UI Access" \
  --type admin \
  --env test

# Use the API key with UI endpoints
curl "http://localhost:8000/ui/conversations" \
  -H "Authorization: Bearer <your-api-key>"
```

### Frontend Integration

If you're building a frontend application:

1. **Generate an API key** for the frontend to use
2. **Store securely** (never expose in client-side code)
3. **Use from backend** - make API calls from your backend server

---

## Production Checklist

Before deploying to production:

- [ ] Generate production API keys with `--env live`
- [ ] Review and restrict account permissions
- [ ] Set API key expiration dates where appropriate
- [ ] Enable HTTPS for all API requests
- [ ] Implement rate limiting (recommended)
- [ ] Monitor API key usage via `last_used_at` field
- [ ] Run database migrations (`alembic upgrade head`)

---

## Troubleshooting

### "Invalid API key" error

1. Check the API key format (should start with `sk_test_` or `sk_live_`)
2. Verify the key wasn't revoked
3. Check if the key has expired
4. Ensure you're using the correct environment (test vs live)

### "Permission denied" error

1. Verify your API key type (admin vs account-scoped)
2. Check which accounts your key has access to
3. Create a new admin key if needed

---

## API Reference

See the interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

All endpoints (CRM API and UI) require API key authentication.
