# Production Environment Fixes

## Issues Identified from Screenshot

### ❌ Issue 1: Business Account Appearing in Contacts List
**Symptom**: Business account `178414057288323526` appears in the conversations list

**Cause**: One of two problems:
1. `.env` file has wrong `INSTAGRAM_BUSINESS_ACCOUNT_ID`
2. Database contains inbound messages FROM the business account (self-messages)

**Fix**:

```bash
# Step 1: Update .env in production
echo "INSTAGRAM_BUSINESS_ACCOUNT_ID=178414057288323526" >> .env

# Step 2: Remove any self-messages from database
# Connect to your production database and run:
DELETE FROM messages
WHERE direction = 'inbound'
AND sender_id = '178414057288323526';

# Step 3: Restart your application server
# (Method depends on your deployment - Docker, systemd, etc.)
```

### ❌ Issue 2: Missing Response Window Badges
**Symptom**: No "Xh left" badges showing in conversation list

**Cause**: Backend not returning `hours_remaining` field in API response

**Verify**:
```bash
# Check what the API is actually returning:
curl -H 'Authorization: Bearer YOUR_API_KEY' \
     https://your-domain.com/api/v1/ui/conversations | jq '.conversations[0]'

# Should include: "hours_remaining": 20
```

**Fix**:
1. Ensure you're running the latest code (commit `abdb2cf` or later)
2. Check backend logs for errors in `/api/v1/ui/conversations` endpoint
3. Verify all messages have `timestamp` field populated in database:

```sql
SELECT id, sender_id, timestamp
FROM messages
WHERE timestamp IS NULL;

-- If any rows returned, those messages need timestamps
UPDATE messages
SET timestamp = created_at
WHERE timestamp IS NULL;
```

### ❌ Issue 3: User IDs Instead of @usernames
**Symptom**: Showing `178414057288323526` instead of `@username`

**Cause**: Expected behavior when Instagram API credentials are not configured

**Fix** (Optional):
Add to `.env`:
```bash
INSTAGRAM_PAGE_ACCESS_TOKEN=your_instagram_access_token
```

Without this, usernames will fallback to user IDs (which is fine for testing).

## Deployment Checklist

After making changes:

- [ ] Update `.env` with correct `INSTAGRAM_BUSINESS_ACCOUNT_ID=178414057288323526`
- [ ] Clean database of self-messages (business account in contacts)
- [ ] Verify all messages have timestamps
- [ ] Deploy latest code (commit `abdb2cf` or later)
- [ ] Restart application server
- [ ] Test API response includes `hours_remaining` field
- [ ] Verify business account no longer in contacts list
- [ ] Verify response window badges appear

## Test API Response

Use this command to verify the fix:

```bash
# Get API key from your deployment
API_KEY="your_api_key_here"

# Test conversations endpoint
curl -s -H "Authorization: Bearer $API_KEY" \
     https://your-domain.com/api/v1/ui/conversations | \
     python3 -m json.tool

# Expected output:
{
  "conversations": [
    {
      "sender_id": "1558635688632972",
      "sender_name": "1558635688632972",  # or @username if API configured
      "last_message": "Do order66",
      "last_message_time": "2025-11-28T...",
      "unread_count": 0,
      "instagram_account_id": "178414057288323526",
      "hours_remaining": 17,   # ← THIS FIELD MUST BE PRESENT
      "can_respond": true
    }
  ]
}
```

## Quick Database Check Script

Run this in production to diagnose issues:

```bash
# Check for self-messages
sqlite3 your_database.db << EOF
SELECT COUNT(*) as self_messages
FROM messages
WHERE direction = 'inbound'
AND sender_id = recipient_id;
EOF

# Check for messages without timestamps
sqlite3 your_database.db << EOF
SELECT COUNT(*) as messages_without_timestamp
FROM messages
WHERE timestamp IS NULL;
EOF

# Show recent conversations
sqlite3 your_database.db << EOF
SELECT sender_id, recipient_id, direction, message_text, timestamp
FROM messages
WHERE direction = 'inbound'
ORDER BY timestamp DESC
LIMIT 5;
EOF
```

## Expected Result After Fixes

After applying all fixes, the UI should show:

✅ Business account `178414057288323526` at top (NOT in contacts list)
✅ Conversations list shows ONLY other users
✅ Each conversation has colored badge: `20h left` (green), `5h left` (orange), etc.
✅ Response window indicator in details panel
✅ Both inbound and outbound messages in threads

## Support

If issues persist after applying these fixes:
1. Check backend logs for API errors
2. Verify `.env` is being loaded correctly
3. Confirm you're running the latest code version
4. Check database schema matches expectations
