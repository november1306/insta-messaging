# Instagram Messenger Automation - Quick Reference Guide

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INSTAGRAM / FACEBOOK PLATFORM                        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    Instagram DM    │   Instagram API
                    (Webhook POST)  │   (Message Send)
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FastAPI APPLICATION                                   │
│                    (Python 3.12 + Async/Await)                              │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ API ROUTES (app/api/)                                                  │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  webhooks.py          messages.py         accounts.py    auth.py      │ │
│  │  ┌──────────────┐    ┌──────────────┐   ┌──────────────┐ ┌─────────┐ │ │
│  │  │  Instagram   │    │   Message    │   │   Account    │ │  Bearer │ │ │
│  │  │  Webhooks    │    │   Sending    │   │ Management   │ │  Token  │ │ │
│  │  │  Receiver    │    │   API        │   │   API        │ │  (Stub) │ │ │
│  │  │              │    │              │   │              │ │         │ │ │
│  │  │ GET verify   │    │ POST send    │   │ POST create  │ │ verify_ │ │ │
│  │  │ POST receive │    │ GET status   │   │ account      │ │ api_key │ │ │
│  │  └──────────────┘    └──────────────┘   └──────────────┘ └─────────┘ │ │
│  │       │                     │                    │           │       │ │
│  │       │ Signature Check     │ Idempotency       │ Store      │       │ │
│  │       │ & Extraction        │ Check & Send      │ Config     │       │ │
│  │       │                     │                    │           │       │ │
│  └───────┼─────────────────────┼────────────────────┼───────────┼───────┘ │
│          │                     │                    │           │         │
└──────────┼─────────────────────┼────────────────────┼───────────┼─────────┘
           │                     │                    │           │
        ┌──┴─────────┐       ┌───┴──────┐        ┌───┴────┐      └─┐
        │ Services   │       │ Clients  │        │   DB   │        │
        │ (Business  │       │ (HTTP)   │        │ Layer  │        │
        │  Logic)    │       │          │        │        │        │
        │            │       │          │        │        │        │
        │ Webhook    │◄──────┤Instagram │       │ Models │        │
        │ Forwarder  │       │ Client   │       │        │        │
        │            │       │          │       │ SQLite │   All endpoints
        └────┬───────┘       └──────────┘       │ (MVP)  │   require
             │                                  │ MySQL  │   Bearer Token
             │                                  │(prod)  │
             │               ┌──────────────────┤        │
             │               │                  │        │
             │               │                  └────┬───┘
             │               │                       │
             │      ┌────────┴────────┐              │
             │      │ Repositories    │              │
             │      │ (Data Access)   │              │
             │      │                 │              │
             │      │ Message         │◄─────────────┘
             │      │ Repository      │
             │      │ (SQLAlchemy)    │
             │      └────────┬────────┘
             │               │
             ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE (SQLite/MySQL)                              │
│                                                                             │
│  Tables:                                                                    │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  messages       │  │  accounts        │  │ crm_outbound_messages    │  │
│  ├─────────────────┤  ├──────────────────┤  ├──────────────────────────┤  │
│  │ id (PK)         │  │ id (PK)          │  │ id (PK)                  │  │
│  │ sender_id       │  │ instagram_acc_id │  │ account_id (FK)          │  │
│  │ recipient_id    │  │ username         │  │ recipient_id             │  │
│  │ message_text    │  │ access_token_enc │  │ message_text             │  │
│  │ direction       │  │ crm_webhook_url  │  │ idempotency_key (U)      │  │
│  │ timestamp       │  │ webhook_secret   │  │ status                   │  │
│  │ created_at      │  │ created_at       │  │ instagram_msg_id         │  │
│  │                 │  │                  │  │ error_code/message       │  │
│  │ Indexes:        │  │ Indexes:         │  │ created_at               │  │
│  │ idx_timestamp   │  │ idx_instagram_id │  │                          │  │
│  │ idx_sender      │  │                  │  │ Indexes:                 │  │
│  │                 │  │                  │  │ idx_account_status       │  │
│  └─────────────────┘  └──────────────────┘  └──────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
        │                                             ▲
        │                                             │
        │          Alembic Migrations                 │
        │          (Database Schema Management)       │
        │                                             │
        └─────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL INTEGRATIONS                               │
