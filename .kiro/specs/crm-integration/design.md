# Design Document

## Overview

The CRM Integration feature implements a webhook-first, bidirectional communication bridge between the Instagram Messenger Automation service (message router) and a custom e-commerce CRM system. The architecture follows industry-standard patterns used by Twilio, Stripe, and SendGrid: the CRM calls REST APIs to send messages, and receives webhooks for inbound messages and status updates. This design ensures loose coupling, independent scalability, and clear separation of concerns.

### Key Design Principles

- **Webhook-First Architecture**: Async event delivery for real-time updates without polling
- **Idempotent Operations**: Prevent duplicate messages with idempotency keys
- **Retry with Backoff**: Exponential backoff for transient failures
- **Fail-Safe Design**: Always acknowledge Instagram webhooks, queue CRM delivery
- **Data Sovereignty**: Each system owns its domain data
- **API-First**: OpenAPI/Swagger for contract-first development
- **Security by Default**: HMAC signatures, API key authentication, encrypted credentials

### Architecture Pattern

```
┌─────────────┐         ┌──────────────────┐         ┌─────────┐
│  Instagram  │────────>│  Message Router  │────────>│   CRM   │
│   (Meta)    │ webhook │   (Your App)     │ webhook │ System  │
└─────────────┘         └──────────────────┘         └─────────┘
                               │                          │
                               │                          │
                        [Router Database]          [CRM Database]
                        - Delivery status          - Customer data
                        - Retry queue              - Conversation history
                        - Instagram metadata       - Business context
```

### Data Flow

**Outbound (CRM → Customer):**
1. CRM calls POST /api/v1/messages/send
2. Message Router validates and returns 202 Accepted with message_id
3. Message Router sends to Instagram API
4. Message Router sends delivery status webhook to CRM

**Inbound (Customer → CRM):**
1. Instagram sends webhook to Message Router
2. Message Router stores delivery metadata
3. Message Router forwards webhook to CRM
4. CRM stores message with customer context

## Architecture

### System Components

```
Message Router Service
├── API Layer (FastAPI)
│   ├── /api/v1/messages/send          (Outbound messages)
│   ├── /api/v1/messages/{id}/status   (Status queries)
│   ├── /api/v1/accounts               (Account management)
│   └── /docs                          (Swagger UI)
│
├── Webhook Delivery Service
│   ├── CRM Webhook Sender
│   ├── Retry Queue Manager
│   └── Dead Letter Queue Handler
│
├── Instagram Integration
│   ├── Webhook Receiver (existing)
│   └── Send API Client (existing)
│
├── Storage Layer
│   ├── Message Delivery Tracking
│   ├── Webhook Retry Queue
│   └── Account Configuration
│
└── Security Layer
    ├── API Key Authentication
    ├── Webhook Signature Generation
    └── Credential Encryption
```

### Component Interactions

```mermaid
sequenceDiagram
    participant CRM
    participant Router
    participant Instagram
    
    Note over CRM,Instagram: Outbound Message Flow
    CRM->>Router: POST /api/v1/messages/send
    Router->>Router: Validate & Store
    Router-->>CRM: 202 Accepted {message_id}
    Router->>Instagram: Send API
    Instagram-->>Router: Success/Failure
    Router->>CRM: Webhook: message.delivered
    
    Note over CRM,Instagram: Inbound Message Flow
    Instagram->>Router: Webhook: New Message
    Router->>Router: Store Metadata
    Router->>CRM: Webhook: message.received
    CRM-->>Router: 200 OK
```

## Components and Interfaces

### 1. Outbound Message API

**Endpoint:** `POST /api/v1/messages/send`

**Request Schema:**
```python
class SendMessageRequest(BaseModel):
    account_id: str = Field(..., description="Instagram account ID")
    recipient_id: str = Field(..., description="Instagram PSID of recipient")
    message: str = Field(..., min_length=1, max_length=1000)
    idempotency_key: str = Field(..., description="Unique key to prevent duplicates")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="CRM-specific metadata")

class SendMessageResponse(BaseModel):
    message_id: str = Field(..., description="Message Router's message ID")
    status: str = Field(..., description="pending | accepted | failed")
    instagram_message_id: Optional[str] = Field(default=None)
    created_at: datetime
```

