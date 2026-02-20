# Channel Binding Guide

How `messaging_channel_id` gets associated with an `Account` — and why getting it wrong causes cross-account data leakage.

---

## Background

When Instagram delivers a webhook it identifies the receiving business channel via `entry[].id` (also mirrored as `messaging[].recipient.id`). This value is the **messaging channel ID** — it is how Instagram's messaging infrastructure knows which business inbox the message belongs to.

The problem: this ID is **not** what the Instagram OAuth API returns. OAuth gives you `instagram_account_id` (a business profile ID). The messaging channel ID may be a completely different number for the same business account.

Until an account has received at least one webhook or completed a conversation sync, its `messaging_channel_id` column in the database is `NULL`.

```
Account (freshly linked via OAuth)
  id                  = "acc_25586af607c2"
  instagram_account_id = "24370771369265571"   <- from OAuth /me
  messaging_channel_id = NULL                  <- not yet known
  conversations_api_id = NULL                  <- not yet known
```

**Channel binding** is the process of filling in `messaging_channel_id` once we observe it in the wild.

---

## The Three-Step Binding Algorithm

Implemented in `_bind_channel_id()` (`app/api/webhooks.py`).

Called on **every** incoming webhook entry, it is fully idempotent — safe to call multiple times.

```
Webhook arrives  →  entry.id = "17841478096518771"
                         |
              ┌──────────▼──────────┐
              │ Step 1: Already     │
              │ bound?              │
              │ WHERE               │
              │ messaging_channel_id│
              │   == "178414..."    │
              └──────────┬──────────┘
          found ◄────────┴──────── not found
            |                          |
         return                        |
         (no-op)          ┌────────────▼────────────┐
                          │ Step 2: instagram_       │
                          │ account_id match?        │
                          │ WHERE                    │
                          │ instagram_account_id     │
                          │   == "178414..."         │
                          │ AND messaging_channel_id │
                          │   IS NULL                │
                          └────────────┬─────────────┘
                      found ◄──────────┴──────── not found
                        |                            |
                   bind + return       ┌─────────────▼──────────────┐
                                       │ Step 3: conversations_      │
                                       │ api_id match?              │
                                       │ WHERE                      │
                                       │ conversations_api_id        │
                                       │   == "178414..."           │
                                       │ AND messaging_channel_id   │
                                       │   IS NULL                  │
                                       └─────────────┬──────────────┘
                                   found ◄────────────┴──────── not found
                                     |                               |
                                bind + return              log WARNING + return
                                                           (never blindly assign)
```

---

## Step-by-Step Explanation

### Step 1 — Already bound (idempotency check)

```python
select(Account).where(Account.messaging_channel_id == messaging_channel_id)
```

If any account already owns this channel ID, there is nothing to do. This is the hot path for established accounts — every subsequent webhook after the first binding hits this branch and returns immediately.

### Step 2 — Match by `instagram_account_id`

```python
select(Account).where(
    Account.instagram_account_id == messaging_channel_id,
    Account.messaging_channel_id.is_(None)
)
```

Handles the common case where Instagram assigns the **same numeric ID** to both the OAuth profile and the messaging channel. When they match, the account can be unambiguously identified even without prior sync.

This is a **positive fingerprint match** — we only bind if the IDs are literally equal, not "close enough".

### Step 3 — Match by `conversations_api_id`

```python
select(Account).where(
    Account.conversations_api_id == messaging_channel_id,
    Account.messaging_channel_id.is_(None)
)
```

`conversations_api_id` is discovered during Instagram Conversations API sync (see `instagram_sync_service.py → _discover_conversations_api_id`). During sync, the service inspects message participant IDs and finds the one that belongs to the business — this becomes `conversations_api_id`.

This step handles accounts where `instagram_account_id != messaging_channel_id`. Once sync has run at least once, `conversations_api_id` is set and Step 3 can bind on the very next webhook.

### No match — warn, do NOT assign

If none of the three steps find a positive match, a `WARNING` is logged and the function returns **without modifying any account**. This is intentional.

