# Account ID Field Guide

## Problem: Two Different ID Types

The application uses **two different types of IDs** to identify Instagram accounts, which can be confusing:

1. **Database Account ID** (`account_id`) - Internal ID for our database
2. **Instagram Account ID** (`instagram_account_id`) - Instagram's actual account ID

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
- Source: Instagram Graph API OAuth response

### Used For
- **Instagram API Calls**: Sending messages, fetching account info
- **Webhook Routing**: Identifying which account received a message
- **Conversation Filtering**: Matching messages to the correct account
- **Public Identification**: This is Instagram's official account identifier

### Where You'll See It
- `Account.instagram_account_id` (unique column in database)
- Webhook payloads: `recipient.id` or `sender.id`
- Messages table: `sender_id`, `recipient_id`
- Instagram Graph API responses
- Frontend conversation filters

### Example Usage
```python
# Webhook from Instagram
{
    "messaging": [{
        "sender": {"id": "1558635688632972"},      # Customer's Instagram ID
        "recipient": {"id": "24370771369265571"}   # ← Your business account ID
    }]
}
```

---

## When to Use Which ID

### Use `account_id` (Database ID) when:
- ✅ Making internal API calls (`/api/v1/messages/send`, `/api/v1/accounts/...`)
- ✅ Checking user permissions (`UserAccount` lookup)
- ✅ Storing references in database tables
- ✅ Passing IDs in JWT tokens
- ✅ Frontend form submissions

### Use `instagram_account_id` (Instagram ID) when:
- ✅ Calling Instagram Graph API
- ✅ Filtering messages/conversations by account
- ✅ Routing incoming webhooks to correct account
- ✅ Matching `recipient_id` in webhook payloads

---

## Common Patterns

### Pattern 1: API Endpoint Accepts Database ID, Uses Instagram ID Internally

```python
# Frontend sends database account_id
POST /api/v1/messages/send
{
    "account_id": "acc_89baed550ed9"  # Database ID
}

# Backend looks up Instagram ID
account = await db.get(Account, "acc_89baed550ed9")
instagram_client.send_message(
    account_id=account.instagram_account_id,  # Instagram ID
    recipient_id="1558635688632972",
    message_text="Hello"
)
```

### Pattern 2: Webhook Contains Instagram ID, Lookup Database ID

```python
# Webhook payload
webhook_data = {
    "recipient": {"id": "24370771369265571"}  # Instagram ID
}

# Look up database account
account = await db.execute(
    select(Account).where(
        Account.instagram_account_id == "24370771369265571"
    )
)
# Now have account.id = "acc_89baed550ed9" (database ID)
```

### Pattern 3: Frontend Conversation Filtering

```javascript
// Frontend filters conversations by Instagram ID
const filteredConversations = conversations.filter(conv =>
    conv.instagram_account_id === accountsStore.selectedAccount.instagram_account_id
)

// But when sending a reply, uses database ID
fetch('/api/v1/messages/send', {
    method: 'POST',
    body: JSON.stringify({
        account_id: accountsStore.selectedAccount.account_id,  // Database ID
        recipient_id: conv.sender_id,
        message_text: "Reply"
    })
})
```

---

## Field Mapping Reference

| Location | Field Name | ID Type | Example Value |
|----------|-----------|---------|---------------|
| `Account.id` | account_id | Database | `acc_89baed550ed9` |
| `Account.instagram_account_id` | instagram_account_id | Instagram | `24370771369265571` |
| `UserAccount.account_id` | account_id | Database | `acc_89baed550ed9` |
| `MessageModel.sender_id` | sender_id | Instagram | `1558635688632972` |
| `MessageModel.recipient_id` | recipient_id | Instagram | `24370771369265571` |
| JWT `primary_account_id` | account_id | Database | `acc_89baed550ed9` |
| Webhook `recipient.id` | - | Instagram | `24370771369265571` |
| API param `account_id` | account_id | Database | `acc_89baed550ed9` |
| Frontend `conversation.instagram_account_id` | instagram_account_id | Instagram | `24370771369265571` |
| Frontend `conversation.account_id` | account_id | Database | `acc_89baed550ed9` |