**Implementation:**
```python
@router.post("/api/v1/messages/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    api_key: str = Depends(verify_api_key),
    message_service: IMessageService = Depends(get_message_service)
):
    # 1. Check idempotency - return existing if duplicate
    existing = await message_service.get_by_idempotency_key(
        request.idempotency_key
    )
    if existing:
        return existing
    
    # 2. Validate account access
    account = await message_service.get_account(request.account_id)
    if not account or not api_key.has_access(account.id):
        raise HTTPException(status_code=403)
    
    # 3. Create message record
    message = await message_service.create_outbound_message(
        account_id=request.account_id,
        recipient_id=request.recipient_id,
        text=request.message,
        idempotency_key=request.idempotency_key,
        metadata=request.metadata
    )
    
    # 4. Queue for Instagram delivery (async)
    await message_service.queue_for_delivery(message.id)
    
    # 5. Return immediately
    return SendMessageResponse(
        message_id=message.id,
        status="pending",
        created_at=message.created_at
    )
```

**Error Responses:**
- 400 Bad Request: Invalid payload
- 401 Unauthorized: Missing/invalid API key
- 403 Forbidden: No access to account
- 429 Too Many Requests: Rate limit exceeded

### 2. Message Status Query API

**Endpoint:** `GET /api/v1/messages/{message_id}/status`

**Response Schema:**
```python
class MessageStatusResponse(BaseModel):
    message_id: str
    status: str = Field(..., description="pending | sent | delivered | read | failed")
    account_id: str
    recipient_id: str
    instagram_message_id: Optional[str]
    status_history: List[StatusTransition]
    error: Optional[ErrorDetail]
    created_at: datetime
    updated_at: datetime

class StatusTransition(BaseModel):
    status: str
    timestamp: datetime
    
class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool
```

**Implementation:**
```python
@router.get("/api/v1/messages/{message_id}/status")
async def get_message_status(
    message_id: str,
    api_key: str = Depends(verify_api_key),
    message_service: IMessageService = Depends(get_message_service)
):
    message = await message_service.get_message_with_status(message_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if not api_key.has_access(message.account_id):
        raise HTTPException(status_code=403)
    
    return MessageStatusResponse.from_message(message)
```

### 3. Inbound Message Webhook

**Webhook Event:** `message.received`

**Payload Schema:**
```python
class InboundMessageWebhook(BaseModel):
    event: str = "message.received"
    message_id: str = Field(..., description="Message Router's message ID")
    account_id: str
    sender_id: str = Field(..., description="Instagram PSID")
    sender_username: Optional[str]
    message: str
    message_type: str = Field(default="text", description="text | image | video | story_reply")
    timestamp: datetime
    instagram_message_id: str
    conversation_id: str
```

**Signature Header:**
```
X-Hub-Signature-256: sha256=<hmac_hex_digest>
```

**CRM Implementation Example:**
```python
@app.post("/webhooks/instagram/messages")
async def receive_message_webhook(
    request: Request,
    signature: str = Header(..., alias="X-Hub-Signature-256")
):
    # 1. Validate signature
    body = await request.body()
    if not validate_signature(body, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401)
    
    # 2. Parse payload
    payload = InboundMessageWebhook.parse_raw(body)
    
    # 3. Store in CRM database with customer context
    await crm_service.store_customer_message(
        customer_id=await crm_service.get_customer_by_instagram_id(
            payload.sender_id
        ),
        message=payload.message,
        timestamp=payload.timestamp,
        external_message_id=payload.message_id
    )
    
    # 4. Acknowledge immediately
    return {"status": "received"}
```

### 4. Delivery Status Webhook

**Webhook Events:**
- `message.sent`: Successfully sent to Instagram API
- `message.delivered`: Instagram confirmed delivery
- `message.read`: Customer read the message
- `message.failed`: Permanent delivery failure

**Payload Schema:**
```python
class DeliveryStatusWebhook(BaseModel):
    event: str = Field(..., description="message.sent | message.delivered | message.read | message.failed")
    message_id: str = Field(..., description="Original message_id from send request")
    account_id: str
    recipient_id: str
    status: str
    timestamp: datetime
    instagram_message_id: Optional[str]
    error: Optional[ErrorDetail]
```

**Message Router Implementation:**
```python
class WebhookDeliveryService:
    async def send_status_webhook(
        self,
        account: Account,
        message: Message,
        event: str
    ):
        payload = DeliveryStatusWebhook(
            event=event,
            message_id=message.id,
            account_id=message.account_id,
            recipient_id=message.recipient_id,
            status=message.status,
            timestamp=datetime.utcnow(),
            instagram_message_id=message.instagram_message_id,
            error=message.error
        )
        
        # Generate signature
        body = payload.json()
        signature = self._generate_signature(body, account.webhook_secret)
        
        # Send with retry
        await self._send_with_retry(
            url=account.crm_webhook_url,
            body=body,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "Content-Type": "application/json"
            },
            max_retries=5
        )
```

