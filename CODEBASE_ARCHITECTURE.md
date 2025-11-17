# Instagram Messenger Automation - Complete Architecture Overview

## Project Summary
Instagram Messenger Automation is an **e-commerce automation platform** that receives Instagram Direct Messages (DMs), processes them, and forwards them to CRM systems. It supports auto-replies based on configurable rules and provides a REST API for CRM integration.

---

## 1. PROJECT STRUCTURE

### Directory Layout
```
/home/user/insta-messaging/
├── app/                          # Main application code
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Configuration management
│   ├── version.py                # Version info
│   │
│   ├── api/                      # FastAPI routers (API endpoints)
│   │   ├── webhooks.py           # Instagram webhook receiver & auto-reply
│   │   ├── messages.py           # CRM message sending API
│   │   ├── accounts.py           # CRM account management
│   │   └── auth.py               # Authentication (stub for MVP)
│   │
│   ├── db/                       # Database layer
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   └── connection.py         # AsyncIO database connection management
│   │
│   ├── clients/                  # External service clients
│   │   └── instagram_client.py   # Instagram Graph API client
│   │
│   ├── core/                     # Core abstractions
│   │   └── interfaces.py         # Domain models & repository interfaces
│   │
│   ├── repositories/             # Data access layer
│   │   └── message_repository.py # Message storage/retrieval
│   │
│   ├── services/                 # Business logic
│   │   └── webhook_forwarder.py  # CRM webhook forwarding service
│   │
│   ├── rules/                    # Auto-reply rules
│   │   ├── message_rules.py      # User-defined reply rules
│   │   └── reply_rules.py        # Rule interface
│   │
│   └── static/                   # Static files
│       └── openapi.yaml          # API documentation
│
├── alembic/                      # Database migrations
│   ├── env.py
│   ├── alembic.ini
│   └── versions/                 # Migration files
│
├── tests/                        # Test suite
├── requirements.txt              # Python dependencies
├── ARCHITECTURE.md               # Architecture design document
├── README.md                     # Getting started guide
└── .env.example                  # Example environment variables
```

---

## 2. WEB FRAMEWORK & TECH STACK

### Backend Framework: **FastAPI**
- **Version**: 0.115.6
- **Server**: Uvicorn 0.32.0 (ASGI)
- **Python**: 3.12+ (async support)

### Database
- **ORM**: SQLAlchemy 2.0.23 (async)
- **Database**: SQLite (MVP), MySQL (production target)
- **Migrations**: Alembic 1.12.1
- **Async Driver**: aiosqlite 0.19.0

### Key Dependencies
```
fastapi==0.115.6
uvicorn[standard]==0.32.0
httpx==0.27.2                 # Async HTTP client
sqlalchemy==2.0.23
aiosqlite==0.19.0
alembic==1.12.1
pydantic==2.5.0               # Data validation
pydantic-settings==2.1.0
python-dotenv==1.0.1          # Environment variables
pyyaml==6.0.1
pytest==8.3.5 & pytest-asyncio==1.2.0
```

---

## 3. MAIN APPLICATION ENTRY POINT

### File: `/home/user/insta-messaging/app/main.py`

**Purpose**: FastAPI application initialization and routing

**Key Features**:
- **Lifespan Management**: Handles startup/shutdown (DB init, logging)
- **OpenAPI Documentation**: Serves custom `/docs` and `/redoc` endpoints
- **Router Registration**: Includes three main router modules:
  - `webhooks.router` - Instagram webhook handling
  - `accounts.router` - CRM account management
  - `messages.router` - CRM message API

**Endpoints**:
```python
GET  /                    # Root info endpoint
GET  /health              # Health check
GET  /openapi.json        # OpenAPI spec
GET  /docs                # Swagger UI documentation
GET  /redoc               # Alternative ReDoc documentation
```

---

## 4. THE "INSTA ROUTER" - DETAILED ANALYSIS

### What Is It?
The "**insta router**" is the webhook receiver and message processor that sits between Instagram/Facebook and your business logic. It receives incoming DMs from Instagram and processes them.