│                                                                             │
│  ┌──────────────────────────┐        ┌──────────────────────────────────┐  │
│  │   Instagram Graph API    │        │      CRM System                  │  │
│  │  (Message Sending)       │        │  (Webhooks Receiver)             │  │
│  │                          │        │                                  │  │
│  │  POST /me/messages       │        │  POST /webhooks/instagram        │  │
│  │  GET /{user_id}          │        │  (Receives forwarded messages)   │  │
│  │  Access Token: IGAA...   │        │  Signature: HMAC-SHA256          │  │
│  └──────────────────────────┘        └──────────────────────────────────┘  │
│           ▲                                      ▲                          │
│           │                                      │                          │
│           └──────────────────┬───────────────────┘                          │
│                              │                                             │
│                         Uses httpx                                         │
│                      (Async HTTP)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Message Flow - Detailed Sequence

### INBOUND: Instagram → Router → Database → CRM

```
Step 1: Instagram User sends DM
        └─→ Facebook detects message event

Step 2: Facebook sends webhook POST to /webhooks/instagram
        Headers: X-Hub-Signature-256: sha256=<signature>
        Body: {entry: [{messaging: [{sender, recipient, message, timestamp}]}]}

Step 3: Router validates signature
        └─→ HMAC-SHA256(INSTAGRAM_APP_SECRET, raw_body) == signature header
        └─→ If invalid: Return 401, log warning
        └─→ If valid: Continue to step 4

Step 4: Extract message data from payload
        └─→ message_id, sender_id, recipient_id, message_text, timestamp
        └─→ If missing fields: Skip silently, return 200 OK

Step 5: Save to DATABASE (messages table)
        └─→ Check for duplicates (webhook retries)
        └─→ If exists: Skip to step 7
        └─→ If new: Store and continue to step 6

Step 6a: Check AUTO-REPLY rules
         └─→ Query message_rules.py: get_reply(message_text)
         └─→ If no match: Go to step 7
         └─→ If match:
             └─→ Get reply text (may contain {username} placeholder)
             └─→ If has {username}: Fetch from Instagram API
             └─→ Send reply via Instagram API
             └─→ Store as outbound message in database

Step 6b: In background (fire-and-forget):
         └─→ asyncio.create_task(_forward_to_crm(message))

Step 7: Forward to CRM webhook (background task)
        └─→ Look up account in accounts table by instagram_account_id
        └─→ If not found: Log warning, return
        └─→ Get crm_webhook_url and webhook_secret
        └─→ Build payload: {event, message_id, sender_id, message, timestamp}
        └─→ Generate signature: HMAC-SHA256(webhook_secret, json_payload)
        └─→ POST to CRM with X-Hub-Signature-256 header
        └─→ If success (2xx): Log info
        └─→ If failure: Log warning (no retries in MVP)

Step 8: Return 200 OK to Instagram
        └─→ Instagram assumes webhook was processed
        └─→ Won't retry even if our processing had errors
```

### OUTBOUND: CRM → Router → Instagram → Database

```
Step 1: CRM makes API request
        POST /api/v1/messages/send
        Authorization: Bearer <api_key>
        {
          "account_id": "acc_abc123",
          "recipient_id": "user_id",
          "message": "Hello!",
          "idempotency_key": "order_123"
        }

Step 2: Verify Bearer token
        └─→ Check Authorization header format
        └─→ In development: Accept any non-empty token
        └─→ In production: Would validate real API key (not implemented)

Step 3: Check idempotency
        └─→ Query outbound_messages by idempotency_key
        └─→ If found: Return existing message_id with status
        └─→ If not found: Continue to step 4

Step 4: Create outbound_messages record
        └─→ Generate message_id: msg_<12_random_chars>
        └─→ Set status: "pending"
        └─→ Store in database

Step 5: Send via Instagram API
        POST https://graph.instagram.com/v21.0/me/messages
        {
          "recipient": {"id": "<recipient_id>"},
          "message": {"text": "<message_text>"}
        }
        Param: access_token=<INSTAGRAM_PAGE_ACCESS_TOKEN>

Step 6: Update message status based on response
        └─→ If 200 OK: status = "sent", store instagram_message_id
        └─→ If error: status = "failed", store error_code and error_message
        └─→ Commit to database

Step 7: Return 202 Accepted
        {
          "message_id": "msg_abc123",
          "status": "sent|failed",
          "created_at": "2025-11-15T10:30:00Z"
        }

Step 8: CRM can check status
        GET /api/v1/messages/{message_id}/status
        └─→ Query outbound_messages by message_id
        └─→ Return current status and error details if failed
```

---

## Key Files at a Glance