### 5. Account Configuration API

**Endpoints:**

**Create Account:** `POST /api/v1/accounts`
```python
class CreateAccountRequest(BaseModel):
    instagram_account_id: str
    username: str
    access_token: str = Field(..., description="Instagram Page Access Token")
    app_secret: str = Field(..., description="Facebook App Secret")
    crm_webhook_url: str = Field(..., description="CRM endpoint for webhooks")
    webhook_secret: str = Field(..., description="Shared secret for webhook signatures")

class AccountResponse(BaseModel):
    account_id: str
    username: str
    status: str = Field(..., description="active | inactive | error")
    crm_webhook_url: str
    created_at: datetime
    # Note: access_token and secrets are never returned
```

**Get Account:** `GET /api/v1/accounts/{account_id}`

**Update Account:** `PUT /api/v1/accounts/{account_id}`
```python
class UpdateAccountRequest(BaseModel):
    crm_webhook_url: Optional[str]
    webhook_secret: Optional[str]
    access_token: Optional[str]
    status: Optional[str]
```

**Implementation:**
```python
@router.post("/api/v1/accounts", response_model=AccountResponse)
async def create_account(
    request: CreateAccountRequest,
    api_key: str = Depends(verify_admin_api_key),
    account_service: IAccountService = Depends(get_account_service)
):
    # 1. Validate Instagram access token
    instagram_client = InstagramClient(request.access_token)
    is_valid = await instagram_client.validate_token()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid Instagram access token"
        )
    
    # 2. Encrypt credentials
    encrypted_token = encrypt(request.access_token, settings.encryption_key)
    encrypted_secret = encrypt(request.app_secret, settings.encryption_key)
    
    # 3. Create account
    account = await account_service.create(
        instagram_account_id=request.instagram_account_id,
        username=request.username,
        access_token_encrypted=encrypted_token,
        app_secret_encrypted=encrypted_secret,
        crm_webhook_url=request.crm_webhook_url,
        webhook_secret=request.webhook_secret
    )
    
    return AccountResponse.from_account(account)
```

### 6. Webhook Retry Service

**Responsibilities:**
- Retry failed webhook deliveries with exponential backoff
- Move to dead letter queue after exhausting retries
- Provide admin API for manual retry

**Retry Strategy:**
```python
class WebhookRetryService:
    RETRY_DELAYS = [1, 2, 4, 8, 16]  # seconds
    MAX_RETRIES = 5
    DLQ_AFTER_HOURS = 24
    
    async def send_with_retry(
        self,
        webhook: WebhookDelivery
    ):
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self._send_webhook(webhook)
                
                if response.status_code in [200, 201, 202, 204]:
                    await self._mark_delivered(webhook)
                    return
                
                if response.status_code in [401, 403]:
                    # Auth error - don't retry
                    await self._mark_failed(webhook, "auth_error")
                    return
                
                # Retryable error
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAYS[attempt])
                    continue
                
            except (httpx.ConnectError, httpx.TimeoutException):
                # Network error - retry
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAYS[attempt])
                    continue
        
        # All retries exhausted
        await self._queue_for_extended_retry(webhook)
    
    async def _queue_for_extended_retry(self, webhook: WebhookDelivery):
        """Continue retrying for 24 hours, then move to DLQ"""
        webhook.extended_retry_until = datetime.utcnow() + timedelta(hours=24)
        await self.retry_queue.add(webhook)
```

**Dead Letter Queue API:**
```python
@router.get("/api/v1/admin/dlq/webhooks")
async def list_failed_webhooks(
    api_key: str = Depends(verify_admin_api_key),
    dlq_service: IDLQService = Depends(get_dlq_service)
):
    return await dlq_service.list_failed_webhooks(limit=100)

@router.post("/api/v1/admin/dlq/webhooks/{webhook_id}/retry")
async def retry_failed_webhook(
    webhook_id: str,
    api_key: str = Depends(verify_admin_api_key),
    dlq_service: IDLQService = Depends(get_dlq_service)
):
    await dlq_service.retry_webhook(webhook_id)
    return {"status": "queued"}
```

### 7. API Authentication

**API Key Format:**
```
Authorization: Bearer router_live_abc123def456...
```