### File: `/home/user/insta-messaging/app/api/webhooks.py`

### How It Works - Message Flow

```
Instagram DM Event
    ↓
Facebook Webhook (HTTPS POST)
    ↓
/webhooks/instagram endpoint (FastAPI)
    ↓
1. Signature Validation (HMAC-SHA256)
2. Payload Extraction
    ├─→ Extract message data
    ├─→ Create domain Message object
    ├─→ Save to database
    ├─→ Trigger auto-reply
    └─→ Forward to CRM webhook
    ↓
Return 200 OK (always, even if processing fails)
```

### Key Functions

#### 1. **Webhook Verification** (GET)
```python
GET /webhooks/instagram?hub.mode=subscribe&hub.verify_token=xxx&hub.challenge=yyy
```
- Facebook calls this to verify webhook ownership
- Returns challenge if verify_token matches
- Called once during webhook setup

#### 2. **Webhook Handler** (POST)
```python
POST /webhooks/instagram
Headers: X-Hub-Signature-256: sha256=<signature>
Body: {
  "object": "instagram",
  "entry": [{
    "messaging": [{
      "sender": {"id": "user_id"},
      "recipient": {"id": "business_account_id"},
      "timestamp": 1234567890000,
      "message": {"mid": "msg_id", "text": "Hello!"}
    }]
  }]
}
```

### Insta Router API Endpoints

#### **Receiving Messages (Inbound)**
```
POST /webhooks/instagram
- Receives incoming messages from Instagram
- Validates X-Hub-Signature-256 header
- Extracts message data
- Stores in messages table
- Triggers auto-reply if rules match
- Forwards to CRM webhook
- Always returns 200 OK to prevent retries
```

#### **Sending Messages (Outbound)**
```
POST /webhooks/send (DEPRECATED - use /api/v1/messages/send instead)
- Manual message sending endpoint
- Used for testing and direct API calls
```

### Security

**Webhook Signature Validation**:
```python
# Instagram uses HMAC-SHA256
signature = HMAC-SHA256(
    secret=INSTAGRAM_APP_SECRET,
    message=raw_request_body
)
```

The router validates this before processing any webhook data.

### Error Handling

- **Signature invalid**: Returns 401 Unauthorized
- **Payload missing fields**: Returns 200 OK (skips processing)
- **Database errors**: Logs error, returns 200 OK (prevents Instagram retries)
- **Auto-reply fails**: Logs error, continues to CRM forwarding
- **CRM forwarding fails**: Logs warning, doesn't affect webhook response

---

## 5. CURRENT MESSAGE HANDLING ARCHITECTURE

### Message Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ INBOUND MESSAGE FLOW (Instagram → Database → CRM)           │
└─────────────────────────────────────────────────────────────┘

Instagram User sends DM
         ↓
Facebook Webhook POST /webhooks/instagram
         ↓
Signature Validation (X-Hub-Signature-256)
         ↓
Extract Message Data
  • message ID, sender ID, recipient ID
  • message text, timestamp
         ↓
Save to DATABASE (messages table)
         ↓
         ├─→ Handle AUTO-REPLY (if rules match)
         │    • Check reply_rules for matching pattern
         │    • Fetch username from Instagram API
         │    • Send reply via Instagram API
         │    • Store as outbound message
         │
         └─→ Forward to CRM WEBHOOK
              • Look up account by instagram_account_id
              • Get CRM webhook URL from accounts table
              • Send InboundMessageWebhook payload
              • Sign with HMAC-SHA256
              • Fire-and-forget (asyncio.create_task)

Return 200 OK to Instagram


┌─────────────────────────────────────────────────────────────┐
│ OUTBOUND MESSAGE FLOW (CRM → Instagram → Database)          │
└─────────────────────────────────────────────────────────────┘

CRM makes request
         ↓
POST /api/v1/messages/send
  Authorization: Bearer <api_key>
  {
    "account_id": "acc_xxx",
    "recipient_id": "user_id",
    "message": "Hello customer!",
    "idempotency_key": "order_123"
  }
         ↓
