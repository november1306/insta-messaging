# Issues to Fix

Found during smoke testing on 2026-01-19.
**Last Updated:** 2026-01-20

---

## High Priority

### 1. ~~Webhook AccountId Format Error~~ ✅ FIXED
**Error:** `ValueError: Invalid AccountId format: channel:17841401592276765. Must start with 'acc_' prefix.`

**Location:** `app/domain/value_objects.py:39`

**Impact:** Inbound Instagram messages may not be processed correctly.

**Root Cause:** `AccountNotFoundError` expected an `AccountId` object, but when no account was found during webhook processing, the code tried to create an invalid `AccountId` with a `channel:` prefix.

**Fix Applied (2026-01-20):**
1. Modified `AccountNotFoundError` in `app/domain/entities.py` to accept either `AccountId` or `str`
2. Updated `app/application/message_service.py:207` to pass string identifier instead of invalid `AccountId`

**Files Changed:**
- `app/domain/entities.py` - Updated `AccountNotFoundError.__init__` signature
- `app/application/message_service.py` - Use string identifier for error

---

## Medium Priority

### 2. ~~Skipped Webhook Messages~~ ✅ RESOLVED
**Log:** `ℹ️ Skipped event type: message (failed extraction) (channel_id: 17841478096518771)`

**Impact:** Some inbound messages are not being saved to the database.

**Root Cause:** This was a cascading issue from Issue #1 - message extraction failed when account lookup failed.

**Status:** Resolved with Issue #1 fix. The "skipped" log now only appears for:
- Delivery receipts (expected - not user messages)
- Read receipts (expected - not user messages)
- Echo messages (expected - messages we sent)
- Messages missing required fields (rare edge case)

---

## Low Priority

### 3. Missing Media Files (404) - Enhancement Needed
**Error:** `Failed to fetch media from /media/outbound/acc_1512d498c86f/...`

**Impact:** Some old outbound media attachments return 404.

**Root Cause:** Media files were either deleted, cleaned up by `media_cleanup.py` (24-hour expiration), or not properly saved to disk.

**Current Behavior:**
- Frontend shows animated placeholder indefinitely when media fails to load
- No visual error state for users
- Video/audio elements have no error handlers
- Image elements have `@error` handler but only log to console

**Recommendations for Future Enhancement:**
1. Add visual error placeholder in `MessageBubble.vue` (e.g., "Media unavailable" icon)
2. Add `@error` handlers to `<video>` and `<audio>` elements
3. Consider retry mechanism for transient network errors
4. Track media load state (loading/loaded/failed) for better UX

**Files to Modify (if implementing):**
- `frontend/src/components/MessageBubble.vue`
- `frontend/src/composables/useAuthenticatedMedia.js`

---

### 4. Instagram User Consent Error - Working As Intended
**Error:** `HTTP/1.1 500 Internal Server Error - User consent is required to access user profile`

**Impact:** Cannot fetch profile info for some users (shows numeric ID instead of username).

**Root Cause:** Instagram API limitation - requires implicit user consent through sufficient interaction before allowing profile access.

**Current Behavior (Correct):**
- `instagram_client.py:get_user_profile()` returns `None` on failure (line 106-117)
- `webhooks.py` catches exception and uses numeric ID as fallback (line 468-469)
- Profile is cached when successfully fetched (`InstagramProfile` table)
- Error is logged as warning, not error

**Status:** ✅ Working as intended. Users see numeric IDs when profiles aren't accessible - this is expected behavior for Instagram's API privacy restrictions.

---

## Completed Issues

| Issue | Status | Fix Date |
|-------|--------|----------|
| #1 Webhook AccountId Format Error | ✅ Fixed | 2026-01-20 |
| #2 Skipped Webhook Messages | ✅ Resolved | 2026-01-20 |
| #3 Missing Media Files | ⚡ Enhancement (low priority) | - |
| #4 Instagram User Consent Error | ✅ Working as intended | - |

---

## Notes

### SSE Connection Behavior
The logs show SSE connections opening/closing every ~3 seconds. This appears to be normal behavior (client reconnection pattern), but worth monitoring for performance impact at scale.

### Environment
- **URL:** https://abuh.com.ua/chat/
- **Test Account:** testacc
- **Instagram Account:** @el_dmytr