**Why this matters for multi-tenant isolation:**

The old code had a Step 3 that did:
```python
# REMOVED — caused cross-account contamination
select(Account).where(Account.messaging_channel_id.is_(None))
# → first() → bind to whoever comes first in query order
```

In a multi-account setup this would assign el_dmytr's channel ID to vs_mua_assistant (or vice versa), making all subsequent messages for that channel appear in the wrong account's conversation list. The contamination was silent and permanent until the database was corrected manually.

---

## What Populates `conversations_api_id`?

`conversations_api_id` is set by `InstagramSyncService._discover_conversations_api_id()` during conversation sync. The discovery logic:

1. Fetches the conversation list from Instagram's Conversations API
2. Iterates participant IDs in each conversation
3. Identifies the participant that is the business (not the customer)
4. Returns that participant ID as `conversations_api_id`

This runs automatically during:
- Full account sync (`sync_account`)
- Incremental batch sync (`sync_batch`)

**Implication**: An account that has **never synced** and whose `instagram_account_id != messaging_channel_id` will **not** bind on first webhook. The webhook is dropped (logged as warning). Once the user triggers a sync, `conversations_api_id` is populated, and subsequent webhooks bind correctly via Step 3.

---

## Binding States and Transitions

```
State A: Never bound
  messaging_channel_id = NULL
  conversations_api_id = NULL
  → Step 2 binds IF instagram_account_id == channel_id
  → Otherwise: webhook dropped (warning logged)

State B: sync ran, not yet bound
  messaging_channel_id = NULL
  conversations_api_id = "178414..."
  → Step 3 binds on next webhook

State C: bound
  messaging_channel_id = "178414..."
  → Step 1 returns immediately (all future webhooks)
```

---

## Conversations Query Isolation (`ui.py`)

Separate from the binding mechanism, the conversations query in `get_conversations()` has an independent `account_id` filter:

```python
# Both subquery and outer query include:
MessageModel.account_id == account_id
```

This means even if two accounts' `business_ids` sets overlap (e.g., due to a past binding error), the query only returns messages that were **stored under** the correct account at write time. The `account_id` column on `MessageModel` is set when the message is created and never changes.

This is defense-in-depth: the binding algorithm prevents future contamination, the query filter prevents past contamination from being visible.

---

## Debugging Binding Issues

### Check current binding state
```python
# In check_database.py or a custom query
SELECT id, username, instagram_account_id, messaging_channel_id, conversations_api_id
FROM accounts;
```

### Look for binding log entries
```bash
# Successful Step 2 bind
grep "matched by instagram_account_id" logs

# Successful Step 3 bind
grep "matched by conversations_api_id" logs

# Failed bind (warning — investigate)
grep "Cannot bind channel" logs
```

### Fix a contaminated account
If `messaging_channel_id` was wrongly assigned:
```sql
-- Reset the wrong account
UPDATE accounts SET messaging_channel_id = NULL WHERE id = 'acc_wrongone';

-- The correct account will re-bind on next webhook automatically
```

### Force sync to populate `conversations_api_id`
Use the Instagram sync UI or API to run a manual sync. After sync:
- `conversations_api_id` is populated
- Next webhook will trigger Step 3 binding

---

## Key Files

| File | Responsibility |
|------|----------------|
| `app/api/webhooks.py` | `_bind_channel_id()` — the binding algorithm |
| `app/application/instagram_sync_service.py` | `_discover_conversations_api_id()` — populates `conversations_api_id` |
| `app/api/ui.py` | `get_conversations()` — `account_id` filter for isolation |
| `app/domain/account_identity.py` | `AccountIdentity` — ID resolution for message routing |
| `app/db/models.py` | `Account.messaging_channel_id`, `Account.conversations_api_id` columns |

---

## Related Docs

- [ACCOUNT_ID_GUIDE.md](ACCOUNT_ID_GUIDE.md) — All three ID types explained
- [CLAUDE.md](CLAUDE.md) — Webhook routing overview under "Webhook Routing & messaging_channel_id"