API Key Validation (Bearer token stub)
         ↓
Check Idempotency (prevent duplicate sends)
  • Query outbound_messages by idempotency_key
  • If exists, return existing message_id
         ↓
Create outbound_messages record (status: pending)
         ↓
Send via Instagram API
  POST https://graph.instagram.com/v21.0/me/messages
  With access token from settings
         ↓
Update Status
  • success → status: "sent"
  • error → status: "failed" + error_code
         ↓
Return 202 Accepted with message_id
```

### Database Models

#### **messages** table
```sql
CREATE TABLE messages (
    id VARCHAR(100) PRIMARY KEY,        -- Instagram message ID
    sender_id VARCHAR(50) NOT NULL,     -- Instagram user ID
    recipient_id VARCHAR(50) NOT NULL,  -- Instagram business account ID
    message_text TEXT,                  -- Message content
    direction VARCHAR(10) NOT NULL,     -- 'inbound' or 'outbound'
    timestamp DATETIME NOT NULL,        -- When message was sent
    created_at DATETIME DEFAULT NOW(),  -- When stored
    
    INDEX idx_timestamp (timestamp),
    INDEX idx_sender (sender_id)
);
```

#### **outbound_messages** table (CRM Integration)
```sql
CREATE TABLE outbound_messages (
    id VARCHAR(50) PRIMARY KEY,                -- Our message ID
    account_id VARCHAR(50) FOREIGN KEY,        -- Reference to accounts table
    recipient_id VARCHAR(50) NOT NULL,         -- Instagram user PSID
    message_text TEXT NOT NULL,                -- Message content
    idempotency_key VARCHAR(100) UNIQUE,       -- Prevent duplicates
    status VARCHAR(20) DEFAULT 'pending',      -- pending | sent | failed
    instagram_message_id VARCHAR(100),         -- Set after successful send
    error_code VARCHAR(50),                    -- Error code if failed
    error_message TEXT,                        -- Error message if failed
    created_at DATETIME DEFAULT NOW(),
    
    INDEX idx_account_status (account_id, status),
    UNIQUE INDEX unique_idempotency_key (idempotency_key)
);
```

#### **accounts** table (CRM Integration)
```sql
CREATE TABLE accounts (
    id VARCHAR(50) PRIMARY KEY,                    -- Our internal account ID
    instagram_account_id VARCHAR(50) UNIQUE,       -- Instagram's account ID
    username VARCHAR(100) NOT NULL,                -- Instagram username
    access_token_encrypted TEXT NOT NULL,          -- Encrypted access token
    crm_webhook_url VARCHAR(500) NOT NULL,         -- Where to forward messages
    webhook_secret VARCHAR(100) NOT NULL,          -- For webhook signature
    created_at DATETIME DEFAULT NOW(),
    
    UNIQUE INDEX unique_instagram_account_id (instagram_account_id)
);
```

---

## 6. API ENDPOINTS

### All Endpoints by Category

#### **System**
```
GET  /                    # Root info
GET  /health              # Health check
GET  /openapi.json        # OpenAPI specification
GET  /docs                # Swagger UI
GET  /redoc               # ReDoc documentation
```

#### **Instagram Webhooks**
```
GET  /webhooks/instagram     # Webhook verification (Facebook setup)
POST /webhooks/instagram     # Receive messages (Instagram → Router)
POST /webhooks/send          # Send message (deprecated)
```

#### **Messages API** (CRM Integration)
```
POST /api/v1/messages/send                # Send message (CRM → Instagram)
GET  /api/v1/messages/{message_id}/status # Check delivery status
```

Request Example:
```bash
curl -X POST "http://localhost:8000/api/v1/messages/send" \
  -H "Authorization: Bearer test_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acc_abc123",
    "recipient_id": "1558635688632972",
    "message": "Hello!",
    "idempotency_key": "order_123"
  }'
