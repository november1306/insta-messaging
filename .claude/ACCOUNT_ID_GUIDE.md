# Account ID Field Guide

## Problem: Three Different ID Types

The application uses **three different types of IDs** to identify Instagram accounts, which can be confusing:

1. **Database Account ID** (`account_id`) - Internal ID for our database
2. **Instagram Account ID** (`instagram_account_id`) - Instagram's OAuth profile ID
3. **Messaging Channel ID** (`messaging_channel_id`) - Instagram's webhook routing ID

Understanding when to use which ID is critical for avoiding bugs.

---

## ID Type 1: Database Account ID (`account_id`)

### Format
- Prefix: `acc_`
- Example: `acc_89baed550ed9`, `acc_2d32237c32c7`
- Generated when: Account is first added to our database (during OAuth)

### Used For
- **Authentication & Permissions**: Verifying user access to accounts
- **API Endpoints**: All internal API calls use this ID
- **Database Relations**: Foreign keys in `user_accounts`, `crm_outbound_messages` tables
- **JWT Tokens**: Stored in session tokens as `primary_account_id`

### Where You'll See It
- `Account.id` (primary key in database)
- `UserAccount.account_id` (foreign key)
- JWT payload: `primary_account_id`
- API request parameters: `account_id`
- API response fields: `account_id`

### Example Usage
```python
# Sending a message via API
POST /api/v1/messages/send
{
    "account_id": "acc_89baed550ed9",  # ← Database ID
    "recipient_id": "1558635688632972",
    "message_text": "Hello"
}
```

---

## ID Type 2: Instagram Account ID (`instagram_account_id`)

### Format
- Numeric string (17-20 digits)
- Example: `24370771369265571`, `25021617690783377`
- Source: Instagram Graph API OAuth response (`/me` endpoint)

### Used For
- **Instagram API Calls**: Sending messages, fetching account info
- **OAuth Identification**: Links OAuth session to account
- **Fallback Routing**: When `messaging_channel_id` is not yet set

### Where You'll See It
- `Account.instagram_account_id` (unique column in database)
- OAuth token response: `user_id` field
- Instagram Graph API: Profile queries

### Key Insight
This ID comes from Instagram's **OAuth profile API** and identifies the business account. However, Instagram may use a **different ID** in webhook payloads for the same account (see `messaging_channel_id` below).

---

## ID Type 3: Messaging Channel ID (`messaging_channel_id`)

### Format
- Numeric string (17-20 digits)
- Example: `17841478096518771`
- Source: Webhook payload `recipient.id` field (for inbound messages)

### Used For
- **Webhook Routing**: Primary identifier for routing incoming messages
- **Message Filtering**: Matching messages to the correct account in UI
- **Conversation Grouping**: Consistent ID across all messages in a conversation

### Where You'll See It
- `Account.messaging_channel_id` (nullable column in database)
- Webhook payloads: `recipient.id` (inbound) or `sender.id` (outbound echoes)
- Messages table: `sender_id`, `recipient_id`
- Frontend conversation filters

### Key Insight
This ID is **often the same** as `instagram_account_id`, but can be **different** depending on Instagram's internal routing. The `messaging_channel_id`:
- Is `NULL` for newly linked accounts (no webhook received yet)
- Gets populated on first inbound webhook OR during conversation sync
- Should be used for all message filtering once available

### Example: When IDs Differ
```python
# OAuth gives us:
instagram_account_id = "24370771369265571"

# But webhook arrives with:
{
    "messaging": [{
        "recipient": {"id": "17841478096518771"}  # Different!
    }]
}

# So we store:
messaging_channel_id = "17841478096518771"
```

---

## The AccountIdentity Abstraction

To handle the complexity of three ID types, we use the `AccountIdentity` class (`app/domain/account_identity.py`).

### Purpose
`AccountIdentity` is a **frozen dataclass** that encapsulates all ID-related logic in one place:

```python
from app.domain.account_identity import AccountIdentity

# Create from Account model
identity = AccountIdentity.from_account(account)

# Get the effective channel ID (with fallback)
channel_id = identity.effective_channel_id

# Check if an ID belongs to this business account
if identity.is_business_id(sender_id):
    direction = "outbound"

# Detect message direction
direction = identity.detect_direction(sender_id)  # 'inbound' or 'outbound'

# Identify the customer in a message
customer_id = identity.identify_other_party(sender_id, recipient_id)
```

### Key Properties and Methods

| Property/Method | Description |
|----------------|-------------|
| `effective_channel_id` | Returns `messaging_channel_id` if set, otherwise `instagram_account_id` |
| `business_ids` | Set of all known business IDs for O(1) membership testing |
| `is_business_id(id)` | Returns `True` if the ID matches any business ID |
| `detect_direction(sender_id)` | Returns `'inbound'` or `'outbound'` |
| `identify_other_party(sender, recipient)` | Returns the customer's ID |
| `normalize_message_ids(sender, customer)` | Returns consistent (sender, recipient) tuple |

### Why This Matters
Before `AccountIdentity`, the codebase had scattered double comparisons:

```python
# OLD: Repeated in multiple files
if sender_id == messaging_channel_id or sender_id == account.instagram_account_id:
    direction = "outbound"
```

Now there's a single source of truth:

```python
# NEW: Clean, testable, consistent
if identity.is_business_id(sender_id):
    direction = "outbound"
```

---

## The `effective_channel_id` API Field

The `/api/v1/accounts/me` endpoint returns an `effective_channel_id` field that frontends should use for message filtering.

### API Response
```json
{
  "accounts": [{
    "account_id": "acc_89baed550ed9",
    "instagram_account_id": "24370771369265571",
    "messaging_channel_id": null,
    "effective_channel_id": "24370771369265571",
    "username": "myshop_official"
  }]
}
```

### Field Semantics

| Field | Value | Use Case |
|-------|-------|----------|
| `messaging_channel_id` | Actual webhook ID or `null` | Diagnostic/debugging |
| `effective_channel_id` | Always valid (with fallback) | **Use this for filtering** |

### Frontend Usage
```javascript
// Always use effective_channel_id for filtering
const filteredMessages = messages.filter(msg =>
    msg.recipient_id === account.effective_channel_id ||
    msg.sender_id === account.effective_channel_id
)
```

---

## When to Use Which ID

### Use `account_id` (Database ID) when:
- ✅ Making internal API calls (`/api/v1/messages/send`, `/api/v1/accounts/...`)
- ✅ Checking user permissions (`UserAccount` lookup)
- ✅ Storing references in database tables
- ✅ Passing IDs in JWT tokens
- ✅ Frontend form submissions

### Use `effective_channel_id` when:
- ✅ Filtering messages/conversations by account in UI
- ✅ Determining message direction
- ✅ Grouping conversations
- ✅ Any place you need "the ID that appears in messages"

### Use `instagram_account_id` when:
- ✅ Calling Instagram Graph API directly
- ✅ Looking up account by OAuth response
- ✅ Diagnostic logging

### Use `messaging_channel_id` when:
- ✅ Routing incoming webhooks (lookup by `recipient.id`)
- ✅ Checking if webhook binding has occurred
- ✅ Diagnostic purposes

---

## Common Patterns

### Pattern 1: Using AccountIdentity for Message Direction

```python
from app.domain.account_identity import AccountIdentity

# In webhook handler or sync service
identity = AccountIdentity.from_account(account)

# Determine direction
direction = identity.detect_direction(sender_id)

# Normalize IDs for storage
normalized_sender, normalized_recipient = identity.normalize_message_ids(
    sender_id, customer_id
)

# Create message with consistent IDs
message = MessageModel(
    sender_id=normalized_sender,
    recipient_id=normalized_recipient,
    direction=direction,
    ...
)
```

### Pattern 2: Webhook Routing with Fallback

```python
# Webhook arrives with recipient.id
webhook_recipient_id = payload["messaging"][0]["recipient"]["id"]

# Try messaging_channel_id first (exact match)
account = await db.execute(
    select(Account).where(
        Account.messaging_channel_id == webhook_recipient_id
    )
).scalar_one_or_none()

# Fallback to instagram_account_id (for newly linked accounts)
if not account:
    account = await db.execute(
        select(Account).where(
            Account.instagram_account_id == webhook_recipient_id
        )
    ).scalar_one_or_none()

    # Bind the messaging_channel_id for future routing
    if account:
        account.messaging_channel_id = webhook_recipient_id
```

### Pattern 3: Frontend Conversation Filtering

```javascript
// Get effective_channel_id from accounts API
const { effective_channel_id } = selectedAccount

// Filter conversations where this account is involved
const myConversations = conversations.filter(conv =>
    conv.recipient_id === effective_channel_id ||
    conv.sender_id === effective_channel_id
)

// When sending a reply, use database account_id
await fetch('/api/v1/messages/send', {
    method: 'POST',
    body: JSON.stringify({
        account_id: selectedAccount.account_id,  // Database ID for API
        recipient_id: conv.customer_id,
        message_text: "Reply"
    })
})
```

### Pattern 4: Syncing Messages with InstagramSyncService

```python
from app.application.instagram_sync_service import InstagramSyncService

# The sync service uses AccountIdentity internally
sync_service = InstagramSyncService(db, instagram_client)
result = await sync_service.sync_account(account, hours_back=24)

# Result includes statistics
print(f"Synced {result.messages_synced} new messages")
print(f"Skipped {result.messages_skipped} duplicates")
```

---

## Field Mapping Reference