**API Key Types:**
- `router_live_*`: Production keys
- `router_test_*`: Test/sandbox keys

**Implementation:**
```python
class APIKey(BaseModel):
    id: str
    key_hash: str  # bcrypt hash
    account_ids: List[str]  # Accounts this key can access
    permissions: List[str]  # ["messages:send", "messages:read", "accounts:read"]
    is_admin: bool = False
    created_at: datetime
    last_used_at: Optional[datetime]

async def verify_api_key(
    authorization: str = Header(..., alias="Authorization")
) -> APIKey:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    
    key = authorization[7:]  # Remove "Bearer "
    
    # Hash and lookup
    key_hash = bcrypt.hashpw(key.encode(), bcrypt.gensalt())
    api_key = await api_key_service.get_by_hash(key_hash)
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Update last used
    await api_key_service.update_last_used(api_key.id)
    
    return api_key
```

### 8. Webhook Signature Validation

**Signature Generation (Message Router):**
```python
def generate_webhook_signature(
    payload: str,
    secret: str
) -> str:
    """Generate HMAC-SHA256 signature"""
    signature = hmac.new(
        key=secret.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"
```

**Signature Validation (CRM):**
```python
def validate_webhook_signature(
    payload: str,
    signature: str,
    secret: str
) -> bool:
    """Validate webhook signature using constant-time comparison"""
    expected = generate_webhook_signature(payload, secret)
    
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected)
```

## Data Models

### Message Router Database Schema

**outbound_messages table:**
```sql
CREATE TABLE outbound_messages (
    id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    recipient_id VARCHAR(50) NOT NULL,
    message_text TEXT NOT NULL,
    idempotency_key VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, sent, delivered, read, failed
    instagram_message_id VARCHAR(100),
    retry_count INT DEFAULT 0,
    metadata JSON,
    error_code VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    INDEX idx_account_status (account_id, status),
    INDEX idx_idempotency (idempotency_key),
    INDEX idx_created_at (created_at)
);
```

**webhook_deliveries table:**
```sql
CREATE TABLE webhook_deliveries (
    id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    webhook_type VARCHAR(50) NOT NULL,  -- message.received, message.delivered, etc.
    payload JSON NOT NULL,
    target_url VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, delivered, failed, dlq
    retry_count INT DEFAULT 0,
    last_attempt_at TIMESTAMP,
    next_retry_at TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    INDEX idx_status_next_retry (status, next_retry_at),
    INDEX idx_account_created (account_id, created_at)
);
```

**accounts table (updated):**
```sql
CREATE TABLE accounts (
    id VARCHAR(50) PRIMARY KEY,
    instagram_account_id VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    app_secret_encrypted TEXT NOT NULL,
    crm_webhook_url VARCHAR(500) NOT NULL,
    webhook_secret VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**api_keys table:**
```sql
CREATE TABLE api_keys (
    id VARCHAR(50) PRIMARY KEY,
    key_hash VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200),
    account_ids JSON,  -- Array of account IDs
    permissions JSON,  -- Array of permission strings
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

### CRM Database Schema (Example)

**customer_messages table:**
```sql
CREATE TABLE customer_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    conversation_id INT NOT NULL,
    direction ENUM('inbound', 'outbound') NOT NULL,
    message_text TEXT NOT NULL,
    channel VARCHAR(20) DEFAULT 'instagram',
    external_message_id VARCHAR(50),  -- Message Router's message_id
    instagram_message_id VARCHAR(100),
    status VARCHAR(20),
    sent_by_user_id INT,  -- CRM user who sent (if outbound)
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    INDEX idx_customer_timestamp (customer_id, timestamp),
    INDEX idx_external_id (external_message_id)
);
```

## Error Handling

### Error Categories

**1. Client Errors (4xx):**
- 400 Bad Request: Invalid payload, validation errors
- 401 Unauthorized: Missing/invalid API key
- 403 Forbidden: No access to resource
- 404 Not Found: Resource doesn't exist
- 429 Too Many Requests: Rate limit exceeded

**2. Server Errors (5xx):**
- 500 Internal Server Error: Unexpected error
- 502 Bad Gateway: Instagram API unavailable
- 503 Service Unavailable: System overloaded

**3. Instagram API Errors:**
- Rate limit (code 4): Queue and retry after window
- Invalid token (code 190): Alert admin, disable account
- User unavailable (code 10): Mark as failed, don't retry
- Temporary error (code 2): Retry with backoff

### Error Response Format