```

Response (202 Accepted):
```json
{
  "message_id": "msg_abc123def456",
  "status": "sent",
  "created_at": "2025-11-15T10:30:00Z"
}
```

#### **Accounts API** (CRM Integration)
```
POST /api/v1/accounts                  # Create account configuration
GET  /api/v1/accounts/{account_id}     # Get account (planned)
PUT  /api/v1/accounts/{account_id}     # Update account (planned)
```

Request Example:
```bash
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer test_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_account_id": "17841405728832526",
    "username": "myshop",
    "access_token": "IGAA...",
    "crm_webhook_url": "https://crm.example.com/webhooks/instagram",
    "webhook_secret": "shared_secret_123"
  }'
```

Response (201 Created):
```json
{
  "account_id": "acc_abc123",
  "instagram_account_id": "17841405728832526",
  "username": "myshop",
  "crm_webhook_url": "https://crm.example.com/webhooks/instagram",
  "created_at": "2025-11-15T10:30:00Z"
}
```

---

## 7. CONFIGURATION MANAGEMENT

### Configuration Layer: `/home/user/insta-messaging/app/config.py`

**Settings Class**:
```python
class Settings:
    # Environment
    environment: str          # "development" | "production"
    
    # Instagram Credentials (from environment)
    facebook_verify_token: str            # Custom token for webhook verification
    facebook_app_secret: str              # For webhook signature validation
    instagram_app_secret: str             # For webhook signature validation
    instagram_page_access_token: str      # For sending messages
    instagram_business_account_id: str    # Your business account ID
    
    # Server
    host: str                 # Default: "0.0.0.0"
    port: int                 # Default: 8000
    
    # Database
    database_url: str         # Default: "sqlite+aiosqlite:///./instagram_automation.db"
    
    # Webhooks
    crm_webhook_timeout: float  # Default: 10.0 seconds
    
    # Logging
    log_level: str            # Default: "INFO"
```

### Environment Variables

**Required (Production)**:
```env
FACEBOOK_VERIFY_TOKEN=my_webhook_token_xyz
FACEBOOK_APP_SECRET=abc123xyz789
INSTAGRAM_APP_SECRET=secret_key_from_instagram
INSTAGRAM_PAGE_ACCESS_TOKEN=IGAA...
INSTAGRAM_BUSINESS_ACCOUNT_ID=12345678
ENVIRONMENT=production
```

**Optional (Development)**:
```env
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./instagram_automation.db
LOG_LEVEL=INFO
CRM_WEBHOOK_TIMEOUT=10.0
```

---

## 8. AUTHENTICATION & AUTHORIZATION

### Current Implementation: STUB (MVP)

**File**: `/home/user/insta-messaging/app/api/auth.py`

**How It Works**:
- **Development Mode**: Accepts any Bearer token (stub authentication)
- **Production Mode**: Blocks all API requests with 503 error

**Authentication Requirement**:
All CRM API endpoints require:
```
Authorization: Bearer <any_non_empty_token>
```

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/messages/send" \
  -H "Authorization: Bearer my_test_key" \
  -H "Content-Type: application/json" \
  -d '...'
```

**Status**:
- ✅ Stub authentication works in development
- ❌ Real API key validation planned for Priority 2

---

## 9. CORE ARCHITECTURE PATTERNS

### 1. Domain Model (Core Interfaces)

File: `/home/user/insta-messaging/app/core/interfaces.py`

```python
class Message:
    """Domain model for messages (not tied to database)"""
    id: str
    sender_id: str
    recipient_id: str
    message_text: str
    direction: str                # 'inbound' | 'outbound'
    timestamp: datetime
    created_at: datetime
```

### 2. Repository Pattern

File: `/home/user/insta-messaging/app/repositories/message_repository.py`

```python
class IMessageRepository(ABC):
    """Interface for message storage"""
    async def save(message: Message) -> Message
    async def get_by_id(message_id: str) -> Optional[Message]

class MessageRepository(IMessageRepository):
    """SQLAlchemy implementation"""
    # Converts between domain Message and MessageModel
```

### 3. Service Layer

File: `/home/user/insta-messaging/app/services/webhook_forwarder.py`