| Location | Field Name | ID Type | Example Value |
|----------|-----------|---------|---------------|
| `Account.id` | account_id | Database | `acc_89baed550ed9` |
| `Account.instagram_account_id` | instagram_account_id | Instagram OAuth | `24370771369265571` |
| `Account.messaging_channel_id` | messaging_channel_id | Webhook Channel | `17841478096518771` |
| `UserAccount.account_id` | account_id | Database | `acc_89baed550ed9` |
| `MessageModel.sender_id` | sender_id | Instagram (effective) | `17841478096518771` |
| `MessageModel.recipient_id` | recipient_id | Instagram (effective) | `17841478096518771` |
| JWT `primary_account_id` | account_id | Database | `acc_89baed550ed9` |
| Webhook `recipient.id` | - | Messaging Channel | `17841478096518771` |
| API param `account_id` | account_id | Database | `acc_89baed550ed9` |
| API response `effective_channel_id` | effective_channel_id | Instagram (with fallback) | `17841478096518771` |
| `AccountIdentity.effective_channel_id` | - | Instagram (with fallback) | `17841478096518771` |

---

## Why Three IDs?

### Historical Context
Instagram's API uses different IDs in different contexts:
- **OAuth API** returns one ID (`instagram_account_id`)
- **Webhooks** may use a different ID (`messaging_channel_id`)

This appears to be an artifact of Instagram's internal architecture, where messaging channels can have different identifiers than account profiles.

### Design Decision
We store both IDs and provide `effective_channel_id` as the resolution:

1. **`instagram_account_id`** - Always populated (from OAuth), used for API calls
2. **`messaging_channel_id`** - Populated by webhooks/sync, used for routing
3. **`effective_channel_id`** - Computed: `messaging_channel_id || instagram_account_id`

The `AccountIdentity` class encapsulates this logic so application code doesn't need to handle fallbacks manually.

---

## Troubleshooting

### Bug: "403 Permission Denied" when sending message
**Cause**: Frontend sent `instagram_account_id` instead of `account_id`
**Fix**: Use `account_id` (database ID) for all API endpoints

### Bug: Conversations not filtering correctly
**Cause**: Using `account_id` or raw `instagram_account_id` to filter messages
**Fix**: Use `effective_channel_id` from the accounts API response

### Bug: Webhook not routing to correct account
**Cause**: Only checking `instagram_account_id`, not `messaging_channel_id`
**Fix**: Check `messaging_channel_id` first, then fall back to `instagram_account_id`

### Bug: Messages have inconsistent sender/recipient IDs
**Cause**: Not normalizing IDs before storage
**Fix**: Use `AccountIdentity.normalize_message_ids()` to ensure consistent IDs

### Bug: New account shows no messages after OAuth
**Cause**: `messaging_channel_id` is NULL, frontend filtering by wrong ID
**Fix**: Use `effective_channel_id` which provides the fallback automatically

---

## Best Practices

1. **Use AccountIdentity**: Always use `AccountIdentity.from_account()` for ID-related logic
2. **Use effective_channel_id**: Frontend should always filter by `effective_channel_id`
3. **Name variables clearly**: Use `db_account_id` vs `instagram_id` when both are in scope
4. **Validate prefixes**: Add validation that `account_id` starts with `acc_` prefix
5. **Logging**: Log all three IDs when debugging:
   ```python
   logger.info(f"@{account.username} (DB: {account.id}, IG: {account.instagram_account_id}, Channel: {account.messaging_channel_id})")
   ```
6. **Don't assume equality**: Never assume `instagram_account_id == messaging_channel_id`

---

## Architecture: Key Files

| File | Responsibility |
|------|----------------|
| `app/domain/account_identity.py` | `AccountIdentity` class - ID resolution logic |
| `app/application/instagram_sync_service.py` | Message sync using `AccountIdentity` |
| `app/api/accounts.py` | API returns `effective_channel_id` |
| `app/api/webhooks.py` | Webhook routing with channel ID binding |

---

## Media Storage: Message-Based Paths (Not Account-Based)

### The Problem with Account-Based Paths

Initially, media files were stored using account-based paths:
```
media/{account_id}/{sender_id}/{message_id}_{index}.ext
```

This created ambiguity because:
- Which `account_id` to use? Database ID (`acc_xxx`) or Instagram ID?
- `messaging_channel_id` ≠ `instagram_account_id` in some cases
- Path relied on external account identifiers that could change

### Current Solution: Attachment-Based Paths

Media files are now stored using **message attachment IDs** only:
```
media/attachments/{attachment_id}.{ext}
```

Where `attachment_id` = `{message_id}_{attachment_index}`

**Example:**
- Message ID: `mid_abc123`
- First attachment: `mid_abc123_0.jpg`
- Second attachment: `mid_abc123_1.mp4`

### Benefits

1. **No Account ID Ambiguity**: Path doesn't depend on which account ID to use
2. **Globally Unique**: Message IDs from Instagram are globally unique
3. **Simple Lookup**: Backend looks up attachment by ID, verifies ownership via message → account relationship
4. **Clean URLs**: Frontend uses `/media/attachments/mid_abc123_0` (no need to know account/sender)

---

## Future Consideration

**Option to Simplify** (Breaking Change):
- Use `instagram_account_id` as primary key directly
- Remove `account_id` field entirely
- Would require migration and frontend updates
- Trade-off: Simpler model but less control over ID format

**Current Recommendation**: Keep both IDs. The `AccountIdentity` abstraction makes the complexity manageable while providing flexibility.
