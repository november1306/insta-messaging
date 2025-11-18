# Quick Authentication Testing Guide

Your authentication system is now running! Here's how to test it.

## ✅ Server Status

```bash
# Check server is running
curl http://localhost:8000/health
```

**Expected:** `{"status":"healthy",...}`

---

## 🔑 API Key Authentication Tests

### Test 1: Use the generated API key

```bash
# Your test API key (from test output):
export API_KEY="sk_test_K17wg5F09jsQgXkjW0SZuzxBVlOv0oQZ"

# Test authenticated request
curl -X GET "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer $API_KEY"
```

**Expected:** `200 OK` (empty list or existing accounts)

### Test 2: Create a new account (admin only)

```bash
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_account_id": "test_ig_123",
    "username": "testuser",
    "access_token": "test_token_abc",
    "crm_webhook_url": "https://example.com/webhook",
    "webhook_secret": "test_secret"
  }'
```

**Expected:** `201 Created` with account details

### Test 3: Invalid API key (should fail)

```bash
curl -X GET "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer sk_test_INVALID_KEY" \
  -w "\nStatus: %{http_code}\n"
```

**Expected:** `401 Unauthorized` with error message

### Test 4: Missing authorization (should fail)

```bash
curl -X GET "http://localhost:8000/api/v1/accounts" \
  -w "\nStatus: %{http_code}\n"
```

**Expected:** `401 Unauthorized`

---

## 🖥️ UI Authentication Tests

### Test 1: Login with valid credentials

```bash
curl -X POST "http://localhost:8000/ui/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }' | jq
```

**Expected:** JWT token response:
```json
{
  "token": "eyJ...",
  "expires_in": 86400,
  "username": "admin",
  "role": "admin",
  "display_name": "Administrator"
}
```

### Test 2: Use JWT token to access UI endpoints

```bash
# Save the token from previous step
export UI_TOKEN="<paste-jwt-token-here>"

# Test authenticated UI request
curl -X GET "http://localhost:8000/ui/conversations" \
  -H "Authorization: Bearer $UI_TOKEN"
```

**Expected:** `200 OK` with conversations list

### Test 3: Invalid password (should fail)

```bash
curl -X POST "http://localhost:8000/ui/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "wrongpassword"
  }' \
  -w "\nStatus: %{http_code}\n"
```

**Expected:** `401 Unauthorized`

### Test 4: Demo user login

```bash
curl -X POST "http://localhost:8000/ui/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo",
    "password": "demo123"
  }' | jq
```

**Expected:** JWT token with `"role": "viewer"`

---

## 🔧 Generate More API Keys

### Admin key

```bash
python -m app.cli.generate_api_key \
  --name "Production Admin" \
  --type admin \
  --env live
```

### Account-scoped key

```bash
# First, create an account and note its account_id
# Then create a key scoped to that account:

python -m app.cli.generate_api_key \
  --name "Customer A Integration" \
  --type account \
  --env live \
  --accounts acc_xyz123
```

### Key with expiration

```bash
python -m app.cli.generate_api_key \
  --name "Temporary Key" \
  --type admin \
  --env test \
  --expires 30  # expires in 30 days
```

---

## 🧪 Permission Testing

### Test account-scoped permissions

```bash
# Create an account-scoped key
python -m app.cli.generate_api_key \
  --name "Scoped Key" \
  --type account \
  --env test \
  --accounts acc_test123

# Try to create a new account (should fail - only admins can do this)
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer <scoped-key>" \
  -H "Content-Type: application/json" \
  -d '{"instagram_account_id": "new_account",...}' \
  -w "\nStatus: %{http_code}\n"
```

**Expected:** `403 Forbidden` - "Only admin API keys can create new accounts"

---

## 📊 API Documentation

View interactive API docs with auth examples:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 🐛 Troubleshooting

### "Invalid API key" errors

1. Check the key format starts with `sk_test_` or `sk_live_`
2. Verify the key wasn't revoked
3. Make sure you copied the entire key (40 characters total)

### "Permission denied" errors

1. Use an admin key for creating accounts
2. Use account-scoped keys only for the accounts they're assigned to
3. Generate a new admin key if needed

### "Invalid or expired token" (UI)

1. Tokens expire after 24 hours by default
2. Log in again to get a fresh token
3. Check JWT_SECRET_KEY hasn't changed

### Server not responding

```bash
# Check server is running
ps aux | grep uvicorn

# Check logs
tail -f /tmp/uvicorn.log  # if using the test setup

# Restart server
uvicorn app.main:app --reload
```

---

## ✅ Success Checklist

- [ ] Server starts without errors
- [ ] Health endpoint returns 200
- [ ] Can generate API keys
- [ ] API key authentication works
- [ ] Invalid API keys are rejected
- [ ] UI login works with admin/admin123
- [ ] JWT tokens are validated
- [ ] Permission checks work correctly

---

## 📚 Next Steps

1. **Read the full docs:** [AUTHENTICATION.md](AUTHENTICATION.md)
2. **Generate your production keys** with `--env live`
3. **Set JWT_SECRET_KEY** in `.env` before production
4. **Test with real Instagram credentials** (see README.md)
5. **Deploy to your server** and test end-to-end

---

**Need help?** Check the logs, review AUTHENTICATION.md, or run `python test_authentication.py` again.
