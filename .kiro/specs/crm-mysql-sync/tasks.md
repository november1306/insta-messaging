# Implementation Plan

Simple dual storage: write messages to both local SQLite and CRM MySQL. Keep it minimal.

## Tasks

- [x] 1. Add CRM MySQL configuration
  - Add environment variables to `.env.example` and `.env`
  - Add CRM settings to `app/config.py` (enabled, host, user, password, database)
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. Install aiomysql dependency
  - Add `aiomysql` to `requirements.txt`
  - Install with `pip install aiomysql`
  - _Requirements: 5.1_

- [x] 3. Create CRM connection pool in app startup
  - Modify `app/main.py` lifespan to create aiomysql pool if enabled
  - Store pool in `app.state.crm_pool`
  - Log connection success/failure
  - Close pool on shutdown
  - _Requirements: 3.4, 3.5, 5.1, 5.3_

- [x] 4. Modify MessageRepository to add CRM sync
  - Add `crm_pool` parameter to `__init__`
  - In `save()`, after local SQLite save succeeds, call `asyncio.create_task(self._sync_to_crm(message))`
  - Implement `_sync_to_crm()` method with try/except (log errors, don't raise)
  - Map fields: sender_id/recipient_id → user_id, direction → 'in'/'out', message_text → message
  - Add TODO comment about missing CRM schema fields
  - Fetch username from Instagram API (with fallback to user_id)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3, 6.4_

- [x] 5. Update dependency injection to pass CRM pool
  - Pass `request.app.state.crm_pool` to MessageRepository in webhook handlers
  - _Requirements: 5.2_

- [ ] 6. Manual testing and verification
  - Start app with `CRM_MYSQL_ENABLED=true` and valid credentials
  - Send test message via webhook or API
  - Verify message in local SQLite: `sqlite3 instagram_automation.db "SELECT * FROM messages ORDER BY created_at DESC LIMIT 1;"`
  - Verify message in CRM MySQL: `mysql -h mysql314.1gb.ua -u gbua_zag -p --ssl-mode=DISABLED gbua_zag -e "SELECT * FROM messages ORDER BY created_at DESC LIMIT 1;"`
  - Check logs for "✅ CRM sync OK" or "❌ CRM sync failed"
  - Test with CRM disabled: set `CRM_MYSQL_ENABLED=false`, verify local storage still works
  - Test with invalid CRM credentials: verify app starts and local storage works
  - _Requirements: All_

## Notes

- Keep it simple - no fancy abstractions, no separate services
- CRM failures are logged but don't break anything
- Local SQLite is always the source of truth
- CRM sync is fire-and-forget (async, non-blocking)
- Username fetching from Instagram API with fallback to user_id