---

## Why Two IDs?

**Historical Context**: The original implementation used environment variables for a single account. When OAuth multi-account support was added, we needed:

1. **Internal database IDs** - To manage user-account relationships, permissions, and avoid conflicts
2. **Instagram's IDs** - To interact with Instagram's API and route webhooks correctly

**Design Decision**: Keep both IDs rather than using Instagram's ID as the primary key because:
- Instagram IDs are external (we don't control the format/changes)
- Database IDs can have meaningful prefixes (`acc_`, `usr_`, etc.)
- Clear separation between internal logic (database ID) and external API (Instagram ID)

---

## Troubleshooting

### Bug: "403 Permission Denied" when sending message
**Cause**: Frontend sent `instagram_account_id` instead of `account_id`
**Fix**: Use `account_id` (database ID) for all API endpoints

### Bug: Conversations not filtering correctly
**Cause**: Using `account_id` to filter messages instead of `instagram_account_id`
**Fix**: Use `instagram_account_id` to match against `recipient_id` in messages

### Bug: Webhook not routing to correct account
**Cause**: Looking up account by `account_id` instead of `instagram_account_id`
**Fix**: Look up `Account.instagram_account_id` to match webhook `recipient.id`

---

## Best Practices

1. **Name variables clearly**: Use `db_account_id` vs `instagram_account_id` when both are in scope
2. **Document API contracts**: Always specify which ID type each endpoint parameter expects
3. **Type hints**: Consider adding TypeScript for frontend to catch ID type mismatches
4. **Validation**: Add validation that `account_id` starts with `acc_` prefix
5. **Logging**: Log both IDs when debugging: `@{username} (DB: {account.id}, IG: {account.instagram_account_id})`

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

### Implementation Details

**Backend Storage** (`app/services/media_downloader.py`):
```python
# Generate attachment ID from message metadata
attachment_id = f"{message_id}_{attachment_index}"

# Store at: media/attachments/{attachment_id}.{ext}
local_path = self.base_dir / "attachments" / f"{attachment_id}{extension}"
```

**Backend Serving** (`app/main.py`):
```python
@app.get("/media/attachments/{attachment_id}")
async def serve_media(
    attachment_id: str,
    auth_context: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    # Look up attachment in database
    attachment = await db.get(MessageAttachment, attachment_id)

    # Verify user owns the message via account ownership
    message = await db.get(MessageModel, attachment.message_id)
    account = await get_account_by_recipient_id(message.recipient_id)
    verify_user_has_access(user_id, account.id)

    # Serve file
    return FileResponse(attachment.media_url_local)
```

**Frontend Extraction** (`useAuthenticatedMedia.js`):
```javascript
// Database stores: "media/attachments/mid_abc123_0.jpg"
// Extract attachment ID: "mid_abc123_0"
const attachmentId = mediaPath.match(/media\/attachments\/([^/.]+)/)[1]

// Request: /media/attachments/mid_abc123_0
const response = await fetch(`/media/attachments/${attachmentId}`)
```

### Access Control

Access is verified through the **message ownership chain**:
1. User owns account (via `UserAccount` table)
2. Account received the message (via `MessageModel.recipient_id` matching `Account.messaging_channel_id` or `Account.instagram_account_id`)
3. Message contains the attachment (via `MessageAttachment.message_id`)

This ensures users can only access media from conversations they own, without needing account IDs in the URL.

---

## Future Consideration

**Option to Simplify** (Breaking Change):
- Use `instagram_account_id` as primary key directly
- Remove `account_id` field entirely
- Would require migration and frontend updates
- Trade-off: Simpler model but less control over ID format

**Current Recommendation**: Keep both IDs. The clarity and control are worth the minor complexity.