```python
# APPLICATION ENTRY POINT
app/main.py
  ├─ FastAPI app initialization
  ├─ Lifespan management (startup/shutdown)
  ├─ Route registration
  └─ Documentation endpoints

# API HANDLERS
app/api/webhooks.py (326 lines)
  ├─ verify_webhook() - GET for webhook setup
  ├─ handle_webhook() - POST for incoming messages
  ├─ _handle_auto_reply() - Auto-reply logic
  ├─ _validate_webhook_signature() - Security
  ├─ _extract_message_data() - Payload parsing
  └─ _forward_to_crm() - Background task

app/api/messages.py (258 lines)
  ├─ send_message() - POST /api/v1/messages/send
  ├─ get_message_status() - GET /api/v1/messages/{id}/status
  └─ Pydantic request/response models

app/api/accounts.py (152 lines)
  ├─ create_account() - POST /api/v1/accounts
  ├─ encrypt_credential() - Base64 (MVP)
  └─ decrypt_credential() - Base64 (MVP)

app/api/auth.py (69 lines)
  └─ verify_api_key() - Bearer token stub

# DATABASE & MODELS
app/db/models.py (86 lines)
  ├─ MessageModel - ORM for messages table
  ├─ Account - ORM for accounts table
  └─ OutboundMessage - ORM for outbound_messages table

app/db/connection.py (84 lines)
  ├─ init_db() - Initialize SQLite
  ├─ get_db_session() - Dependency injection
  └─ close_db() - Cleanup

# CORE ABSTRACTIONS
app/core/interfaces.py (46 lines)
  ├─ Message - Domain model
  └─ IMessageRepository - Interface

# DATA ACCESS LAYER
app/repositories/message_repository.py (114 lines)
  ├─ save() - Store message
  └─ get_by_id() - Retrieve message

# EXTERNAL CLIENTS
app/clients/instagram_client.py (237 lines)
  ├─ send_message() - Send via Instagram API
  └─ get_user_profile() - Fetch user info

# SERVICES & BUSINESS LOGIC
app/services/webhook_forwarder.py (193 lines)
  ├─ forward_message() - Send to CRM webhook
  ├─ _build_payload() - Construct webhook JSON
  └─ _generate_signature() - HMAC-SHA256

# AUTO-REPLY RULES
app/rules/message_rules.py (44 lines)
  └─ get_reply() - Match message to reply

# CONFIGURATION
app/config.py (113 lines)
  ├─ Settings class
  ├─ Environment variable loading
  └─ Production/development mode handling
```

---

## Quick Command Reference

### Setup & Running

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
alembic upgrade head

# Run development server
uvicorn app.main:app --reload

# Run tests
pytest
pytest --cov=app
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Required variables for production
export FACEBOOK_VERIFY_TOKEN=my_token
export FACEBOOK_APP_SECRET=secret
export INSTAGRAM_APP_SECRET=secret
export INSTAGRAM_PAGE_ACCESS_TOKEN=IGAA...
export INSTAGRAM_BUSINESS_ACCOUNT_ID=12345

# Optional
export ENVIRONMENT=development
export DATABASE_URL=sqlite+aiosqlite:///./instagram_automation.db
export LOG_LEVEL=INFO
```

### Testing API Endpoints

```bash
# Create account configuration
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer test_key" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_account_id": "12345",
    "username": "myshop",
    "access_token": "IGAA...",
    "crm_webhook_url": "https://crm.example.com/webhooks",
    "webhook_secret": "secret"
  }'

# Send message
curl -X POST "http://localhost:8000/api/v1/messages/send" \
  -H "Authorization: Bearer test_key" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acc_123",
    "recipient_id": "user_456",
    "message": "Hello!",
    "idempotency_key": "order_123"
  }'

# Check message status
curl -X GET "http://localhost:8000/api/v1/messages/msg_abc/status" \
  -H "Authorization: Bearer test_key"

# Health check
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

---

## Architecture Patterns Used

1. **Async/Await** - Full asynchronous architecture with asyncio
2. **Repository Pattern** - Data access layer abstraction
3. **Dependency Injection** - FastAPI dependencies
4. **Domain Models** - Separate from database models
5. **Service Layer** - Business logic isolation
6. **Error Handling** - Specific exception types
7. **Configuration Management** - Environment-based settings
8. **Webhook Signature Validation** - HMAC-SHA256 security
9. **Fire-and-Forget** - Background tasks that don't block
10. **Idempotency** - Duplicate prevention with unique keys

---

## Priority & Status

**IMPLEMENTED (Phase 1 - MVP)**
- ✅ Instagram webhook receiving
- ✅ Message storage
- ✅ Auto-reply rules
- ✅ CRM message sending
- ✅ Account management
- ✅ Health check
- ✅ Webhook forwarding to CRM

**IN PROGRESS**
- 🚧 API documentation (OpenAPI spec exists but not fully implemented)

**PLANNED (Phase 2+)**
- ❌ Real API key validation (currently stub)
- ❌ Credential encryption (currently base64)
- ❌ Rate limiting
- ❌ Message queuing & retries
- ❌ Delivery status webhooks
- ❌ Advanced analytics