```python
class WebhookForwarder:
    """Business logic for forwarding messages to CRM"""
    async def forward_message(message: Message, account: Account) -> bool
    def _build_payload(message, account) -> dict
    def _generate_signature(payload, secret) -> str
```

### 4. External Client (HTTP)

File: `/home/user/insta-messaging/app/clients/instagram_client.py`

```python
class InstagramClient:
    """Instagram Graph API client"""
    async def send_message(recipient_id: str, message_text: str) -> SendMessageResponse
    async def get_user_profile(user_id: str) -> Optional[dict]
```

---

## 10. AUTO-REPLY SYSTEM

### How Auto-Replies Work

**File**: `/home/user/insta-messaging/app/rules/message_rules.py`

1. **Trigger**: When inbound message is saved to database
2. **Rule Matching**: Check message text against defined rules
3. **Reply Generation**: If rule matches, get reply text
4. **Username Resolution**: If reply contains `{username}`, fetch from Instagram
5. **Send**: Send reply via Instagram API
6. **Store**: Save as outbound message

**Current Rules** (edit to customize):
```python
def get_reply(message_text: str) -> Optional[str]:
    msg = message_text.lower()
    
    # Rule 1: "order66" keyword
    if "order66" in msg:
        return "Order 66 confirmed, {username}! Your request has been received."
    
    # Add more rules here...
    return None  # No match
```

**Example Reply with Personalization**:
```
Incoming: "Hello, can you process my order?"
Rule Match: "help" keyword
Reply Template: "Hello {username}, how can we help?"
Resolved Reply: "Hello @john_doe, how can we help?"
```

---

## 11. DATABASE & MIGRATIONS

### Migration System: Alembic

**File**: `/home/user/insta-messaging/alembic.ini`

**How to Run**:
```bash
# Apply all pending migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback
alembic downgrade -1
```

### Existing Migrations

```
1. c67fc6b5677b - Simplified schema (messages only, YAGNI)
2. 57fc6c6e6f58 - CRM integration tables (accounts, outbound_messages)
3. e75f64bf2da2 - Instagram message tracking (error handling)
```

### Current Database Schema

**Tables**:
- `messages` - All inbound/outbound messages
- `accounts` - CRM account configurations
- `outbound_messages` - Tracking for CRM-sent messages

---

## 12. FRONTEND/API DOCUMENTATION

### Interactive API Docs

**Endpoints**:
```
GET /docs     → Swagger UI (http://localhost:8000/docs)
GET /redoc    → ReDoc UI (http://localhost:8000/redoc)
GET /openapi.json → OpenAPI 3.0 specification
```

**OpenAPI Spec File**:
- Location: `/home/user/insta-messaging/app/static/openapi.yaml`
- Format: OpenAPI 3.0.3
- Includes: All endpoints, request/response schemas, examples, security schemes

**Key Documentation Files**:
- `README.md` - Getting started
- `ARCHITECTURE.md` - Design document
- `SETUP.md` - Installation guide
- `SECURITY.md` - Security considerations

---

## 13. SECURITY CONSIDERATIONS

### Currently Implemented ✅

1. **Webhook Signature Validation**
   - HMAC-SHA256 validation of Instagram webhooks
   - Constant-time comparison prevents timing attacks

2. **Bearer Token Authentication**
   - Required for all CRM API endpoints
   - Stub implementation for MVP

3. **Idempotency Protection**
   - Prevents duplicate message sends
   - Uses unique idempotency_key

### Not Yet Implemented ❌

1. **Credential Encryption**
   - Currently using base64 encoding (NOT secure)
   - TODO: Implement Fernet encryption in Priority 2

2. **Real API Key Validation**
   - Stub accepts any Bearer token
   - TODO: Database-backed API key system

3. **Rate Limiting**
   - Not implemented
   - TODO: Add in Priority 2

4. **CORS Security**
   - Not configured
   - TODO: Add in Priority 2

---

## 14. KEY IMPLEMENTATION DETAILS

### Async/Await Pattern

The entire application is **fully asynchronous**:
- FastAPI with async handlers
- SQLAlchemy 2.0 async support
- httpx for async HTTP requests
- asyncio for background tasks