```python
class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable message")
    details: Optional[Dict[str, Any]] = None
    correlation_id: str = Field(..., description="For support/debugging")
    timestamp: datetime
```

**Example:**
```json
{
  "error": "invalid_recipient",
  "message": "The recipient ID is not valid or the user has blocked the page",
  "details": {
    "recipient_id": "123456789",
    "instagram_error_code": 10
  },
  "correlation_id": "req_abc123def456",
  "timestamp": "2025-11-06T10:30:00Z"
}
```

## Testing Strategy

### 1. API Contract Testing

**OpenAPI Schema Validation:**
- Generate test cases from OpenAPI spec
- Validate all request/response schemas
- Test error responses match spec

**Tools:**
- Schemathesis for property-based testing
- Postman collections for manual testing

### 2. Webhook Testing

**Signature Validation:**
- Test valid signatures accepted
- Test invalid signatures rejected
- Test timing attack resistance

**Retry Logic:**
- Test exponential backoff timing
- Test DLQ after max retries
- Test manual retry from DLQ

### 3. Integration Testing

**End-to-End Flows:**
- Send message via API → Verify Instagram API called
- Receive Instagram webhook → Verify CRM webhook sent
- Test idempotency with duplicate requests
- Test webhook retry on CRM failure

**Test Environment:**
- Use Instagram test users
- Mock CRM webhook endpoint
- Separate test database

### 4. Load Testing

**Scenarios:**
- 100 concurrent message sends
- 1000 webhooks/minute from Instagram
- CRM webhook endpoint slow/unavailable

**Metrics:**
- API response time < 200ms (p95)
- Webhook delivery latency < 2s (p95)
- Message throughput > 100/second

## Deployment

### Configuration

**Environment Variables:**
```bash
# Database
DATABASE_URL=mysql://user:pass@host:3306/db

# Security
ENCRYPTION_KEY=base64_encoded_key_32_bytes
API_KEY_SALT=random_salt_for_hashing

# Instagram (for webhook validation)
INSTAGRAM_APP_ID=your_app_id

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=https://...
```

### OpenAPI/Swagger Setup

**FastAPI Configuration:**
```python
app = FastAPI(
    title="Instagram Message Router API",
    description="CRM integration API for Instagram messaging",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add security scheme
app.openapi_schema = {
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "API Key"
            }
        }
    },
    "security": [{"ApiKeyAuth": []}]
}
```

**Swagger UI Customization:**
```python
from fastapi.openapi.docs import get_swagger_ui_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True
        }
    )
```

### Monitoring

**Metrics to Track:**
- API request rate and latency
- Message send success/failure rate
- Webhook delivery success/failure rate
- Retry queue depth
- DLQ size

**Alerting:**
- DLQ size > 100
- Webhook delivery failure rate > 5%
- API error rate > 1%
- Instagram API errors

### Scaling Considerations

**Horizontal Scaling:**
- Stateless API servers behind load balancer
- Shared database for state
- Distributed retry queue (Redis/RabbitMQ)

**Vertical Scaling:**
- Database connection pooling
- Async I/O for webhook delivery
- Background workers for retry processing

**Rate Limiting:**
- Per-account rate limits
- Global rate limits
- Instagram API rate limit tracking

## Security Considerations

### 1. Credential Protection

- Encrypt Instagram access tokens at rest
- Never log or expose credentials in responses
- Rotate webhook secrets regularly
- Use environment variables for encryption keys

### 2. API Security

- Require API key for all endpoints
- Use HTTPS only (enforce in production)
- Implement rate limiting per API key
- Log all authentication failures

### 3. Webhook Security

- Validate signatures on all webhooks
- Use constant-time comparison
- Reject webhooks with invalid signatures
- Don't retry on 401 responses (auth errors)

### 4. Data Privacy

- Never log message content
- Minimize PII in logs
- Implement data retention policies
- Support GDPR deletion requests

## Migration Path

### Phase 1: MVP (Single Account)
- Implement core APIs (send, status, webhooks)
- Single Instagram account configuration
- Basic retry logic
- Swagger documentation

### Phase 2: Multi-Account
- Account management API
- Per-account webhook configuration
- Account-scoped API keys
- Account isolation

### Phase 3: Production Hardening
- Advanced retry with circuit breakers
- Dead letter queue with admin UI
- Comprehensive monitoring
- Load testing and optimization

### Phase 4: Advanced Features
- Message templates
- Rich media support (images, buttons)
- Webhook event filtering
- Analytics and reporting API