### Background Tasks

Messages forwarded to CRM are sent as **fire-and-forget**:
```python
asyncio.create_task(_forward_to_crm(message))
```

This prevents CRM failures from blocking the Instagram webhook response.

### Transaction Management

Database transactions are handled by the dependency injection:
```python
async def get_db_session():
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
```

### Error Handling

**Instagram Webhook** (always returns 200):
- Signature invalid → Log & return 200
- DB error → Log & return 200
- Auto-reply fails → Log & continue
- CRM forward fails → Log warning & return 200

This ensures Instagram won't retry invalid webhooks.

---

## 15. DEPLOYMENT ARCHITECTURE

### Supported Deployment Methods

1. **Local Development**
   ```bash
   uvicorn app.main:app --reload
   ```

2. **Production Server**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Docker** (Ready)
   - Dockerfile exists for containerization
   - Can be deployed to any container platform

4. **Railway** (Recommended)
   - Auto-detects Python
   - Environment variables via dashboard
   - Automatic HTTPS

5. **DigitalOcean**
   - VM deployment with systemd
   - Process manager for auto-restart
   - See DEPLOYMENT-DIGITALOCEAN.md

---

## 16. PRIORITY ROADMAP

### Phase 1: MVP ✅ (Current)
- [x] Webhook receiving
- [x] Message storage
- [x] Auto-replies
- [x] CRM API (send messages)
- [x] Account management

### Phase 2: Production Ready 🚧
- [ ] Real API key validation
- [ ] Credential encryption (Fernet)
- [ ] Rate limiting
- [ ] Account validation on send

### Phase 3: Async Delivery
- [ ] Message queue (Redis/RabbitMQ)
- [ ] Retry logic with exponential backoff
- [ ] Dead letter queue (DLQ)

### Phase 4: Advanced Features
- [ ] Delivery status webhooks
- [ ] Read receipts
- [ ] Conversation management
- [ ] Advanced analytics

---

## 17. TESTING

### Test Files Location
```
/home/user/insta-messaging/tests/
├── conftest.py                    # Pytest fixtures
├── test_auth.py                   # Authentication tests
├── test_webhooks.py               # Webhook handling
├── test_webhook_forwarder.py       # CRM forwarding
├── test_message_repository.py      # Data layer
├── test_accounts_api.py            # Account management
└── test_tasks7_8.py                # Integration tests
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_webhooks.py
```

---

## 18. KEY FILES REFERENCE

| File | Purpose | Status |
|------|---------|--------|
| `main.py` | FastAPI app setup | ✅ Complete |
| `config.py` | Configuration management | ✅ Complete |
| `webhooks.py` | Instagram webhook receiver | ✅ Complete |
| `messages.py` | CRM message sending API | ✅ Complete |
| `accounts.py` | Account management API | ✅ Complete |
| `auth.py` | Authentication | 🚧 Stub |
| `instagram_client.py` | Instagram API integration | ✅ Complete |
| `message_repository.py` | Message storage layer | ✅ Complete |
| `webhook_forwarder.py` | CRM webhook forwarding | ✅ Complete |
| `reply_rules.py` | Auto-reply rules engine | ✅ Complete |
| `db/models.py` | SQLAlchemy models | ✅ Complete |
| `db/connection.py` | Database connection | ✅ Complete |

---

## Summary

This is a well-architected **FastAPI-based e-commerce automation platform** that:

1. ✅ **Receives** Instagram DMs via secure webhooks
2. ✅ **Processes** messages with auto-reply rules
3. ✅ **Forwards** to CRM systems via webhooks
4. ✅ **Sends** messages back to Instagram via API
5. ✅ **Stores** full conversation history
6. ✅ **Tracks** message delivery status
7. 🚧 **Secures** credentials (MVP: base64, needs encryption)
8. 🚧 **Authenticates** (MVP: stub, needs real API keys)

The codebase follows clean architecture principles with clear separation of concerns: API handlers → Services → Repositories → Database/External Services.
